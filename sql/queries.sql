-- ============================================================================
-- BLUESTOCK MUTUAL FUND ANALYTICS — ANALYTICAL QUERIES
-- Database: SQLite (bluestock_mf.db)
-- Run with: sqlite3 bluestock_mf.db < sql/queries.sql
-- All queries are written against the star schema (dim_fund, dim_date,
-- fact_nav, fact_transactions, fact_performance, fact_aum) defined in
-- sql/schema.sql.
-- ============================================================================

-- ============================================================================
-- Query 1: Top 5 funds by AUM (latest available snapshot per fund)
-- ============================================================================
WITH latest_aum AS (
    SELECT fund_id, aum_cr, date_id,
           ROW_NUMBER() OVER (PARTITION BY fund_id ORDER BY date_id DESC) AS rn
    FROM fact_aum
)
SELECT
    f.amfi_code,
    f.fund_name,
    f.fund_house,
    la.aum_cr,
    d.full_date AS as_on_date
FROM latest_aum la
JOIN dim_fund f ON f.fund_id = la.fund_id
JOIN dim_date d ON d.date_id = la.date_id
WHERE la.rn = 1
ORDER BY la.aum_cr DESC
LIMIT 5;

-- ============================================================================
-- Query 2: Average NAV per month, per fund
-- ============================================================================
SELECT
    f.amfi_code,
    f.fund_name,
    d.year,
    d.month,
    d.month_name,
    ROUND(AVG(n.nav), 4) AS avg_nav,
    COUNT(*) AS trading_days_counted
FROM fact_nav n
JOIN dim_fund f ON f.fund_id = n.fund_id
JOIN dim_date d ON d.date_id = n.date_id
GROUP BY f.amfi_code, f.fund_name, d.year, d.month, d.month_name
ORDER BY f.amfi_code, d.year, d.month;

-- ============================================================================
-- Query 3: SIP Year-over-Year (YoY) growth, overall
-- ============================================================================
WITH sip_by_year AS (
    SELECT d.year, SUM(t.amount) AS sip_amount
    FROM fact_transactions t
    JOIN dim_date d ON d.date_id = t.date_id
    WHERE t.transaction_type = 'SIP'
    GROUP BY d.year
)
SELECT
    year,
    sip_amount,
    LAG(sip_amount) OVER (ORDER BY year) AS prior_year_sip_amount,
    ROUND(
        100.0 * (sip_amount - LAG(sip_amount) OVER (ORDER BY year))
        / NULLIF(LAG(sip_amount) OVER (ORDER BY year), 0)
    , 2) AS yoy_growth_pct
FROM sip_by_year
ORDER BY year;

-- ============================================================================
-- Query 4: Transactions by state
-- ============================================================================
SELECT
    COALESCE(t.state, 'Unknown') AS state,
    COUNT(*) AS transaction_count,
    ROUND(SUM(t.amount), 2) AS total_amount,
    ROUND(AVG(t.amount), 2) AS avg_amount,
    COUNT(DISTINCT t.fund_id) AS distinct_funds_invested_in
FROM fact_transactions t
GROUP BY COALESCE(t.state, 'Unknown')
ORDER BY total_amount DESC;

-- ============================================================================
-- Query 5: Funds with expense_ratio < 1% (latest snapshot per fund)
-- ============================================================================
WITH latest_perf AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY fund_id ORDER BY date_id DESC) AS rn
    FROM fact_performance
)
SELECT
    f.amfi_code,
    f.fund_name,
    f.category,
    lp.expense_ratio,
    lp.return_1y,
    lp.return_3y
FROM latest_perf lp
JOIN dim_fund f ON f.fund_id = lp.fund_id
WHERE lp.rn = 1 AND lp.expense_ratio < 1.0
ORDER BY lp.expense_ratio ASC;

-- ============================================================================
-- Query 6: Top 10 funds by 1-year return (latest snapshot, excluding flagged anomalies)
-- ============================================================================
WITH latest_perf AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY fund_id ORDER BY date_id DESC) AS rn
    FROM fact_performance
)
SELECT
    f.amfi_code,
    f.fund_name,
    f.category,
    lp.return_1y,
    lp.expense_ratio
FROM latest_perf lp
JOIN dim_fund f ON f.fund_id = lp.fund_id
WHERE lp.rn = 1 AND lp.is_anomaly = 0 AND lp.return_1y IS NOT NULL
ORDER BY lp.return_1y DESC
LIMIT 10;

-- ============================================================================
-- Query 7: SIP vs Lumpsum vs Redemption — monthly volume trend
-- ============================================================================
SELECT
    d.year,
    d.month,
    d.month_name,
    t.transaction_type,
    COUNT(*) AS transaction_count,
    ROUND(SUM(t.amount), 2) AS total_amount
FROM fact_transactions t
JOIN dim_date d ON d.date_id = t.date_id
GROUP BY d.year, d.month, d.month_name, t.transaction_type
ORDER BY d.year, d.month, t.transaction_type;

-- ============================================================================
-- Query 8: KYC status breakdown and its relationship to transaction value
-- ============================================================================
SELECT
    t.kyc_status,
    COUNT(*) AS transaction_count,
    ROUND(SUM(t.amount), 2) AS total_amount,
    ROUND(AVG(t.amount), 2) AS avg_amount,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM fact_transactions), 2) AS pct_of_all_transactions
FROM fact_transactions t
GROUP BY t.kyc_status
ORDER BY total_amount DESC;

-- ============================================================================
-- Query 9: Fund category performance leaderboard (avg return_1y and avg expense_ratio by category)
-- ============================================================================
WITH latest_perf AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY fund_id ORDER BY date_id DESC) AS rn
    FROM fact_performance
)
SELECT
    f.category,
    COUNT(DISTINCT f.fund_id) AS fund_count,
    ROUND(AVG(lp.return_1y), 2) AS avg_return_1y,
    ROUND(AVG(lp.return_3y), 2) AS avg_return_3y,
    ROUND(AVG(lp.expense_ratio), 3) AS avg_expense_ratio
FROM latest_perf lp
JOIN dim_fund f ON f.fund_id = lp.fund_id
WHERE lp.rn = 1
GROUP BY f.category
ORDER BY avg_return_1y DESC;

-- ============================================================================
-- Query 10: NAV volatility ranking (std dev of daily nav_change_pct per fund,
--           over the trailing 90 days of loaded data) -- a simple risk proxy
-- ============================================================================
WITH recent_nav AS (
    SELECT n.fund_id, n.nav_change_pct
    FROM fact_nav n
    JOIN dim_date d ON d.date_id = n.date_id
    WHERE d.date_id >= (
        SELECT CAST(strftime('%Y%m%d', date(MAX(full_date), '-90 days')) AS INTEGER)
        FROM dim_date
    )
    AND n.nav_change_pct IS NOT NULL
)
SELECT
    f.amfi_code,
    f.fund_name,
    f.category,
    COUNT(*) AS days_counted,
    ROUND(AVG(rn.nav_change_pct), 4) AS avg_daily_change_pct,
    -- SQLite has no native STDDEV; compute it manually via the definition
    ROUND(
        SQRT(
            SUM((rn.nav_change_pct - sub.avg_change) * (rn.nav_change_pct - sub.avg_change)) / COUNT(*)
        ), 4
    ) AS stddev_daily_change_pct
FROM recent_nav rn
JOIN dim_fund f ON f.fund_id = rn.fund_id
JOIN (
    SELECT fund_id, AVG(nav_change_pct) AS avg_change
    FROM recent_nav
    GROUP BY fund_id
) sub ON sub.fund_id = rn.fund_id
GROUP BY f.amfi_code, f.fund_name, f.category
ORDER BY stddev_daily_change_pct DESC
LIMIT 20;

-- ============================================================================
-- END OF QUERIES
-- ============================================================================
