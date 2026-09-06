"""
build_facts.py
===============
Joins the 3 cleaned source files against dim_fund/dim_date to produce the
surrogate-keyed fact table CSVs ready for loading into SQLite.

Produces:
    fact_nav.csv           <- nav_history_clean.csv
    fact_transactions.csv  <- investor_transactions_clean.csv
    fact_performance.csv   <- scheme_performance_clean.csv
    fact_aum.csv           <- empty shell (no AUM source file in this batch;
                               see docs/data_dictionary.md note on fact_aum)

Usage:
    python scripts/build_facts.py --indir data/processed --outdir data/processed
"""
import argparse
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("build_facts")


def to_date_id(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series).dt.strftime("%Y%m%d").astype(int)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indir", type=Path, default=Path("data/processed"))
    parser.add_argument("--outdir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    dim_fund = pd.read_csv(args.indir / "dim_fund.csv")[["fund_id", "amfi_code"]]
    dim_fund["amfi_code"] = dim_fund["amfi_code"].astype(str)

    # --- fact_nav ---
    nav = pd.read_csv(args.indir / "nav_history_clean.csv", parse_dates=["date"])
    nav["amfi_code"] = nav["amfi_code"].astype(str)
    nav = nav.merge(dim_fund, on="amfi_code", how="left")
    n_unmatched = nav["fund_id"].isna().sum()
    if n_unmatched:
        log.warning(f"fact_nav: {n_unmatched} rows had no matching fund_id in dim_fund -- dropped.")
        nav = nav.dropna(subset=["fund_id"])
    nav["date_id"] = to_date_id(nav["date"])
    fact_nav = nav[["fund_id", "date_id", "nav", "is_forward_filled", "nav_change", "nav_change_pct"]].copy()
    fact_nav["fund_id"] = fact_nav["fund_id"].astype(int)
    fact_nav.to_csv(args.outdir / "fact_nav.csv", index=False)
    log.info(f"fact_nav.csv           : {len(fact_nav):,} rows")

    # --- fact_transactions ---
    txn = pd.read_csv(args.indir / "investor_transactions_clean.csv", parse_dates=["date"])
    txn["amfi_code"] = txn["amfi_code"].astype(str)
    txn = txn.merge(dim_fund, on="amfi_code", how="left")
    n_unmatched = txn["fund_id"].isna().sum()
    if n_unmatched:
        log.warning(f"fact_transactions: {n_unmatched} rows had no matching fund_id in dim_fund -- dropped.")
        txn = txn.dropna(subset=["fund_id"])
    txn["date_id"] = to_date_id(txn["date"])
    keep_cols = ["fund_id", "date_id", "transaction_type", "amount", "kyc_status"]
    for optional in ["source_transaction_id", "investor_id", "units", "state", "channel"]:
        if optional in txn.columns:
            keep_cols.append(optional)
        else:
            txn[optional] = pd.NA
            keep_cols.append(optional)
    fact_transactions = txn[keep_cols].copy()
    fact_transactions["fund_id"] = fact_transactions["fund_id"].astype(int)
    fact_transactions.to_csv(args.outdir / "fact_transactions.csv", index=False)
    log.info(f"fact_transactions.csv  : {len(fact_transactions):,} rows")

    # --- fact_performance ---
    perf = pd.read_csv(args.indir / "scheme_performance_clean.csv", parse_dates=["date"])
    perf["amfi_code"] = perf["amfi_code"].astype(str)
    perf = perf.merge(dim_fund, on="amfi_code", how="left")
    n_unmatched = perf["fund_id"].isna().sum()
    if n_unmatched:
        log.warning(f"fact_performance: {n_unmatched} rows had no matching fund_id in dim_fund -- dropped.")
        perf = perf.dropna(subset=["fund_id"])
    perf["date_id"] = to_date_id(perf["date"])
    return_cols = [c for c in [
        "return_1m", "return_3m", "return_6m", "return_1y", "return_3y",
        "return_5y", "return_since_inception",
    ] if c in perf.columns]
    keep_cols = ["fund_id", "date_id"] + return_cols + ["expense_ratio", "is_anomaly", "anomaly_reason"]
    fact_performance = perf[keep_cols].copy()
    fact_performance["fund_id"] = fact_performance["fund_id"].astype(int)
    fact_performance.to_csv(args.outdir / "fact_performance.csv", index=False)
    log.info(f"fact_performance.csv   : {len(fact_performance):,} rows")

    # --- fact_aum (empty shell -- no AUM source file provided in this batch) ---
    fact_aum = pd.DataFrame(columns=["fund_id", "date_id", "aum_cr"])
    fact_aum.to_csv(args.outdir / "fact_aum.csv", index=False)
    log.info("fact_aum.csv           : 0 rows (no AUM source file in this batch -- see data_dictionary.md)")


if __name__ == "__main__":
    main()
