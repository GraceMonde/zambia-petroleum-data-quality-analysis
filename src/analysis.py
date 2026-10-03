from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN_PATH = ROOT / "data" / "cleaned_data.csv"
PROCESSED_PATH = ROOT / "data" / "processed_data.csv"
ISSUES_PATH = ROOT / "data" / "issues_flagged.csv"
ROUTE_METRICS_PATH = ROOT / "data" / "route_metrics.csv"
SUMMARY_PATH = ROOT / "reports" / "analytical_summary.md"

ROUTE_DEVIATION_THRESHOLD_PCT = 10.0
REPEATED_ANOMALY_THRESHOLD = 2


def route_label(depot, destination):
    return f"{depot} -> {destination}"


def build_route_metrics(clean):
    network_rate = clean["transport_cost"].sum() / (
        clean["volume_litres"] * clean["reference_distance_km"]
    ).sum()

    metrics = (
        clean.groupby(["depot", "destination"])
        .agg(
            shipments=("shipment_id", "count"),
            volume_litres=("volume_litres", "sum"),
            transport_cost=("transport_cost", "sum"),
            reference_distance_km=("reference_distance_km", "first"),
        )
        .reset_index()
    )
    metrics["route"] = [
        route_label(depot, destination)
        for depot, destination in zip(metrics["depot"], metrics["destination"])
    ]
    metrics["cost_per_litre"] = metrics["transport_cost"] / metrics["volume_litres"]
    metrics["cost_per_litre_km"] = metrics["transport_cost"] / (
        metrics["volume_litres"] * metrics["reference_distance_km"]
    )
    metrics["deviation_pct"] = (
        metrics["cost_per_litre_km"] / network_rate - 1
    ) * 100
    return metrics, network_rate


def add_anomaly_counts(metrics, issues):
    repeated = (
        issues[issues["issue_code"] == "HIGH_COST"]["route"]
        .value_counts()
        .rename("high_cost_anomalies")
    )
    metrics = metrics.merge(repeated, left_on="route", right_index=True, how="left")
    metrics["high_cost_anomalies"] = metrics["high_cost_anomalies"].fillna(0).astype(int)
    return metrics


def flag_routes(metrics):
    costly = metrics["deviation_pct"] >= ROUTE_DEVIATION_THRESHOLD_PCT
    repeated = metrics["high_cost_anomalies"] >= REPEATED_ANOMALY_THRESHOLD

    reasons = []
    for i, row in metrics.iterrows():
        parts = []
        if row["deviation_pct"] >= ROUTE_DEVIATION_THRESHOLD_PCT:
            parts.append(
                f"cost per litre-km {row['deviation_pct']:.1f}% above network average"
            )
        if row["high_cost_anomalies"] >= REPEATED_ANOMALY_THRESHOLD:
            parts.append(
                f"{int(row['high_cost_anomalies'])} high-cost anomalies on this route"
            )
        reasons.append("; ".join(parts))

    metrics["flagged"] = costly | repeated
    metrics["flag_reason"] = reasons
    return metrics.sort_values(["flagged", "cost_per_litre_km"], ascending=[False, False])


def distance_findings(issues, network_rate):
    merged = issues[issues["issue_code"] == "DISTANCE_MISMATCH"].copy()
    if merged.empty:
        return {"count": 0, "overstated": 0, "understated": 0}

    merged["difference_km"] = (
        merged["claimed_distance_km"] - merged["reference_distance_km"]
    )
    overclaimed = merged[merged["difference_km"] > 0]
    exposure = (
        (overclaimed["difference_km"] * overclaimed["volume_litres"]).sum() * network_rate
    )
    worst = merged.loc[merged["difference_km"].abs().idxmax()]
    return {
        "count": len(merged),
        "overstated": len(overclaimed),
        "understated": int((merged["difference_km"] < 0).sum()),
        "total_overstated_km": float(overclaimed["difference_km"].sum()),
        "max_abs_km": abs(float(worst["difference_km"])),
        "max_route": worst["route"],
        "exposure_zmw": float(exposure),
    }


def build_summary(metrics, clean, issues, network_rate, distance_stats, n_total):
    flagged = metrics[metrics["flagged"]].sort_values(
        "cost_per_litre_km", ascending=False
    )
    total_volume = clean["volume_litres"].sum()
    product_mix = (
        clean.groupby("product")["volume_litres"].sum().sort_values(ascending=False)
    )
    product_share = (product_mix / total_volume * 100).round(1)
    province_mix = (
        clean.groupby("province")["volume_litres"].sum().sort_values(ascending=False)
    )
    monthly = clean.copy()
    monthly["month"] = monthly["shipment_date"].str[:7]
    monthly_stats = monthly.groupby("month").agg(
        volume=("volume_litres", "sum"),
        avg_cost=("transport_cost", "mean"),
    )
    clean_pct = len(clean) / n_total * 100
    missing_distance = int((issues["issue_code"] == "MISSING_DISTANCE").sum())
    volume_change = (
        monthly_stats["volume"].iloc[-1] / monthly_stats["volume"].iloc[-2] - 1
    ) * 100
    volume_direction = "rose" if volume_change >= 0 else "fell"

    lines = [
        "# Analytical Summary",
        "",
        "**Question:** Which routes require further investigation?",
        "",
        f"All calculations use the {len(clean)} clean records (`data/cleaned_data.csv`); "
        "records with outstanding data-quality issues are held in "
        "`data/issues_flagged.csv` and reviewed separately. Cost per litre-km is "
        "normalised on the **reference** distance so that disputed claims cannot "
        "distort the comparison.",
        "",
        "## Method",
        "",
        "1. Cost per litre = transport cost / volume.",
        "2. Cost per litre-km = transport cost / (volume x reference distance).",
        "3. Route values are compared with the network average of "
        f"**{network_rate:.6f} ZMW per litre-km**.",
        f"4. A route is **flagged for further investigation** if either:",
        f"   - its cost per litre-km is **{ROUTE_DEVIATION_THRESHOLD_PCT:.0f}% or more** "
        "above the network average, or",
        f"   - it carries **{REPEATED_ANOMALY_THRESHOLD} or more** high-cost anomaly "
        "records (repeat exceptions, not one-off variance).",
        "",
        "## Routes flagged",
        "",
    ]

    if flagged.empty:
        lines.append("_No routes exceeded the flagging rules._")
    else:
        lines += [
            "| Route | Shipments | Volume (L) | Cost/litre (ZMW) | Cost/litre-km | Vs network | Anomalies | Reason |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for _, row in flagged.iterrows():
            lines.append(
                f"| {row['route']} | {int(row['shipments'])} | "
                f"{row['volume_litres']:,.0f} | {row['cost_per_litre']:.3f} | "
                f"{row['cost_per_litre_km']:.6f} | {row['deviation_pct']:+.1f}% | "
                f"{int(row['high_cost_anomalies'])} | {row['flag_reason']} |"
            )

    lines += [
        "",
        f"Routes assessed: **{len(metrics)}** - full table in `data/route_metrics.csv`.",
        "",
        "## Network position",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Network cost per litre-km | {network_rate:.6f} ZMW |",
        f"| Network cost per litre | "
        f"{clean['transport_cost'].sum() / total_volume:.3f} ZMW |",
        f"| Clean volume moved | {total_volume:,.0f} L |",
        f"| Clean shipments | {len(clean):,.0f} |",
        f"| Product leader | {product_mix.index[0]} "
        f"({product_share.iloc[0]:.1f}% of volume) |",
        f"| Busiest month by volume | {monthly_stats['volume'].idxmax()} "
        f"({monthly_stats['volume'].max():,.0f} L) |",
        f"| Highest average monthly cost | {monthly_stats['avg_cost'].idxmax()} "
        f"(ZMW {monthly_stats['avg_cost'].max():,.0f}) |",
        "",
        "## Data-quality context",
        "",
        "| Measure | Value |",
        "| --- | ---: |",
        f"| Records read | {n_total} |",
        f"| Clean records | {len(clean)} ({clean_pct:.1f}%) |",
        f"| Issues raised | {len(issues)} across {issues['issue_code'].nunique()} categories |",
        f"| Distance discrepancies | {distance_stats['count']} "
        f"({distance_stats.get('overstated', 0)} claimed longer than reference, "
        f"{distance_stats.get('understated', 0)} shorter) |",
        f"| Largest single distance gap | {distance_stats.get('max_abs_km', 0):,.0f} km "
        f"({distance_stats.get('max_route', '-')}) |",
        f"| Indicative exposure on overstated claims | "
        f"ZMW {distance_stats.get('exposure_zmw', 0):,.0f} |",
        "",
        "> The exposure figure is an order-of-magnitude estimate: the additional claimed",
        "> distance valued at the network average rate on the recorded volumes. It is",
        "> presented for verification against supporting documentation, not as a loss.",
        "",
        "## Findings",
        "",
        f"1. **{len(clean)} of {n_total} records ({clean_pct:.1f}%) were usable after "
        f"cleaning**; {len(issues)} issues were raised across "
        f"{issues['issue_code'].nunique()} categories, led by distance discrepancies "
        f"({distance_stats['count']}) and missing claimed distances "
        f"({missing_distance}).",
        f"2. **{len(flagged)} routes were flagged for further investigation**"
        + (
            ": "
            + "; ".join(
                f"{row['route']} ({row['flag_reason']})"
                for _, row in flagged.iterrows()
            )
            + "."
            if not flagged.empty
            else "."
        ),
        f"3. **Distance claims diverge from reference distances on both sides** - "
        f"{distance_stats.get('overstated', 0)} records claimed a longer journey and "
        f"{distance_stats.get('understated', 0)} a shorter one, with a maximum gap of "
        f"{distance_stats.get('max_abs_km', 0):,.0f} km "
        f"({distance_stats.get('max_route', '-')}).",
        f"4. **Demand is concentrated**: {product_mix.index[0]} and "
        f"{product_mix.index[1]} account for "
        f"{product_share.iloc[0] + product_share.iloc[1]:.1f}% of clean volume, and "
        f"{province_mix.index[0]} is the largest destination province "
        f"({province_mix.iloc[0] / total_volume * 100:.1f}% of volume).",
        f"5. **Cost intensity rose after {monthly_stats.index[0]}**: average transport "
        f"cost per shipment moved from ZMW {monthly_stats['avg_cost'].iloc[0]:,.0f} "
        f"({monthly_stats.index[0]}) to a peak of "
        f"ZMW {monthly_stats['avg_cost'].max():,.0f} "
        f"({monthly_stats['avg_cost'].idxmax()}) and closed the period at "
        f"ZMW {monthly_stats['avg_cost'].iloc[-1]:,.0f} "
        f"({monthly_stats.index[-1]}), while clean volume {volume_direction} "
        f"{abs(volume_change):.1f}% between {monthly_stats.index[-2]} and "
        f"{monthly_stats.index[-1]}.",
        "",
    ]
    return "\n".join(lines)


def main():
    clean = pd.read_csv(CLEAN_PATH)
    issues = pd.read_csv(ISSUES_PATH)
    n_total = len(pd.read_csv(PROCESSED_PATH))

    metrics, network_rate = build_route_metrics(clean)
    metrics = add_anomaly_counts(metrics, issues)
    metrics = flag_routes(metrics)

    distance_stats = distance_findings(issues, network_rate)

    metrics_out = metrics[
        [
            "route",
            "depot",
            "destination",
            "reference_distance_km",
            "shipments",
            "volume_litres",
            "transport_cost",
            "cost_per_litre",
            "cost_per_litre_km",
            "deviation_pct",
            "high_cost_anomalies",
            "flagged",
            "flag_reason",
        ]
    ].sort_values("cost_per_litre_km", ascending=False)
    metrics_out.to_csv(ROUTE_METRICS_PATH, index=False)

    SUMMARY_PATH.write_text(
        build_summary(metrics, clean, issues, network_rate, distance_stats, n_total),
        encoding="utf-8",
    )

    flagged = metrics[metrics["flagged"]]
    print(f"network cost per litre-km : {network_rate:.6f} ZMW")
    print(f"routes assessed            : {len(metrics)}")
    print(f"routes flagged             : {len(flagged)}")
    for _, row in flagged.sort_values("cost_per_litre_km", ascending=False).iterrows():
        print(f"  - {row['route']}: {row['flag_reason']}")
    print(f"wrote {ROUTE_METRICS_PATH.name}, {SUMMARY_PATH.name}")


if __name__ == "__main__":
    main()
