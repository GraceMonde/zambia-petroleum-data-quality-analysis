from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw_data.csv"
CLEAN_PATH = ROOT / "data" / "cleaned_data.csv"
PROCESSED_PATH = ROOT / "data" / "processed_data.csv"
ISSUES_PATH = ROOT / "data" / "issues_flagged.csv"
REPORT_PATH = ROOT / "reports" / "data_quality_report.md"

DISTANCE_TOLERANCE_KM = 20
IQR_MULTIPLIER = 3.0

CANONICAL_PRODUCTS = ["Petrol", "Diesel", "Kerosene", "Jet A-1"]

ISSUE_LABELS = {
    "DUPLICATE": "Duplicate record",
    "MISSING_DIMENSION": "Missing company/depot",
    "MISSING_DISTANCE": "Missing distance",
    "INVALID_VOLUME": "Invalid volume",
    "DISTANCE_MISMATCH": "Distance discrepancy",
    "HIGH_COST": "High-cost anomaly",
    "DATE_INVALID": "Invalid date",
}

ISSUE_ORDER = [
    "DUPLICATE",
    "MISSING_DIMENSION",
    "MISSING_DISTANCE",
    "INVALID_VOLUME",
    "DISTANCE_MISMATCH",
    "HIGH_COST",
    "DATE_INVALID",
]

SEVERITY = {
    "DUPLICATE": "Medium",
    "MISSING_DIMENSION": "High",
    "MISSING_DISTANCE": "High",
    "INVALID_VOLUME": "High",
    "DISTANCE_MISMATCH": "High",
    "HIGH_COST": "Medium",
    "DATE_INVALID": "High",
}

NUMERIC_COLUMNS = [
    "volume_litres",
    "reference_distance_km",
    "claimed_distance_km",
    "transport_cost",
]

TEXT_COLUMNS = ["company", "depot", "product", "destination", "province"]


def load_raw():
    return pd.read_csv(RAW_PATH, dtype=str, keep_default_na=False, na_filter=False)


def standardise_text(df):
    changes = {}
    stripped = {col: df[col].str.strip() for col in TEXT_COLUMNS}

    product_lookup = {name.lower(): name for name in CANONICAL_PRODUCTS}
    canonical_product = (
        stripped["product"].str.lower().map(product_lookup).fillna(stripped["product"].str.title())
    )
    changes["product"] = int((df["product"] != canonical_product).sum())
    df["product"] = canonical_product

    for col in ["company", "depot", "destination", "province"]:
        changes[col] = int((df[col] != stripped[col]).sum())
        df[col] = stripped[col]

    return df, changes


def coerce_numerics(df):
    fixed = 0
    for col in NUMERIC_COLUMNS:
        raw = df[col]
        cleaned = raw.str.replace(",", "", regex=False)
        fixed += int((cleaned != raw).sum())
        df[col] = pd.to_numeric(cleaned, errors="coerce")
    return df, fixed


def parse_dates(df):
    df["shipment_date"] = pd.to_datetime(df["shipment_date"], errors="coerce")
    return df


def compute_cost_threshold(df, duplicate_mask):
    candidate = df[
        ~duplicate_mask
        & df["volume_litres"].gt(0)
        & df["transport_cost"].gt(0)
        & df["reference_distance_km"].gt(0)
    ]
    rate = candidate["transport_cost"] / (
        candidate["volume_litres"] * candidate["reference_distance_km"]
    )
    q1, q3 = rate.quantile([0.25, 0.75])
    return q3 + IQR_MULTIPLIER * (q3 - q1)


def comparison_columns(df):
    return [col for col in df.columns if col != "record_id"]


def build_flags(df, duplicate_mask, threshold):
    grouped = df.groupby(comparison_columns(df), dropna=False)
    first_id = grouped["shipment_id"].transform("first")
    first_record = grouped["record_id"].transform("first")
    flags = []
    for i, row in df.iterrows():
        recorded = []

        if duplicate_mask.loc[i]:
            recorded.append(
                ("DUPLICATE", f"Identical to {first_id.loc[i]} (record {first_record.loc[i]})")
            )

        missing_dims = [col for col in ["company", "depot", "destination"] if not row[col]]
        if missing_dims:
            recorded.append(("MISSING_DIMENSION", f"{', '.join(missing_dims)} not supplied"))

        if pd.isna(row["shipment_date"]):
            recorded.append(("DATE_INVALID", "shipment_date is not a valid date"))

        if pd.isna(row["claimed_distance_km"]):
            recorded.append(("MISSING_DISTANCE", "claimed_distance_km is empty or non-numeric"))
        elif pd.isna(row["reference_distance_km"]):
            recorded.append(("MISSING_DISTANCE", "reference_distance_km is empty or non-numeric"))

        volume = row["volume_litres"]
        if pd.isna(volume):
            recorded.append(("INVALID_VOLUME", "volume_litres is empty or non-numeric"))
        elif volume <= 0:
            recorded.append(("INVALID_VOLUME", f"volume_litres = {volume:,.0f}"))

        if pd.notna(row["claimed_distance_km"]) and pd.notna(row["reference_distance_km"]):
            difference = abs(row["claimed_distance_km"] - row["reference_distance_km"])
            if difference > DISTANCE_TOLERANCE_KM:
                recorded.append(
                    (
                        "DISTANCE_MISMATCH",
                        f"claimed {row['claimed_distance_km']:,.0f} km vs reference "
                        f"{row['reference_distance_km']:,.0f} km (difference {difference:,.0f} km)",
                    )
                )

        if (
            pd.notna(volume)
            and volume > 0
            and pd.notna(row["reference_distance_km"])
            and row["reference_distance_km"] > 0
            and pd.notna(row["transport_cost"])
            and row["transport_cost"] > 0
        ):
            rate = row["transport_cost"] / (volume * row["reference_distance_km"])
            if rate > threshold:
                recorded.append(
                    (
                        "HIGH_COST",
                        f"{rate:.5f} ZMW per litre-km exceeds threshold of {threshold:.5f}",
                    )
                )

        for code, detail in recorded:
            flags.append(
                {
                    "row_index": i,
                    "shipment_id": row["shipment_id"],
                    "issue": code,
                    "severity": SEVERITY[code],
                    "detail": detail,
                }
            )
    return pd.DataFrame(flags)


def build_issues_frame(df, flags):
    issues = df.loc[flags["row_index"]].copy()
    issues.insert(2, "route", issues["depot"] + " -> " + issues["destination"])
    issues["issue_code"] = flags["issue"].to_numpy()
    issues["issue"] = flags["issue"].map(ISSUE_LABELS).to_numpy()
    issues["severity"] = flags["severity"].to_numpy()
    issues["detail"] = flags["detail"].to_numpy()
    issues["shipment_date"] = issues["shipment_date"].dt.strftime("%Y-%m-%d")
    issues = issues[
        [
            "record_id",
            "shipment_id",
            "shipment_date",
            "company",
            "route",
            "product",
            "issue_code",
            "issue",
            "severity",
            "detail",
            "volume_litres",
            "claimed_distance_km",
            "reference_distance_km",
            "transport_cost",
        ]
    ]
    return issues.sort_values(["issue_code", "shipment_id"])


def build_processed_frame(df, flags):
    codes = {}
    if len(flags):
        for row_index, code in zip(flags["row_index"], flags["issue"]):
            codes.setdefault(row_index, []).append(code)

    processed = df.copy()
    joined = [";".join(sorted(codes.get(i, []))) for i in processed.index]
    processed["issues"] = joined
    processed["quality_status"] = ["clean" if not value else "flagged" for value in joined]
    processed["shipment_date"] = processed["shipment_date"].dt.strftime("%Y-%m-%d")
    return processed.sort_values(["shipment_date", "shipment_id"])


def write_report(total, counts, n_flagged, resolved, threshold, n_clean):
    lines = [
        "# Data Quality Report",
        "",
        "Synthetic portfolio dataset - `data/raw_data.csv` (generated by `src/generate_data.py`).",
        "",
        "## Validation summary",
        "",
        "| Check | Records affected | Severity |",
        "| --- | ---: | --- |",
    ]
    for code in ISSUE_ORDER:
        lines.append(f"| {ISSUE_LABELS[code]} | {counts.get(code, 0)} | {SEVERITY[code]} |")

    lines += [
        "",
        "| Measure | Records |",
        "| --- | ---: |",
        f"| Total records read | {total} |",
        f"| Records with at least one issue | {n_flagged} |",
        f"| **Clean records** | **{n_clean}** |",
        "",
        "> Counts in the first table are issue occurrences; a record can raise more than one issue.",
        "> Clean records = records with no outstanding issue after cleaning.",
        "",
        "## Issues resolved during cleaning",
        "",
        "| Action | Records/fields updated |",
        "| --- | ---: |",
    ]
    for action, count in resolved:
        lines.append(f"| {action} | {count} |")

    lines += [
        "",
        "## Detection thresholds",
        "",
        f"- Distance tolerance: claimed vs reference distance difference > {DISTANCE_TOLERANCE_KM} km",
        f"- High-cost anomaly: cost per litre-km > Q3 + {IQR_MULTIPLIER:g} x IQR "
        f"= {threshold:.5f} ZMW per litre-km",
        f"- Cost per litre-km normalised on reference distance, rows with missing or "
        f"non-positive volume/distance/cost excluded from the threshold calculation",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main():
    raw = load_raw()
    total = len(raw)

    df, text_changes = standardise_text(raw)
    df, numeric_fixes = coerce_numerics(df)
    df = parse_dates(df)

    duplicate_mask = df.duplicated(subset=comparison_columns(df), keep="first")
    threshold = compute_cost_threshold(df, duplicate_mask)
    flags = build_flags(df, duplicate_mask, threshold)

    counts = flags["issue"].value_counts().to_dict() if len(flags) else {}
    flagged_rows = set(flags["row_index"]) if len(flags) else set()
    clean = df[~df.index.isin(flagged_rows)].copy()

    issues = build_issues_frame(df, flags) if len(flags) else pd.DataFrame()
    processed = build_processed_frame(df, flags)

    clean = clean.sort_values(["shipment_date", "shipment_id"])
    clean_export = clean.copy()
    clean_export["shipment_date"] = clean_export["shipment_date"].dt.strftime("%Y-%m-%d")
    clean_export.to_csv(CLEAN_PATH, index=False)
    processed.to_csv(PROCESSED_PATH, index=False)
    issues.to_csv(ISSUES_PATH, index=False)

    resolved = [
        ("Product names standardised (case/whitespace)", text_changes["product"]),
        ("Text fields stripped of whitespace", sum(text_changes[c] for c in ["company", "depot", "destination", "province"])),
        ("Numeric fields reformatted (thousand separators)", numeric_fixes),
        ("Duplicate rows removed from clean output", int(duplicate_mask.sum())),
    ]

    write_report(total, counts, len(flagged_rows), resolved, threshold, len(clean))

    print(f"records read          : {total}")
    for code in ISSUE_ORDER:
        if counts.get(code):
            print(f"{ISSUE_LABELS[code]:<22}: {counts[code]}")
    print(f"clean records         : {len(clean)}")
    print(f"high-cost threshold   : {threshold:.5f} ZMW/litre-km")
    print(f"wrote {CLEAN_PATH.name}, {PROCESSED_PATH.name}, {ISSUES_PATH.name}, {REPORT_PATH.name}")


if __name__ == "__main__":
    main()
