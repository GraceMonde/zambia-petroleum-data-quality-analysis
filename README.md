# Zambia Petroleum Transport - Data Quality & Analysis

A small, end-to-end data analysis project: generate a synthetic petroleum transport dataset, clean
and validate it, reconcile claims against reference distances, load it into a SQL database, analyse
route costs, and present the results in a dashboard.

**Objective** - to demonstrate data cleaning, validation, reconciliation, anomaly detection, SQL
analysis and dashboard development using a synthetic petroleum transportation dataset.

> **Important:** this is a **portfolio/synthetic dataset**. Every record is fictional and generated
> by `src/generate_data.py`. Nothing here represents ERB data, an actual UPP calculation, or real
> company performance.

Full write-up - why this project was chosen, how it was built, what it found and why the findings
matter: [`docs/project_report.md`](docs/project_report.md).

---

## Results at a glance

| Measure | Value |
| --- | ---: |
| Records received | 408 |
| Clean records after validation | 353 (86.5%) |
| Clean volume moved | 11,562,000 L |
| Issues raised | 55 across 6 categories |
| Routes assessed | 26 |
| Routes flagged for further investigation | 3 |
| Network cost per litre-km | 0.004431 ZMW |

### Data quality findings

| Check | Records | Severity |
| --- | ---: | --- |
| Distance discrepancy (claimed vs reference > 20 km) | 17 | High |
| Missing claimed distance | 11 | High |
| High-cost anomaly (cost/litre-km > Q3 + 3 x IQR) | 9 | Medium |
| Duplicate record | 8 | Medium |
| Missing company or depot | 6 | High |
| Invalid volume (zero, negative or non-numeric) | 4 | High |

Resolved automatically during cleaning: 26 product names standardised (`diesel` / `DIESEL` /
`Diesel`), 3 thousand-separator values reformatted, 8 duplicate rows removed from the analysis set.

### Key findings

1. **353 of 408 records (86.5%) were usable after cleaning**; 55 issues were raised across 6
   categories, led by distance discrepancies (17) and missing claimed distances (11).
2. **3 routes were flagged for further investigation**: Lusaka -> Chipata (+13.9% vs network cost
   per litre-km), Livingstone -> Kazungula (+12.1%), and Lusaka -> Kitwe (2 high-cost anomalies on
   the same route).
3. **Distance claims diverge from reference distances in both directions** - 7 records claimed a
   longer journey and 10 a shorter one, with a maximum gap of 90 km on Ndola -> Solwezi.
4. **Demand is concentrated**: Petrol and Diesel account for 77.0% of clean volume, and the
   Copperbelt is the largest destination province (26.4% of volume).
5. **Cost intensity rose after July**: average transport cost per shipment moved from ZMW 36,494
   (2026-07) to a peak of ZMW 41,750 (2026-08) and closed at ZMW 40,810 (2026-09), while clean
   volume fell 15.8% between August and September.

Full write-up: [`reports/analytical_summary.md`](reports/analytical_summary.md).
Records are **flagged for investigation**, never described as fraudulent or incorrect.

---

## Pipeline

```text
src/generate_data.py     synthetic raw data with 8 deliberate defect types
        |
        v
src/data_cleaning.py     standardise -> coerce -> validate -> flag -> clean set
        |                outputs: cleaned_data, processed_data, issues_flagged,
        |                         data_quality_report.md
        v
src/load_database.py     dimensional schema in SQLite (companies, depots,
        |                destinations, routes, shipments, shipment_issues)
        v
src/run_queries.py       executes sql/analysis_queries.sql -> sql/query_results.md
        |
        v
src/analysis.py          route cost-per-litre-km review + analytical summary
        |
        v
dashboard/build_dashboard.py   Excel dashboard (KPIs, 5 charts, exception register)
```

Rebuild everything from a clean checkout:

```bash
pip install -r requirements.txt

python src/generate_data.py
python src/data_cleaning.py
python src/load_database.py
python src/run_queries.py
python src/analysis.py
python dashboard/build_dashboard.py

python tests/verify_project.py   # 87 assertions against the rebuilt outputs
```

Requires **Python 3.11+**. The dataset is seeded (`SEED = 42`), so every run reproduces the same
408 records and the same 55 issues. `tests/verify_project.py` exits non-zero if any assumption has
drifted.

---

## Repository structure

```text
README.md
requirements.txt
data/
  raw_data.csv             408 records as generated, defects included
  processed_data.csv       all 408 records standardised, with quality_status
  cleaned_data.csv         353 analysis-ready records
  issues_flagged.csv       55 exceptions with severity and detail
  route_metrics.csv        26 routes with cost metrics and flags
  warehouse.db             SQLite database
src/
  generate_data.py         synthetic dataset generator (seeded)
  data_cleaning.py         cleaning, validation, data quality report
  load_database.py         builds the SQLite schema and loads it
  run_queries.py           runs the SQL file and writes the results
  analysis.py              route cost analysis and analytical summary
sql/
  analysis_queries.sql     9 queries (KPIs, trends, reconciliation, ranking)
  query_results.md         executed queries with their results
dashboard/
  build_dashboard.py       generates the Excel dashboard
  ERB_transport_dashboard.xlsx
  powerbi_build_spec.md    step-by-step Power BI build specification
reports/
  data_quality_report.md   validation counts, rules and thresholds
  analytical_summary.md    one-page analytical write-up
docs/
  project_report.md         full project report: why, how, results, why they matter
  guide.txt                project brief
  screenshots/             dashboard captures (see below)
tests/
  verify_project.py        87 automated checks over every output
```

---

## SQL

`sql/analysis_queries.sql` runs against `data/warehouse.db` and covers: headline KPIs, volume by
product, volume by province, average cost by destination, monthly trend, distance reconciliation,
issues by category, highest cost-per-litre-km routes, and exceptions by company. Results:
[`sql/query_results.md`](sql/query_results.md).

Example - reconciling claimed against reference distances:

```sql
SELECT s.shipment_id, dep.depot_name, dest.destination_name,
       s.reference_distance_km, s.claimed_distance_km,
       ABS(s.claimed_distance_km - s.reference_distance_km) AS difference_km
FROM shipments s
JOIN depots dep ON dep.depot_id = s.depot_id
JOIN destinations dest ON dest.destination_id = s.destination_id
WHERE ABS(s.claimed_distance_km - s.reference_distance_km) > 20
ORDER BY difference_km DESC;
```

---

## Dashboard

`dashboard/ERB_transport_dashboard.xlsx` (generated) contains four KPI cards, five visuals
(volume by product, volume by region, average cost by destination, cost trend over time, issues by
category), the flagged-routes block and the full 55-row exception register with severity colouring.

`dashboard/powerbi_build_spec.md` is the equivalent specification for building the same page in
Power BI Desktop - data model, DAX measures, visual field wells and a validation checklist that
must reconcile to `sql/query_results.md`.

---

## Screenshots

Capture these into `docs/screenshots/` (names match `powerbi_build_spec.md` section 7):

| File | What to capture |
| --- | --- |
| `dashboard_overview.png` | Excel dashboard - KPI row and all five charts |
| `dashboard_exceptions.png` | Excel dashboard - exception register with severity colours |
| `powerbi_overview.png` | Power BI report page (if the `.pbix` is built) |
| `powerbi_exceptions.png` | Power BI exceptions table with conditional formatting |

---

## How this maps to the Data Analyst role

| Requirement | Evidence in this project |
| --- | --- |
| Collect, clean and validate data | `src/data_cleaning.py`, `reports/data_quality_report.md` |
| Maintain regional datasets | `data/processed_data.csv`, SQLite dimensions, province rollups |
| Reconcile datasets | claimed vs reference distance, 17 discrepancies in `sql/query_results.md` |
| Identify duplicates | 8 duplicates detected and excluded |
| Identify anomalies and inconsistencies | distance tolerance, IQR cost threshold, missing/invalid values |
| Analyse trends | monthly and weekly trend queries and charts |
| Prepare reports and dashboards | Excel dashboard, `sql/query_results.md`, analytical summary |
| SQL | `data/warehouse.db` + 9 queries |
| Python | generator, cleaning, loader, analysis, dashboard builder |
| Petroleum data context | synthetic fuel movements by depot, product, route |
| Evidence-based decisions | 3 routes flagged for investigation with stated rules |
| Data confidentiality | fully synthetic data, clearly labelled everywhere |

---

## Note on scope

Deliberately **not** included: a web application, an API, machine learning, a UPP calculator, or a
large dataset. The point is a correct, documented, reproducible workflow - not volume.
