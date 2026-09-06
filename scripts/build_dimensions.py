"""
build_dimensions.py
====================
Builds dim_date.csv and dim_fund.csv from the 3 cleaned source files, ready
to be loaded into SQLite alongside the fact tables.

dim_date  : one row per calendar day spanning the min/max date across all
            three cleaned sources (so every fact row has a matching date_id).
dim_fund  : one row per distinct amfi_code seen across all three cleaned
            sources, with whatever descriptive attributes (fund_name,
            fund_house, category, ...) are available from the source data.

Usage:
    python scripts/build_dimensions.py \
        --nav data/processed/nav_history_clean.csv \
        --txn data/processed/investor_transactions_clean.csv \
        --perf data/processed/scheme_performance_clean.csv \
        --outdir data/processed
"""
import argparse
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("build_dimensions")

# Columns that, if present in any of the 3 cleaned source files, describe a
# fund and should be carried into dim_fund. Extend this list once the real
# files' headers are known.
FUND_ATTRIBUTE_COLUMNS = [
    "fund_name", "fund_house", "category", "sub_category",
    "plan_type", "option_type", "benchmark_index", "launch_date",
]


def build_dim_date(min_date: pd.Timestamp, max_date: pd.Timestamp) -> pd.DataFrame:
    dates = pd.date_range(min_date, max_date, freq="D")
    df = pd.DataFrame({"full_date": dates})
    df["date_id"] = df["full_date"].dt.strftime("%Y%m%d").astype(int)
    df["day"] = df["full_date"].dt.day
    df["month"] = df["full_date"].dt.month
    df["month_name"] = df["full_date"].dt.strftime("%B")
    df["quarter"] = df["full_date"].dt.quarter
    df["year"] = df["full_date"].dt.year
    # Indian financial year: Apr(year) - Mar(year+1) => "FY2025-26" style
    fy_start_year = df["year"].where(df["month"] >= 4, df["year"] - 1)
    df["financial_year"] = "FY" + fy_start_year.astype(str).str[-2:] + "-" + (fy_start_year + 1).astype(str).str[-2:]
    df["day_of_week"] = df["full_date"].dt.strftime("%A")
    df["is_weekend"] = df["full_date"].dt.dayofweek.isin([5, 6]).astype(int)
    df["is_month_end"] = df["full_date"].dt.is_month_end.astype(int)
    df["is_trading_holiday"] = 0  # placeholder -- overlay a real NSE/BSE holiday calendar once available
    df["full_date"] = df["full_date"].dt.strftime("%Y-%m-%d")
    return df[[
        "date_id", "full_date", "day", "month", "month_name", "quarter", "year",
        "financial_year", "day_of_week", "is_weekend", "is_month_end", "is_trading_holiday",
    ]]


def build_dim_fund(frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [f.assign(amfi_code=f["amfi_code"].astype(str).str.strip()) for f in frames if "amfi_code" in f.columns]
    all_codes = pd.concat([f[["amfi_code"]] for f in frames], ignore_index=True)
    dim = all_codes.drop_duplicates().reset_index(drop=True)

    # Pull in any descriptive attributes available from any source, first-non-null wins
    for f in frames:
        cols = [c for c in FUND_ATTRIBUTE_COLUMNS if c in f.columns]
        if not cols:
            continue
        attrs = f[["amfi_code"] + cols].drop_duplicates(subset="amfi_code", keep="first")
        dim = dim.merge(attrs, on="amfi_code", how="left", suffixes=("", "_new"))
        for c in cols:
            new_col = f"{c}_new"
            if new_col in dim.columns:
                dim[c] = dim[c].fillna(dim[new_col]) if c in dim.columns else dim[new_col]
                dim = dim.drop(columns=[new_col])

    if "fund_name" not in dim.columns:
        dim["fund_name"] = "Unknown - " + dim["amfi_code"]
        log.warning("No fund_name column found in any source; using placeholder names from amfi_code.")
    else:
        dim["fund_name"] = dim["fund_name"].fillna("Unknown - " + dim["amfi_code"])

    dim["is_active"] = 1
    dim = dim.sort_values("amfi_code").reset_index(drop=True)
    dim.insert(0, "fund_id", range(1, len(dim) + 1))
    return dim


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nav", type=Path, default=Path("data/processed/nav_history_clean.csv"))
    parser.add_argument("--txn", type=Path, default=Path("data/processed/investor_transactions_clean.csv"))
    parser.add_argument("--perf", type=Path, default=Path("data/processed/scheme_performance_clean.csv"))
    parser.add_argument("--outdir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    frames = []
    dates = []
    for path in [args.nav, args.txn, args.perf]:
        if not path.exists():
            log.error(f"Missing cleaned input: {path}. Run the 3 clean_*.py scripts first.")
            raise SystemExit(1)
        df = pd.read_csv(path, parse_dates=["date"])
        frames.append(df)
        dates.append(df["date"])

    all_dates = pd.concat(dates)
    dim_date = build_dim_date(all_dates.min(), all_dates.max())
    dim_fund = build_dim_fund(frames)

    args.outdir.mkdir(parents=True, exist_ok=True)
    dim_date.to_csv(args.outdir / "dim_date.csv", index=False)
    dim_fund.to_csv(args.outdir / "dim_fund.csv", index=False)

    log.info(f"dim_date.csv  : {len(dim_date):,} rows ({dim_date['full_date'].min()} to {dim_date['full_date'].max()})")
    log.info(f"dim_fund.csv  : {len(dim_fund):,} rows ({dim_fund['amfi_code'].nunique():,} unique funds)")


if __name__ == "__main__":
    main()
