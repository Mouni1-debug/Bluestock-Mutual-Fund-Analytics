# Data Dictionary — Bluestock Mutual Fund Analytics

**Database:** `bluestock_mf.db` (SQLite) · **Schema:** `sql/schema.sql` · **Status:** Scaffold complete, pending real source data

> ⚠️ **Note on current status:** The 3 raw source files (`nav_history.csv`,
> `investor_transactions.csv`, `scheme_performance.csv`) had not been supplied
> as of this document's creation. Every table, column, and constraint below is
> fully built and tested against representative sample data, but the tables in
> `bluestock_mf.db` contain **0 real rows** until the actual CSVs are placed in
> `data/raw/` and the pipeline (`scripts/clean_*.py` → `scripts/build_dimensions.py`
> → `scripts/build_facts.py` → `scripts/load_to_sqlite.py`) is run. See `README.md`
> for the exact commands.

---

## 1. Source Files (raw, as received)

### 1.1 `nav_history.csv`
Daily Net Asset Value (NAV) per mutual fund scheme.

| Column | Type (raw) | Business Definition | Notes |
|---|---|---|---|
| `amfi_code` | string/int | AMFI-assigned unique scheme code (natural key for a fund) | Cast to text on load to preserve leading zeros |
| `date` | string | Calendar date the NAV was published | Multiple formats tolerated; parsed with `pandas.to_datetime` |
| `nav` | float | Net Asset Value per unit, in ₹ | Must be > 0; invalid/missing values are forward-filled from the prior valid trading day, per fund |

**Source/Provenance:** AMFI (Association of Mutual Funds in India) daily NAV disclosure, or equivalent internal feed. *(To be confirmed once the real file is supplied — update this line with the actual origin, e.g. "AMFI NAVAll.txt daily download" or "internal data warehouse export.")*

### 1.2 `investor_transactions.csv`
Individual investor transaction log (SIP/Lumpsum/Redemption).

| Column | Type (raw) | Business Definition | Notes |
|---|---|---|---|
| `amfi_code` | string/int | Scheme the transaction was made against | FK to `dim_fund` after load |
| `date` | string | Transaction date | Parsed to ISO 8601 |
| `transaction_type` | string | SIP / Lumpsum / Redemption | Standardised via a synonym map (e.g. "lump sum", "purchase" → "Lumpsum") — see `scripts/clean_investor_transactions.py` |
| `amount` | float | Transaction amount, in ₹ | Must be > 0 |
| `kyc_status` | string | Investor's KYC (Know Your Customer) verification status | Standardised to one of: Verified / Pending / Rejected / Not Initiated |
| `investor_id` | string | Investor/folio reference | Kept as a degenerate dimension on `fact_transactions` (no separate `dim_investor` in this batch) |
| `state` | string | Investor's state (for geographic analysis) | Used in the "transactions by state" query |
| `channel` | string | How the transaction was placed (e.g. Direct, Broker, App) | Optional — kept if present in source |
| `units` | float | Number of fund units transacted | Optional |

**Source/Provenance:** Internal transaction processing system / RTA (Registrar & Transfer Agent, e.g. CAMS/KFintech) export. *(To be confirmed.)*

### 1.3 `scheme_performance.csv`
Periodic performance snapshot per scheme.

| Column | Type (raw) | Business Definition | Notes |
|---|---|---|---|
| `amfi_code` | string/int | Scheme code | FK to `dim_fund` after load |
| `date` | string | As-of date of this performance snapshot | |
| `return_1m` … `return_since_inception` | float | Trailing returns (%) over the named period | All coerced to numeric; non-numeric values become null, not dropped |
| `expense_ratio` | float | Total Expense Ratio (TER), % | Valid range per business rule: **0.1% – 2.5%**; values outside this range are *flagged*, not deleted (see `is_anomaly`) |

**Source/Provenance:** AMFI / AMC (Asset Management Company) factsheet disclosure. *(To be confirmed.)*

---

## 2. Cleaned Files (`data/processed/*_clean.csv`)

Same columns as the raw files above, plus:

| Column | Added by | Meaning |
|---|---|---|
| `is_forward_filled` (nav_history_clean.csv) | `clean_nav_history.py` | 1 if this day's NAV was carried forward from the last valid trading day (holiday/weekend/gap), 0 if it was an original reported value |
| `nav_change`, `nav_change_pct` (nav_history_clean.csv) | `clean_nav_history.py` | Day-over-day NAV change, absolute and % — used in Query 10 (volatility) |
| `is_anomaly`, `anomaly_reason` (scheme_performance_clean.csv) | `clean_scheme_performance.py` | Flags rows where a return value or `expense_ratio` fell outside its sanity range; reason is a semicolon-joined list of which field(s) triggered it |

---

## 3. Star Schema Tables (`bluestock_mf.db`)

### 3.1 `dim_fund` — one row per mutual fund scheme
| Column | Type | Key | Business Definition |
|---|---|---|---|
| `fund_id` | INTEGER | **PK** | Surrogate key |
| `amfi_code` | TEXT | Natural key (UNIQUE) | AMFI scheme code |
| `fund_name` | TEXT | | Scheme name |
| `fund_house` | TEXT | | Asset Management Company (AMC) name |
| `category` | TEXT | | Equity / Debt / Hybrid / Solution Oriented / Other |
| `sub_category` | TEXT | | e.g. Large Cap, Liquid, ELSS |
| `plan_type` | TEXT | | Direct / Regular |
| `option_type` | TEXT | | Growth / IDCW (Dividend) |
| `benchmark_index` | TEXT | | Index the scheme is benchmarked against |
| `launch_date` | TEXT | | Scheme inception date, ISO 8601 |
| `is_active` | INTEGER | | 1 = active, 0 = closed/merged scheme |

### 3.2 `dim_date` — one row per calendar day
| Column | Type | Key | Business Definition |
|---|---|---|---|
| `date_id` | INTEGER | **PK** | Surrogate key, `YYYYMMDD` integer (e.g. `20260115`) — chosen over SQLite's native TEXT date type for cheap sort/filter/range performance |
| `full_date` | TEXT | UNIQUE | ISO 8601 date |
| `day`, `month`, `year`, `quarter` | INTEGER | | Calendar parts |
| `month_name`, `day_of_week` | TEXT | | Display labels |
| `financial_year` | TEXT | | Indian FY convention, e.g. `FY2025-26` (Apr–Mar) |
| `is_weekend` | INTEGER | | 1 = Saturday/Sunday |
| `is_month_end` | INTEGER | | 1 = last calendar day of the month |
| `is_trading_holiday` | INTEGER | | 1 = flagged NSE/BSE non-trading day (placeholder — overlay a real holiday calendar once available) |

### 3.3 `fact_nav` — grain: one row per (fund, date)
| Column | Type | Key | Business Definition |
|---|---|---|---|
| `nav_id` | INTEGER | **PK** | Surrogate key |
| `fund_id` | INTEGER | **FK** → `dim_fund` | |
| `date_id` | INTEGER | **FK** → `dim_date` | |
| `nav` | REAL | | NAV per unit, ₹; `CHECK (nav > 0)` |
| `is_forward_filled` | INTEGER | | See §2 |
| `nav_change`, `nav_change_pct` | REAL | | See §2 |

`UNIQUE(fund_id, date_id)` enforces the one-row-per-fund-per-day grain.

### 3.4 `fact_transactions` — grain: one row per investor transaction
| Column | Type | Key | Business Definition |
|---|---|---|---|
| `transaction_id` | INTEGER | **PK** | Surrogate key |
| `source_transaction_id` | TEXT | UNIQUE (nullable) | Original transaction ID from the source system, if present |
| `fund_id` | INTEGER | **FK** → `dim_fund` | |
| `date_id` | INTEGER | **FK** → `dim_date` | |
| `investor_id` | TEXT | | Degenerate dimension — investor/folio reference |
| `transaction_type` | TEXT | | `CHECK IN ('SIP','Lumpsum','Redemption')` |
| `amount` | REAL | | ₹; `CHECK (amount > 0)` |
| `units` | REAL | | Fund units transacted |
| `kyc_status` | TEXT | | `CHECK IN ('Verified','Pending','Rejected','Not Initiated')` |
| `state` | TEXT | | Investor's state |
| `channel` | TEXT | | Transaction channel |

### 3.5 `fact_performance` — grain: one row per (fund, as-of date) performance snapshot
| Column | Type | Key | Business Definition |
|---|---|---|---|
| `performance_id` | INTEGER | **PK** | Surrogate key |
| `fund_id` | INTEGER | **FK** → `dim_fund` | |
| `date_id` | INTEGER | **FK** → `dim_date` | |
| `return_1m` … `return_since_inception` | REAL | | Trailing % returns |
| `expense_ratio` | REAL | | Business rule range: [0.1%, 2.5%]. **Deliberately no DB-level CHECK constraint** — out-of-range values are *flagged* via `is_anomaly`/`anomaly_reason` (populated in `clean_scheme_performance.py`) rather than rejected, since the task specifies "flag anomalies," and a genuinely out-of-range expense ratio is a real data point for an analyst to review, not a row that should silently fail to load |
| `is_anomaly`, `anomaly_reason` | INTEGER, TEXT | | See §2 |

`UNIQUE(fund_id, date_id)`.

### 3.6 `fact_aum` — grain: one row per (fund, as-of date) AUM snapshot
| Column | Type | Key | Business Definition |
|---|---|---|---|
| `aum_id` | INTEGER | **PK** | Surrogate key |
| `fund_id` | INTEGER | **FK** → `dim_fund` | |
| `date_id` | INTEGER | **FK** → `dim_date` | |
| `aum_cr` | REAL | | Assets Under Management, ₹ crore; `CHECK (aum_cr >= 0)` |

**⚠️ Status: currently an empty shell (0 rows).** No `aum_*.csv` source file was included in this task's 3 inputs (`nav_history.csv`, `investor_transactions.csv`, `scheme_performance.csv`). The table and its constraints are fully built per the star-schema brief so it's ready the moment an AUM source (e.g. a monthly AMFI AUM disclosure file) is supplied — `scripts/build_facts.py` currently writes it as a 0-row CSV with the correct headers.

---

## 4. Staging Tables (loaded alongside the star schema)

`stg_nav_history`, `stg_investor_transactions`, `stg_scheme_performance` — the 3 cleaned flat files loaded as-is (no star-schema surrogate keys), for anyone who wants to query the cleaned data directly without joining through `dim_fund`/`dim_date`. These are loaded with `if_exists="replace"` since they carry no constraints to protect.

---

## 5. Data Quality Report (`data/processed/data_quality_report.csv`)

One row per source file, generated by `scripts/generate_data_quality_report.py`, recording: raw/cleaned row counts, raw/cleaned null-cell counts, raw duplicate-row count, rows dropped during cleaning, and rows added by the NAV forward-fill/reindex step. Regenerate any time after re-running the cleaning scripts.

---

## 6. Business Rules Enforced

| Rule | Enforced where |
|---|---|
| NAV must be > 0 | `clean_nav_history.py` (drops/forward-fills) **and** `fact_nav.nav CHECK (nav > 0)` |
| Transaction amount must be > 0 | `clean_investor_transactions.py` **and** `fact_transactions.amount CHECK` |
| `transaction_type` ∈ {SIP, Lumpsum, Redemption} | `clean_investor_transactions.py` standardisation map **and** `fact_transactions CHECK` |
| `kyc_status` ∈ {Verified, Pending, Rejected, Not Initiated} | `clean_investor_transactions.py` standardisation map **and** `fact_transactions CHECK` |
| `expense_ratio` ∈ [0.1%, 2.5%] | **Flagged** (not dropped, no hard DB CHECK) in `clean_scheme_performance.py` via `is_anomaly`/`anomaly_reason` — see design note in `sql/schema.sql` |
| No duplicate (fund, date) NAV/performance/AUM rows | `UNIQUE(fund_id, date_id)` on `fact_nav`, `fact_performance`, `fact_aum` |
| One row per transaction | `source_transaction_id UNIQUE` (when present in source) |

---

## 7. Known Gaps / Follow-Ups

1. **Real source files not yet supplied** — every script in `scripts/` validates its expected columns against `EXPECTED_COLUMNS` and fails loudly with a clear message if the real file's headers differ; update those lists on first contact with the real data.
2. **`fact_aum` has no source file in this batch** — see §3.6.
3. **`is_trading_holiday` in `dim_date` is a placeholder (always 0)** — overlay a real NSE/BSE trading holiday calendar once available, so `is_forward_filled` in `fact_nav` can be cross-checked against genuine holidays vs. unexplained data gaps.
4. **`fund_house`, `category`, and other `dim_fund` descriptive attributes** depend entirely on whether the real source files include them — `scripts/build_dimensions.py` pulls whatever is available and falls back to a placeholder fund name if none is found.

---

**Document Status:** Scaffold complete — update the *Provenance* lines in §1 and the *Known Gaps* in §7 once the real CSVs are received.
