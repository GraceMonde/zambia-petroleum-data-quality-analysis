# Power BI Build Specification

Companion to the Excel dashboard (`dashboard/ERB_transport_dashboard.xlsx`).
Build in **Power BI Desktop** and save as `dashboard/ERB_transport_dashboard.pbix`.

Everything here is reproducible from the committed files; no external data source is required.

---

## 1. Data sources

**Option A - SQLite (recommended, matches the SQL portion of this project)**

1. `Get data` -> `Database` -> `SQLite database`
2. File: `data/warehouse.db`
3. Load: `shipments`, `shipment_issues`, `companies`, `depots`, `destinations`, `routes`
4. Also `Get data` -> `Text/CSV` -> `data/route_metrics.csv` (route-level summary, used by the flagged-routes table)

**Option B - CSV files**

1. `Get data` -> `Text/CSV`
2. Load: `data/cleaned_data.csv` (fact, 353 rows), `data/issues_flagged.csv` (exceptions, 55 rows), `data/route_metrics.csv` (route summary, 26 rows)

> In Option B the fact table is `cleaned_data` (already filtered to clean records), so it has no
> `quality_status` column and no `quality_status` filter is needed on visuals 1-4. Field names are
> the CSV column names: `destination` instead of `destinations[destination_name]`, and so on.

### Power Query steps (both options)

| Step | Action |
| --- | --- |
| 1 | Set `shipment_date` data type to **Date** |
| 2 | Add column -> **Week Start** = `Date.StartOfWeek([shipment_date], Day.Monday)` |
| 3 | Set `volume_litres`, `claimed_distance_km`, `reference_distance_km`, `transport_cost` to **Decimal number** |
| 4 | Rename `quality_status` values `clean` / `flagged` (already correct) |
| 5 | Close & Apply |

---

## 2. Model

Option A relationships (single star schema):

| From | To | Cardinality |
| --- | --- | --- |
| `shipment_issues[record_id]` | `shipments[record_id]` | many-to-one, cross filter single |
| `shipments[company_id]` | `companies[company_id]` | many-to-one |
| `shipments[depot_id]` | `depots[depot_id]` | many-to-one |
| `shipments[destination_id]` | `destinations[destination_id]` | many-to-one |
| `shipments[destination_id]` + `shipments[depot_id]` | `routes[destination_id]` + `routes[depot_id]` | many-to-one |

Option B: leave the three CSV tables unrelated and measure-driven (they are pre-aggregated or pre-filtered extracts).

`route_metrics` is a standalone summary table in both options - it needs no relationship.

> `record_id` is the surrogate key. Do **not** relate on `shipment_id`: the dataset deliberately
> contains 8 duplicate rows that share a `shipment_id`.

---

## 3. Measures (DAX)

Create a measure table called `Measures`.

> Table names below assume Option A. For Option B replace `shipments` with `cleaned_data`,
> `shipment_issues` with `issues_flagged`, and remove the `quality_status` filters.

```dax
Total shipments      = COUNTROWS ( shipments )
Clean shipments      = CALCULATE ( COUNTROWS ( shipments ), shipments[quality_status] = "clean" )
Data quality issues  = COUNTROWS ( shipment_issues )
Clean rate %         = DIVIDE ( [Clean shipments], [Total shipments] )
Volume moved (L)     = CALCULATE ( SUM ( shipments[volume_litres] ), shipments[quality_status] = "clean" )
Avg transport cost   = CALCULATE ( AVERAGE ( shipments[transport_cost] ), shipments[quality_status] = "clean" )
```

```dax
Cost per litre =
    DIVIDE (
        CALCULATE ( SUM ( shipments[transport_cost] ), shipments[quality_status] = "clean" ),
        [Volume moved (L)]
    )

Cost per litre-km =
    DIVIDE (
        CALCULATE ( SUM ( shipments[transport_cost] ), shipments[quality_status] = "clean" ),
        SUMX (
            FILTER ( shipments, shipments[quality_status] = "clean" ),
            shipments[volume_litres] * shipments[reference_distance_km]
        )
    )
```

```dax
High severity issues =
    CALCULATE ( COUNTROWS ( shipment_issues ), shipment_issues[severity] = "High" )

Flagged routes = COUNTROWS ( route_metrics )   -- CSV option only
```

**Important:** every analytical measure filters `quality_status = "clean"`. The exception visuals
use `shipment_issues` instead. Mixing the two would reintroduce the records that failed validation.

---

## 4. Page layout - single page, 16:9

Canvas: 1280 x 720. Background white, no page-level filters.

### Row 1 - KPI cards (height 110 px)

| Card | Measure | Display |
| --- | --- | --- |
| Shipments analysed | `[Clean shipments]` | whole number |
| Volume moved (litres) | `[Volume moved (L)]` | `#,##0` |
| Avg transport cost (ZMW) | `[Avg transport cost]` | `#,##0` |
| Data quality issues | `[Data quality issues]` | whole number, red text when > 0 |

Add a text box underneath: `408 records received | 86.5% clean | 55 records excluded pending review`
and the synthetic-data disclaimer in italic red.

### Row 2-3 - five visuals

| # | Visual | Field well | Notes |
| --- | --- | --- | --- |
| 1 | Clustered bar chart | Axis: `product`; Values: `[Volume moved (L)]` | Sort descending, data labels on |
| 2 | Clustered bar chart | Axis: `destinations[province]`; Values: `[Volume moved (L)]` | Sort descending |
| 3 | Clustered bar chart | Axis: `destinations[destination_name]`; Values: `[Avg transport cost]` | Top 10 by value, sort descending |
| 4 | Line chart | Axis: `shipments[Week Start]`; Values: `[Avg transport cost]` | Markers on, constant colour |
| 5 | Clustered bar chart | Axis: `shipment_issues[issue]`; Values: `[Data quality issues]` | Sort descending, data labels on |

### Row 4 - tables

| Table | Columns | Notes |
| --- | --- | --- |
| Routes flagged for investigation | `route`, `[Cost per litre-km]`, `% vs network`, `high_cost_anomalies` | Conditional formatting: background colour by `% vs network` |
| Data-quality exceptions | `shipment_id`, `route`, `issue`, `severity`, `detail` | Conditional formatting: `severity` = High -> red, Medium -> amber; sync slicer with the charts |

---

## 5. Formatting standards

- Theme: navy `#1F3864`, accent `#2E75B6`, alert `#C00000`, amber `#FFF2CC`
- Fonts: Segoe UI, 10 pt body, 20 pt KPI values, 18 pt page title
- Axis titles on every visual; no legend for single-series visuals; no gridlines on the cost trend
- Numbers: volumes and costs `#,##0`; cost per litre-km `0.000000`; percentages `+0.0%;-0.0%`

---

## 6. Validation checklist

Before saving, confirm the Power BI numbers match `sql/query_results.md`:

| Check | Expected |
| --- | ---: |
| Total shipments (Option A) | 408 |
| Total shipments (Option B) | 353 |
| Clean shipments | 353 |
| Data quality issues | 55 |
| Volume moved (clean) | 11,562,000 L |
| Distance discrepancies | 17 |
| Flagged routes | 3 |

If any figure differs, the cause is almost always a missing `quality_status = "clean"` filter, a
date column that was not converted from text, or a relationship built on `shipment_id` instead of
`record_id`.

---

## 7. Screenshots to capture

1. Full page with all visuals
2. Exceptions table with conditional formatting
3. Data view of `shipment_issues` showing the severity codes

Save to `docs/screenshots/` as `powerbi_overview.png`, `powerbi_exceptions.png`, `powerbi_dataview.png`.
