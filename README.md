# Bluestock Mutual Fund Analytics — Day 2

**Status:** Pipeline scaffold complete and tested against sample data. **Waiting on the 3 real source CSVs** (`nav_history.csv`, `investor_transactions.csv`, `scheme_performance.csv`) before a real load — see `docs/data_dictionary.md` for the exact status of each deliverable.

---

## What's in this repo

```
bluestock_mf/
├── data/
│   ├── raw/                 # <- place the 3 real source CSVs here
│   └── processed/           # <- pipeline outputs land here (currently empty)
├── scripts/
│   ├── clean_nav_history.py
│   ├── clean_investor_transactions.py
│   ├── clean_scheme_performance.py
│   ├── build_dimensions.py          # builds dim_fund.csv, dim_date.csv
│   ├── build_facts.py               # builds fact_nav/transactions/performance/aum.csv
│   ├── generate_data_quality_report.py
│   └── load_to_sqlite.py            # SQLAlchemy loader + row-count verification
├── sql/
│   ├── schema.sql            # star schema DDL (dim_fund, dim_date, fact_*)
│   └── queries.sql           # 10 analytical queries
├── docs/
│   └── data_dictionary.md
├── bluestock_mf.db            # SQLite DB — schema created, 0 rows loaded yet
├── requirements.txt
└── README.md
```

## Why no data yet

The 3 raw CSVs for this task weren't supplied, so rather than fabricate numbers that would need to be thrown away, every script, the schema, and the queries were built and syntax/logic-tested against representative sample data, then left ready to run the moment the real files arrive. Nothing here needs to change structurally — you only need to drop the 3 files into `data/raw/` and run the pipeline below.

## How to run the full pipeline (once the 3 CSVs are in `data/raw/`)

```bash
pip install -r requirements.txt

# 1-3: clean each source file
python scripts/clean_nav_history.py
python scripts/clean_investor_transactions.py
python scripts/clean_scheme_performance.py

# 4: build the dimension tables
python scripts/build_dimensions.py

# 5: build the fact tables (surrogate-keyed, joined to dims)
python scripts/build_facts.py

# 6: data quality summary (optional but recommended)
python scripts/generate_data_quality_report.py

# 7: load everything into SQLite (recreates schema fresh, then loads + verifies row counts)
python scripts/load_to_sqlite.py --init-schema

# 8: run the analytical queries
sqlite3 bluestock_mf.db < sql/queries.sql
```

Each `clean_*.py` script validates the real file's column headers against an `EXPECTED_COLUMNS` list at the top of the file and fails with a clear error message (naming exactly which columns are missing) if the real file's schema differs from what was assumed in this scaffold — update that list and re-run.

## Column assumptions made in this scaffold

Since the real files weren't available, each cleaning script assumes:
- **nav_history.csv:** `amfi_code, date, nav`
- **investor_transactions.csv:** `amfi_code, date, transaction_type, amount, kyc_status` (+ optional `state, channel, investor_id, units, source_transaction_id`)
- **scheme_performance.csv:** `amfi_code, date, expense_ratio` (+ optional `return_1m ... return_since_inception`)

See `docs/data_dictionary.md` §1 for the full column-by-column breakdown and business definitions.

## Verifying the schema independently of real data

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('bluestock_mf.db')
print([r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")])
"
```

## Git

```
git log --oneline
```
See the "Day 2: Cleaned data + SQLite DB loaded" commit for this scaffold. Note the commit captures the **pipeline** (schema + scripts + queries + docs), not real loaded data, since the source CSVs weren't supplied — the commit message will need a small follow-up commit once real data is loaded (e.g. "Day 2b: Loaded real source data, N rows verified").
