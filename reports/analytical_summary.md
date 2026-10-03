# Analytical Summary

**Question:** Which routes require further investigation?

All calculations use the 353 clean records (`data/cleaned_data.csv`); records with outstanding data-quality issues are held in `data/issues_flagged.csv` and reviewed separately. Cost per litre-km is normalised on the **reference** distance so that disputed claims cannot distort the comparison.

## Method

1. Cost per litre = transport cost / volume.
2. Cost per litre-km = transport cost / (volume x reference distance).
3. Route values are compared with the network average of **0.004431 ZMW per litre-km**.
4. A route is **flagged for further investigation** if either:
   - its cost per litre-km is **10% or more** above the network average, or
   - it carries **2 or more** high-cost anomaly records (repeat exceptions, not one-off variance).

## Routes flagged

| Route | Shipments | Volume (L) | Cost/litre (ZMW) | Cost/litre-km | Vs network | Anomalies | Reason |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Lusaka -> Chipata | 16 | 520,000 | 1.842 | 0.005046 | +13.9% | 0 | cost per litre-km 13.9% above network average |
| Livingstone -> Kazungula | 4 | 140,000 | 0.397 | 0.004966 | +12.1% | 0 | cost per litre-km 12.1% above network average |
| Lusaka -> Kitwe | 11 | 328,000 | 1.466 | 0.004250 | -4.1% | 2 | 2 high-cost anomalies on this route |

Routes assessed: **26** - full table in `data/route_metrics.csv`.

## Network position

| Metric | Value |
| --- | ---: |
| Network cost per litre-km | 0.004431 ZMW |
| Network cost per litre | 1.213 ZMW |
| Clean volume moved | 11,562,000 L |
| Clean shipments | 353 |
| Product leader | Petrol (40.3% of volume) |
| Busiest month by volume | 2026-08 (4,208,000 L) |
| Highest average monthly cost | 2026-08 (ZMW 41,750) |

## Data-quality context

| Measure | Value |
| --- | ---: |
| Records read | 408 |
| Clean records | 353 (86.5%) |
| Issues raised | 55 across 6 categories |
| Distance discrepancies | 17 (7 claimed longer than reference, 10 shorter) |
| Largest single distance gap | 90 km (Ndola -> Solwezi) |
| Indicative exposure on overstated claims | ZMW 49,530 |

> The exposure figure is an order-of-magnitude estimate: the additional claimed
> distance valued at the network average rate on the recorded volumes. It is
> presented for verification against supporting documentation, not as a loss.

## Findings

1. **353 of 408 records (86.5%) were usable after cleaning**; 55 issues were raised across 6 categories, led by distance discrepancies (17) and missing claimed distances (11).
2. **3 routes were flagged for further investigation**: Lusaka -> Chipata (cost per litre-km 13.9% above network average); Livingstone -> Kazungula (cost per litre-km 12.1% above network average); Lusaka -> Kitwe (2 high-cost anomalies on this route).
3. **Distance claims diverge from reference distances on both sides** - 7 records claimed a longer journey and 10 a shorter one, with a maximum gap of 90 km (Ndola -> Solwezi).
4. **Demand is concentrated**: Petrol and Diesel account for 77.0% of clean volume, and Copperbelt is the largest destination province (26.4% of volume).
5. **Cost intensity rose after 2026-07**: average transport cost per shipment moved from ZMW 36,494 (2026-07) to a peak of ZMW 41,750 (2026-08) and closed the period at ZMW 40,810 (2026-09), while clean volume fell 15.8% between 2026-08 and 2026-09.
