-- ============================================================================
-- BLUESTOCK MUTUAL FUND ANALYTICS — STAR SCHEMA
-- Database: SQLite (bluestock_mf.db)
-- Grain of each fact table is documented above its CREATE TABLE statement.
-- Run with: sqlite3 bluestock_mf.db < sql/schema.sql
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ============================================================================
-- DROP (safe re-run during development)
-- ============================================================================
DROP TABLE IF EXISTS fact_aum;
DROP TABLE IF EXISTS fact_performance;
DROP TABLE IF EXISTS fact_transactions;
DROP TABLE IF EXISTS fact_nav;
DROP TABLE IF EXISTS dim_fund;
DROP TABLE IF EXISTS dim_date;

-- ============================================================================
-- DIM_FUND
-- One row per mutual fund scheme (identified by its unique AMFI code).
-- Source: derived from the distinct amfi_code / fund attributes present
--         across nav_history.csv, investor_transactions.csv and
--         scheme_performance.csv.
-- ============================================================================
CREATE TABLE dim_fund (
    fund_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code           TEXT NOT NULL UNIQUE,          -- AMFI scheme code, natural/business key
    fund_name           TEXT NOT NULL,
    fund_house          TEXT,                          -- AMC name, e.g. "HDFC Mutual Fund"
    category            TEXT,                          -- Equity / Debt / Hybrid / Solution Oriented / Other
    sub_category        TEXT,                          -- e.g. Large Cap, Liquid, ELSS
    plan_type           TEXT,                          -- Direct / Regular
    option_type         TEXT,                          -- Growth / IDCW (Dividend)
    benchmark_index     TEXT,
    launch_date         TEXT,                          -- ISO 8601 (YYYY-MM-DD)
    is_active           INTEGER NOT NULL DEFAULT 1,    -- 1 = active, 0 = closed/merged
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_dim_fund_category ON dim_fund(category);
CREATE INDEX idx_dim_fund_house ON dim_fund(fund_house);

-- ============================================================================
-- DIM_DATE
-- One row per calendar date spanned by the source data. Pre-populate with a
-- date-range generator (see scripts/build_dimensions.py) rather than relying
-- on SQLite's limited native date functions for reporting.
-- ============================================================================
CREATE TABLE dim_date (
    date_id             INTEGER PRIMARY KEY,            -- YYYYMMDD integer surrogate key, e.g. 20260115
    full_date            TEXT NOT NULL UNIQUE,          -- ISO 8601 (YYYY-MM-DD)
    day                  INTEGER NOT NULL,
    month                INTEGER NOT NULL,
    month_name           TEXT NOT NULL,
    quarter              INTEGER NOT NULL,
    year                 INTEGER NOT NULL,
    financial_year       TEXT NOT NULL,                 -- Indian FY, e.g. "FY2025-26"
    day_of_week          TEXT NOT NULL,                 -- Monday .. Sunday
    is_weekend           INTEGER NOT NULL,              -- 1 = Sat/Sun
    is_month_end         INTEGER NOT NULL,
    is_trading_holiday    INTEGER NOT NULL DEFAULT 0     -- 1 if flagged as a non-trading day (NSE/BSE holiday)
);

CREATE INDEX idx_dim_date_year_month ON dim_date(year, month);

-- ============================================================================
-- FACT_NAV
-- Grain: one row per (fund, date) — the fund's NAV on that calendar date.
-- Source: nav_history.csv (after cleaning: sorted, deduplicated, forward-filled
--         for holidays/weekends, NAV > 0 validated).
-- ============================================================================
CREATE TABLE fact_nav (
    nav_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id             INTEGER NOT NULL,
    date_id             INTEGER NOT NULL,
    nav                 REAL NOT NULL CHECK (nav > 0),
    is_forward_filled   INTEGER NOT NULL DEFAULT 0,     -- 1 if this NAV was carried forward from the prior trading day
    nav_change          REAL,                            -- nav - previous trading day's nav
    nav_change_pct      REAL,                            -- (nav_change / previous nav) * 100
    FOREIGN KEY (fund_id) REFERENCES dim_fund(fund_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    UNIQUE (fund_id, date_id)
);

CREATE INDEX idx_fact_nav_fund ON fact_nav(fund_id);
CREATE INDEX idx_fact_nav_date ON fact_nav(date_id);

-- ============================================================================
-- FACT_TRANSACTIONS
-- Grain: one row per individual investor transaction.
-- Source: investor_transactions.csv (after cleaning: standardised
--         transaction_type, amount > 0 validated, KYC enum checked).
-- ============================================================================
CREATE TABLE fact_transactions (
    transaction_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    source_transaction_id TEXT UNIQUE,                  -- original transaction id/reference from the source file, if present
    fund_id             INTEGER NOT NULL,
    date_id             INTEGER NOT NULL,
    investor_id         TEXT,                            -- investor / folio reference (degenerate dimension)
    transaction_type    TEXT NOT NULL CHECK (transaction_type IN ('SIP','Lumpsum','Redemption')),
    amount              REAL NOT NULL CHECK (amount > 0),
    units               REAL,
    kyc_status          TEXT NOT NULL CHECK (kyc_status IN ('Verified','Pending','Rejected','Not Initiated')),
    state               TEXT,                            -- investor's state, for the "transactions by state" query
    channel             TEXT,                             -- e.g. Direct, MFU, Broker, App (kept if present in source)
    FOREIGN KEY (fund_id) REFERENCES dim_fund(fund_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
);

CREATE INDEX idx_fact_txn_fund ON fact_transactions(fund_id);
CREATE INDEX idx_fact_txn_date ON fact_transactions(date_id);
CREATE INDEX idx_fact_txn_type ON fact_transactions(transaction_type);
CREATE INDEX idx_fact_txn_state ON fact_transactions(state);

-- ============================================================================
-- FACT_PERFORMANCE
-- Grain: one row per (fund, as-of date) performance snapshot.
-- Source: scheme_performance.csv (after cleaning: numeric validation on all
--         return columns, anomaly flagging, expense_ratio range check
--         0.1%-2.5%).
-- ============================================================================
CREATE TABLE fact_performance (
    performance_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id             INTEGER NOT NULL,
    date_id             INTEGER NOT NULL,                 -- as-of date of this performance snapshot
    return_1m           REAL,
    return_3m           REAL,
    return_6m           REAL,
    return_1y           REAL,
    return_3y           REAL,
    return_5y           REAL,
    return_since_inception REAL,
    expense_ratio       REAL,                              -- % ; business rule range is 0.1-2.5, enforced as a FLAG not a hard reject (see is_anomaly) -- a real fund with an out-of-range TER is a data point to review, not a row to silently lose
    is_anomaly          INTEGER NOT NULL DEFAULT 0,       -- 1 if any return/expense value failed a sanity check
    anomaly_reason       TEXT,
    FOREIGN KEY (fund_id) REFERENCES dim_fund(fund_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    UNIQUE (fund_id, date_id)
);

CREATE INDEX idx_fact_perf_fund ON fact_performance(fund_id);
CREATE INDEX idx_fact_perf_date ON fact_performance(date_id);
CREATE INDEX idx_fact_perf_anomaly ON fact_performance(is_anomaly);

-- ============================================================================
-- FACT_AUM
-- Grain: one row per (fund, as-of date) Assets Under Management snapshot.
-- Source: derived — AUM is typically published alongside scheme performance
--         data (e.g. a monthly AMFI AUM disclosure) rather than transaction
--         data; kept as its own fact table per the star-schema brief so it
--         can be sourced independently (e.g. a future aum_history.csv).
-- ============================================================================
CREATE TABLE fact_aum (
    aum_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id             INTEGER NOT NULL,
    date_id             INTEGER NOT NULL,
    aum_cr              REAL NOT NULL CHECK (aum_cr >= 0),  -- AUM in INR crores
    FOREIGN KEY (fund_id) REFERENCES dim_fund(fund_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    UNIQUE (fund_id, date_id)
);

CREATE INDEX idx_fact_aum_fund ON fact_aum(fund_id);
CREATE INDEX idx_fact_aum_date ON fact_aum(date_id);

-- ============================================================================
-- NOTES
-- ============================================================================
-- 1. Surrogate keys (fund_id, date_id, *_id) are used for all facts, with the
--    natural/business keys (amfi_code, full_date) kept as unique attributes.
-- 2. date_id uses the YYYYMMDD integer convention so it sorts/filters cheaply
--    without needing SQLite's weaker native date parsing.
-- 3. fact_aum is deliberately independent of fact_performance even though AUM
--    often ships in the same file as returns/expense ratio in practice --
--    keeping it separate matches the 4-fact-table brief and lets AUM be
--    reloaded from a different cadence/source without touching performance.
-- 4. Run PRAGMA foreign_key_check; after loading data to catch any orphaned
--    fund_id/date_id values from bad source rows.
-- 5. expense_ratio on fact_performance has NO hard CHECK range constraint,
--    by design: the task's business rule ("check expense_ratio range
--    0.1%-2.5%") is a FLAGGING rule (see is_anomaly/anomaly_reason,
--    populated by scripts/clean_scheme_performance.py), not a hard rejection
--    rule -- a genuinely out-of-range expense ratio is a real data point an
--    analyst should review, not a row that should silently fail to load.
--    fact_nav.nav and fact_transactions.amount DO use hard CHECK (> 0)
--    constraints, since "amount > 0" / "NAV > 0" in the brief are validation
--    rules, not flagging rules.
-- ============================================================================
