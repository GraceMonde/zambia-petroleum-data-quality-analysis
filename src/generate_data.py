from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_RECORDS = 400
START_DATE = pd.Timestamp("2026-07-01")
END_DATE = pd.Timestamp("2026-09-30")

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw_data.csv"

COMPANIES = [
    "ZamFuel Trading Ltd",
    "Copperbelt Fuels Ltd",
    "Rift Petro Supplies Ltd",
    "Great Lakes Energy Ltd",
    "Zambezi Oil Distributors Ltd",
    "Mosi Petroleum Merchants Ltd",
]
COMPANY_WEIGHTS = [0.28, 0.22, 0.16, 0.14, 0.11, 0.09]

DEPOT_WEIGHT_BY_NAME = {
    "Lusaka": 3.0,
    "Ndola": 2.5,
    "Kitwe": 2.0,
    "Kabwe": 1.5,
    "Livingstone": 1.0,
    "Kasama": 1.5,
}

ROUTES = [
    ("Lusaka", "Kabwe", "Central", 130),
    ("Lusaka", "Choma", "Southern", 320),
    ("Lusaka", "Livingstone", "Southern", 485),
    ("Lusaka", "Ndola", "Copperbelt", 370),
    ("Lusaka", "Kitwe", "Copperbelt", 345),
    ("Lusaka", "Mongu", "Western", 560),
    ("Lusaka", "Chipata", "Eastern", 365),
    ("Lusaka", "Mansa", "Luapula", 455),
    ("Lusaka", "Solwezi", "North-Western", 575),
    ("Lusaka", "Petauke", "Eastern", 420),
    ("Ndola", "Kitwe", "Copperbelt", 65),
    ("Ndola", "Chingola", "Copperbelt", 60),
    ("Ndola", "Mufulira", "Copperbelt", 45),
    ("Ndola", "Solwezi", "North-Western", 215),
    ("Ndola", "Kasumbalesa", "Copperbelt", 105),
    ("Ndola", "Kapiri Mposhi", "Central", 150),
    ("Kabwe", "Mkushi", "Central", 95),
    ("Kabwe", "Serenje", "Central", 175),
    ("Livingstone", "Kazungula", "Southern", 80),
    ("Livingstone", "Sesheke", "Western", 145),
    ("Livingstone", "Choma", "Southern", 200),
    ("Kitwe", "Kalulushi", "Copperbelt", 40),
    ("Kitwe", "Chingola", "Copperbelt", 65),
    ("Kasama", "Mpika", "Muchinga", 190),
    ("Kasama", "Mbala", "Northern", 90),
    ("Kasama", "Serenje", "Central", 215),
]

PRODUCTS = ["Petrol", "Diesel", "Kerosene", "Jet A-1"]
PRODUCT_WEIGHTS = [0.40, 0.38, 0.14, 0.08]

VOLUMES = [24000, 28000, 30000, 32000, 34000, 36000, 38000, 40000]

N_MISSING_DISTANCE = 11
N_INVALID_VOLUME = 4
N_DISTANCE_MISMATCH = 17
N_HIGH_COST = 9
N_MISSING_COMPANY = 3
N_MISSING_DEPOT = 3
N_DUPLICATES = 8
N_PRODUCT_VARIANTS = 25
N_COMMA_COSTS = 3


def route_weights():
    weights = np.array([DEPOT_WEIGHT_BY_NAME[r[0]] for r in ROUTES], dtype=float)
    return weights / weights.sum()


def assign_indices(rng, pool, sizes):
    shuffled = rng.permutation(pool)
    assigned = []
    cursor = 0
    for size in sizes:
        assigned.append(np.sort(shuffled[cursor:cursor + size]))
        cursor += size
    return assigned


def product_variant(rng, value):
    choice = rng.integers(0, 4)
    if choice == 0:
        return value.lower()
    if choice == 1:
        return value.upper()
    if choice == 2:
        return f" {value} "
    return f"{value.lower()} "


def generate_rows(rng):
    n_routes = len(ROUTES)
    route_idx = rng.choice(n_routes, size=N_RECORDS, p=route_weights())
    company_idx = rng.choice(len(COMPANIES), size=N_RECORDS, p=COMPANY_WEIGHTS)
    product_idx = rng.choice(len(PRODUCTS), size=N_RECORDS, p=PRODUCT_WEIGHTS)
    day_offset = rng.integers(0, (END_DATE - START_DATE).days + 1, size=N_RECORDS)
    volumes = rng.choice(VOLUMES, size=N_RECORDS)
    route_rates = rng.uniform(0.0040, 0.0050, size=n_routes)
    noise = np.clip(rng.normal(1.0, 0.05, size=N_RECORDS), 0.85, 1.15)

    rows = []
    for i in range(N_RECORDS):
        depot, destination, province, reference_km = ROUTES[route_idx[i]]
        rate = route_rates[route_idx[i]]
        volume = int(volumes[i])
        cost = int(round(volume * reference_km * rate * noise[i]))
        rows.append(
            {
                "shipment_id": f"SHP-{i + 1:04d}",
                "shipment_date": (START_DATE + pd.Timedelta(days=int(day_offset[i]))).strftime("%Y-%m-%d"),
                "company": COMPANIES[company_idx[i]],
                "depot": depot,
                "product": PRODUCTS[product_idx[i]],
                "destination": destination,
                "province": province,
                "volume_litres": volume,
                "reference_distance_km": int(reference_km),
                "claimed_distance_km": int(reference_km),
                "transport_cost": cost,
            }
        )
    return rows


def inject_issues(rng, rows):
    issue_pool = list(range(N_RECORDS))
    missing_distance, invalid_volume, mismatch, high_cost, missing_company, missing_depot = assign_indices(
        rng,
        issue_pool,
        [
            N_MISSING_DISTANCE,
            N_INVALID_VOLUME,
            N_DISTANCE_MISMATCH,
            N_HIGH_COST,
            N_MISSING_COMPANY,
            N_MISSING_DEPOT,
        ],
    )

    for i in missing_distance:
        rows[i]["claimed_distance_km"] = None

    invalid_patterns = ["N/A", "N/A", 0, -5000]
    for i, pattern in zip(invalid_volume, invalid_patterns):
        rows[i]["volume_litres"] = pattern

    for i in mismatch:
        delta = int(rng.choice([-1, 1]) * rng.integers(25, 91))
        rows[i]["claimed_distance_km"] = max(int(rows[i]["reference_distance_km"]) + delta, 5)

    for i in high_cost:
        rows[i]["transport_cost"] = int(round(rows[i]["transport_cost"] * rng.uniform(1.7, 2.4)))

    for i in missing_company:
        rows[i]["company"] = ""

    for i in missing_depot:
        rows[i]["depot"] = ""

    issue_rows = sorted(
        set(missing_distance)
        | set(invalid_volume)
        | set(mismatch)
        | set(high_cost)
        | set(missing_company)
        | set(missing_depot)
    )
    clean_pool = [i for i in range(N_RECORDS) if i not in set(issue_rows)]

    variant_idx = rng.choice(clean_pool, size=N_PRODUCT_VARIANTS, replace=False)
    for i in variant_idx:
        rows[i]["product"] = product_variant(rng, rows[i]["product"])

    comma_idx = rng.choice(clean_pool, size=N_COMMA_COSTS, replace=False)
    for i in comma_idx:
        rows[i]["transport_cost"] = f"{rows[i]['transport_cost']:,}"

    duplicate_sources = rng.choice(clean_pool, size=N_DUPLICATES, replace=False)
    duplicates = [dict(rows[i]) for i in duplicate_sources]

    return rows + duplicates


def main():
    rng = np.random.default_rng(SEED)
    rows = inject_issues(rng, generate_rows(rng))
    for sequence, row in enumerate(rows, start=1):
        row["record_id"] = sequence
    ordered = ["record_id"] + [key for key in rows[0] if key != "record_id"]
    df = pd.DataFrame(rows)[ordered]
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW_PATH, index=False)
    print(f"Wrote {len(df)} records to {RAW_PATH}")


if __name__ == "__main__":
    main()
