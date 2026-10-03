import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_PATH = ROOT / "data" / "processed_data.csv"
ISSUES_PATH = ROOT / "data" / "issues_flagged.csv"
DB_PATH = ROOT / "data" / "warehouse.db"

NOT_SUPPLIED = "(not supplied)"

SCHEMA = """
CREATE TABLE companies (
    company_id   INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL UNIQUE
);

CREATE TABLE depots (
    depot_id   INTEGER PRIMARY KEY,
    depot_name TEXT NOT NULL UNIQUE
);

CREATE TABLE destinations (
    destination_id   INTEGER PRIMARY KEY,
    destination_name TEXT NOT NULL,
    province         TEXT NOT NULL,
    UNIQUE (destination_name, province)
);

CREATE TABLE routes (
    route_id             INTEGER PRIMARY KEY,
    depot_id             INTEGER NOT NULL REFERENCES depots(depot_id),
    destination_id       INTEGER NOT NULL REFERENCES destinations(destination_id),
    reference_distance_km INTEGER NOT NULL,
    UNIQUE (depot_id, destination_id)
);

CREATE TABLE shipments (
    record_id              INTEGER PRIMARY KEY,
    shipment_id            TEXT NOT NULL,
    shipment_date          DATE NOT NULL,
    company_id             INTEGER NOT NULL REFERENCES companies(company_id),
    depot_id               INTEGER NOT NULL REFERENCES depots(depot_id),
    destination_id         INTEGER NOT NULL REFERENCES destinations(destination_id),
    product                TEXT NOT NULL,
    volume_litres          REAL,
    reference_distance_km  INTEGER,
    claimed_distance_km    REAL,
    transport_cost         REAL,
    quality_status         TEXT NOT NULL CHECK (quality_status IN ('clean', 'flagged'))
);

CREATE TABLE shipment_issues (
    issue_id    INTEGER PRIMARY KEY,
    record_id   INTEGER NOT NULL REFERENCES shipments(record_id),
    issue_code  TEXT NOT NULL,
    issue       TEXT NOT NULL,
    severity    TEXT NOT NULL CHECK (severity IN ('High', 'Medium', 'Low')),
    detail      TEXT NOT NULL
);

CREATE INDEX idx_shipments_status ON shipments (quality_status);
CREATE INDEX idx_shipments_business_key ON shipments (shipment_id);
CREATE INDEX idx_shipments_destination ON shipments (destination_id);
CREATE INDEX idx_shipments_date ON shipments (shipment_date);
CREATE INDEX idx_issues_record ON shipment_issues (record_id);
"""


def dimension(values, not_supplied=NOT_SUPPLIED):
    members = sorted({value for value in values if value and value == value})
    ids = {value: i + 1 for i, value in enumerate(members)}
    ids[not_supplied] = 0
    return ids


def to_records(ids):
    lookup = {code: name for name, code in ids.items()}
    return [(code, name) for code, name in sorted(lookup.items())]


def main():
    processed = pd.read_csv(PROCESSED_PATH)
    issues = pd.read_csv(ISSUES_PATH)

    if DB_PATH.exists():
        DB_PATH.unlink()

    processed["company"] = processed["company"].fillna(NOT_SUPPLIED)
    processed["depot"] = processed["depot"].fillna(NOT_SUPPLIED)

    company_ids = dimension(processed["company"])
    depot_ids = dimension(processed["depot"])
    destination_pairs = sorted(set(zip(processed["destination"], processed["province"])))
    destination_ids = {
        (name, province): i + 1 for i, (name, province) in enumerate(destination_pairs)
    }

    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)

    connection.executemany(
        "INSERT INTO companies (company_id, company_name) VALUES (?, ?)",
        to_records(company_ids),
    )
    connection.executemany(
        "INSERT INTO depots (depot_id, depot_name) VALUES (?, ?)",
        to_records(depot_ids),
    )
    connection.executemany(
        "INSERT INTO destinations (destination_id, destination_name, province) VALUES (?, ?, ?)",
        [(destination_ids[key], key[0], key[1]) for key in destination_pairs],
    )

    route_rows = sorted(
        {
            (depot_ids[depot], destination_ids[(destination, province)], int(distance))
            for depot, destination, province, distance in zip(
                processed["depot"],
                processed["destination"],
                processed["province"],
                processed["reference_distance_km"],
            )
            if depot_ids[depot] != 0 and pd.notna(distance)
        }
    )
    connection.executemany(
        "INSERT INTO routes (route_id, depot_id, destination_id, reference_distance_km) "
        "VALUES (?, ?, ?, ?)",
        [(i + 1, row[0], row[1], row[2]) for i, row in enumerate(route_rows)],
    )

    shipment_rows = [
        (
            int(row.record_id),
            row.shipment_id,
            row.shipment_date,
            company_ids[row.company],
            depot_ids[row.depot],
            destination_ids[(row.destination, row.province)],
            row.product,
            None if pd.isna(row.volume_litres) else float(row.volume_litres),
            None if pd.isna(row.reference_distance_km) else int(row.reference_distance_km),
            None if pd.isna(row.claimed_distance_km) else float(row.claimed_distance_km),
            None if pd.isna(row.transport_cost) else float(row.transport_cost),
            row.quality_status,
        )
        for row in processed.itertuples(index=False)
    ]
    connection.executemany(
        "INSERT INTO shipments (record_id, shipment_id, shipment_date, company_id, depot_id, "
        "destination_id, product, volume_litres, reference_distance_km, claimed_distance_km, "
        "transport_cost, quality_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        shipment_rows,
    )

    connection.executemany(
        "INSERT INTO shipment_issues (record_id, issue_code, issue, severity, detail) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (int(row.record_id), row.issue_code, row.issue, row.severity, row.detail)
            for row in issues.itertuples(index=False)
        ],
    )
    connection.commit()

    broken = connection.execute("PRAGMA foreign_key_check").fetchall()
    counts = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in [
            "companies",
            "depots",
            "destinations",
            "routes",
            "shipments",
            "shipment_issues",
        ]
    }
    connection.close()

    print(f"database: {DB_PATH}")
    for table, count in counts.items():
        print(f"  {table:<18}: {count}")
    print(f"  foreign key violations: {len(broken)}")


if __name__ == "__main__":
    main()
