-- ============================================================
-- Fuel Transport Data Quality & Analysis - SQLite queries
-- Database: data/warehouse.db  (built by src/load_database.py)
-- All analytical queries exclude records with outstanding
-- data-quality issues (quality_status = 'clean'), except the
-- reconciliation and data-quality queries, which inspect them.
-- ============================================================

-- query: Headline key performance indicators
SELECT
    (SELECT COUNT(*) FROM shipments) AS total_shipments,
    (SELECT COUNT(*) FROM shipments WHERE quality_status = 'clean') AS clean_shipments,
    (SELECT ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM shipments), 1)
       FROM shipments WHERE quality_status = 'clean') AS clean_pct,
    (SELECT CAST(SUM(volume_litres) AS INTEGER)
       FROM shipments WHERE quality_status = 'clean') AS total_volume_litres,
    (SELECT CAST(ROUND(AVG(transport_cost)) AS INTEGER)
       FROM shipments WHERE quality_status = 'clean') AS avg_transport_cost_zmw,
    (SELECT COUNT(*) FROM shipment_issues) AS data_quality_issues;

-- query: Total volume by product
SELECT
    product,
    COUNT(*) AS shipments,
    CAST(SUM(volume_litres) AS INTEGER) AS total_volume_litres,
    ROUND(100.0 * SUM(volume_litres) / SUM(SUM(volume_litres)) OVER (), 1) AS volume_share_pct
FROM shipments
WHERE quality_status = 'clean'
GROUP BY product
ORDER BY total_volume_litres DESC;

-- query: Volume by province
SELECT
    dest.province,
    COUNT(*) AS shipments,
    CAST(SUM(s.volume_litres) AS INTEGER) AS total_volume_litres
FROM shipments s
JOIN destinations dest ON dest.destination_id = s.destination_id
WHERE s.quality_status = 'clean'
GROUP BY dest.province
ORDER BY total_volume_litres DESC;

-- query: Average transport cost by destination
SELECT
    dest.destination_name,
    dest.province,
    COUNT(*) AS shipments,
    CAST(ROUND(AVG(s.transport_cost)) AS INTEGER) AS avg_transport_cost_zmw,
    ROUND(AVG(s.transport_cost / s.volume_litres), 3) AS avg_cost_per_litre
FROM shipments s
JOIN destinations dest ON dest.destination_id = s.destination_id
WHERE s.quality_status = 'clean'
GROUP BY dest.destination_name, dest.province
ORDER BY avg_transport_cost_zmw DESC
LIMIT 10;

-- query: Monthly volume and cost trend
SELECT
    strftime('%Y-%m', s.shipment_date) AS month,
    COUNT(*) AS shipments,
    CAST(SUM(s.volume_litres) AS INTEGER) AS total_volume_litres,
    CAST(ROUND(AVG(s.transport_cost)) AS INTEGER) AS avg_transport_cost_zmw,
    ROUND(AVG(s.transport_cost / (s.volume_litres * s.reference_distance_km)), 6)
        AS avg_cost_per_litre_km
FROM shipments s
WHERE s.quality_status = 'clean'
GROUP BY month
ORDER BY month;

-- query: Suspicious distance claims
SELECT
    s.record_id,
    s.shipment_id,
    s.shipment_date,
    c.company_name,
    dep.depot_name || ' -> ' || dest.destination_name AS route,
    s.reference_distance_km,
    s.claimed_distance_km,
    ABS(s.claimed_distance_km - s.reference_distance_km) AS difference_km,
    s.transport_cost
FROM shipments s
JOIN companies c ON c.company_id = s.company_id
JOIN depots dep ON dep.depot_id = s.depot_id
JOIN destinations dest ON dest.destination_id = s.destination_id
WHERE ABS(s.claimed_distance_km - s.reference_distance_km) > 20
ORDER BY difference_km DESC;

-- query: Data-quality issues by category
SELECT
    i.issue,
    i.severity,
    COUNT(*) AS occurrences,
    COUNT(DISTINCT i.record_id) AS records_affected
FROM shipment_issues i
GROUP BY i.issue, i.severity
ORDER BY occurrences DESC, i.issue;

-- query: Highest cost per litre-km routes
SELECT
    dep.depot_name || ' -> ' || dest.destination_name AS route,
    r.reference_distance_km,
    COUNT(*) AS shipments,
    ROUND(SUM(s.transport_cost) / SUM(s.volume_litres), 3) AS cost_per_litre,
    ROUND(SUM(s.transport_cost) / SUM(s.volume_litres * s.reference_distance_km), 6)
        AS cost_per_litre_km
FROM shipments s
JOIN depots dep ON dep.depot_id = s.depot_id
JOIN destinations dest ON dest.destination_id = s.destination_id
JOIN routes r ON r.depot_id = s.depot_id AND r.destination_id = s.destination_id
WHERE s.quality_status = 'clean'
GROUP BY dep.depot_name, dest.destination_name, r.reference_distance_km
ORDER BY cost_per_litre_km DESC
LIMIT 10;

-- query: Data-quality exceptions by company
SELECT
    c.company_name,
    COUNT(DISTINCT i.record_id) AS records_affected,
    COUNT(*) AS issues,
    SUM(CASE WHEN i.severity = 'High' THEN 1 ELSE 0 END) AS high_severity_issues
FROM shipment_issues i
JOIN shipments s ON s.record_id = i.record_id
JOIN companies c ON c.company_id = s.company_id
GROUP BY c.company_name
ORDER BY high_severity_issues DESC, issues DESC;
