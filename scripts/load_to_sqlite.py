"""
load_to_sqlite.py
==================
Loads all cleaned/dimension/fact CSVs into bluestock_mf.db using SQLAlchemy's
create_engine + DataFrame.to_sql(), then verifies that the row count loaded
into each table matches the row count of its source CSV exactly.

Load order matters (dims before facts, so foreign keys resolve):
    dim_fund -> dim_date -> fact_nav -> fact_transactions
    -> fact_performance -> fact_aum

The star-schema tables (dim_*/fact_*) must already exist -- run
`sqlite3 bluestock_mf.db < sql/schema.sql` (or the --init-schema flag below)
before this script, since to_sql(if_exists="append") relies on the
CHECK/FOREIGN KEY constraints already being in place.

Usage:
    python scripts/load_to_sqlite.py --init-schema
"""
import argparse
import logging
import subprocess
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("load_to_sqlite")

# (table_name, source_csv, if_exists_mode)
# Star-schema tables use "append" since schema.sql already created them with
# their PRIMARY KEY / FOREIGN KEY / CHECK constraints -- to_sql(if_exists="replace")
# would silently drop those constraints.
LOAD_PLAN = [
    ("dim_fund", "dim_fund.csv"),
    ("dim_date", "dim_date.csv"),
    ("fact_nav", "fact_nav.csv"),
    ("fact_transactions", "fact_transactions.csv"),
    ("fact_performance", "fact_performance.csv"),
    ("fact_aum", "fact_aum.csv"),
]

# Also load the 3 cleaned "flat" source files as their own tables, for anyone
# who wants to query the pre-star-schema cleaned data directly.
STAGING_LOAD_PLAN = [
    ("stg_nav_history", "nav_history_clean.csv"),
    ("stg_investor_transactions", "investor_transactions_clean.csv"),
    ("stg_scheme_performance", "scheme_performance_clean.csv"),
]


def init_schema(db_path: Path, schema_path: Path):
    log.info(f"Initialising schema from {schema_path} into {db_path} ...")
    sql_text = schema_path.read_text()
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql_text)
        conn.commit()
    finally:
        conn.close()
    log.info("Schema initialised.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("bluestock_mf.db"))
    parser.add_argument("--datadir", type=Path, default=Path("data/processed"))
    parser.add_argument("--schema", type=Path, default=Path("sql/schema.sql"))
    parser.add_argument("--init-schema", action="store_true",
                         help="Run sql/schema.sql against the DB before loading (fresh/clean load).")
    parser.add_argument("--include-staging", action="store_true", default=True,
                         help="Also load the 3 cleaned flat CSVs as stg_* tables.")
    args = parser.parse_args()

    if args.init_schema:
        init_schema(args.db, args.schema)

    engine = create_engine(f"sqlite:///{args.db}")

    verification = []

    def load_table(table_name: str, csv_name: str, if_exists: str):
        csv_path = args.datadir / csv_name
        if not csv_path.exists():
            log.error(f"Missing CSV for {table_name}: {csv_path}")
            sys.exit(1)
        df = pd.read_csv(csv_path)
        with engine.begin() as conn:
            df.to_sql(table_name, conn, if_exists=if_exists, index=False)
            loaded_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
        match = "OK" if loaded_count == len(df) else "MISMATCH"
        verification.append({
            "table": table_name, "source_csv": csv_name,
            "csv_rows": len(df), "loaded_rows": loaded_count, "status": match,
        })
        log.info(f"{table_name:<28} <- {csv_name:<32} csv_rows={len(df):<8} loaded_rows={loaded_count:<8} [{match}]")
        if match != "OK":
            log.error(f"ROW COUNT MISMATCH for {table_name}: csv had {len(df)}, DB has {loaded_count}")

    # dims/facts append into schema.sql's pre-created tables (keeps constraints)
    for table_name, csv_name in LOAD_PLAN:
        load_table(table_name, csv_name, if_exists="append")

    # staging flat tables can be freely replaced (no constraints to preserve)
    if args.include_staging:
        for table_name, csv_name in STAGING_LOAD_PLAN:
            load_table(table_name, csv_name, if_exists="replace")

    report = pd.DataFrame(verification)
    print("\n" + "=" * 78)
    print("ROW COUNT VERIFICATION")
    print("=" * 78)
    print(report.to_string(index=False))
    print("=" * 78)

    if (report["status"] != "OK").any():
        log.error("One or more tables failed row-count verification. See table above.")
        sys.exit(1)
    log.info("All tables verified: loaded row counts match source CSV row counts exactly.")


if __name__ == "__main__":
    main()
