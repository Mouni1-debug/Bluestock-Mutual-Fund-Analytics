"""
clean_scheme_performance.py
=============================
Task 3: Clean scheme_performance.csv

Steps (per spec):
  1. Validate all return values are numeric
  2. Flag anomalies
  3. Check expense_ratio range (0.1% - 2.5%)

Expected input columns (adjust EXPECTED_COLUMNS below once the real file
is available -- this is the schema assumed from the task brief):
    amfi_code, date, return_1m, return_3m, return_6m, return_1y, return_3y,
    return_5y, return_since_inception, expense_ratio

Usage:
    python scripts/clean_scheme_performance.py \
        --input data/raw/scheme_performance.csv \
        --output data/processed/scheme_performance_clean.csv
"""
import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("clean_scheme_performance")

EXPECTED_COLUMNS = ["amfi_code", "date", "expense_ratio"]
RETURN_COLUMNS = [
    "return_1m", "return_3m", "return_6m", "return_1y", "return_3y",
    "return_5y", "return_since_inception",
]

# Sanity bounds used only to *flag* anomalies -- rows are NOT dropped, since a
# genuinely extreme return (e.g. a sector fund in a boom/bust year) is real
# data, not necessarily an error. A human reviewer should look at flagged rows.
RETURN_ANOMALY_BOUNDS = (-90.0, 500.0)   # % return outside this range gets flagged
EXPENSE_RATIO_MIN, EXPENSE_RATIO_MAX = 0.1, 2.5  # per spec, in percent


def load(input_path: Path) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    missing = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(
            f"scheme_performance.csv is missing expected column(s): {sorted(missing)}. "
            f"Found columns: {list(df.columns)}. Update EXPECTED_COLUMNS in this "
            f"script once you've seen the real file's headers."
        )
    present_return_cols = [c for c in RETURN_COLUMNS if c in df.columns]
    if not present_return_cols:
        log.warning(
            "None of the expected return_* columns were found. Update RETURN_COLUMNS "
            "in this script to match the real file's column names."
        )
    log.info(f"Loaded {len(df):,} raw rows, {df.shape[1]} columns from {input_path}")
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    report = {}
    df = df.copy()

    df["amfi_code"] = df["amfi_code"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=False)
    n_bad_dates = df["date"].isna().sum()
    if n_bad_dates:
        log.warning(f"{n_bad_dates} rows had unparseable dates and were dropped.")
        df = df.dropna(subset=["date"])
    report["unparseable_dates_dropped"] = int(n_bad_dates)

    present_return_cols = [c for c in RETURN_COLUMNS if c in df.columns]

    # --- 1. Validate all return values are numeric ---
    non_numeric_counts = {}
    for col in present_return_cols:
        before_na = df[col].isna().sum()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        after_na = df[col].isna().sum()
        newly_non_numeric = after_na - before_na
        if newly_non_numeric > 0:
            non_numeric_counts[col] = int(newly_non_numeric)
    report["non_numeric_return_values_coerced_to_null"] = non_numeric_counts

    # --- 3. Check expense_ratio range (0.1% - 2.5%) ---
    df["expense_ratio"] = pd.to_numeric(df["expense_ratio"], errors="coerce")
    er_out_of_range = ~df["expense_ratio"].between(EXPENSE_RATIO_MIN, EXPENSE_RATIO_MAX) & df["expense_ratio"].notna()
    report["expense_ratio_out_of_range_flagged"] = int(er_out_of_range.sum())

    # --- 2. Flag anomalies (returns outside sane bounds, or expense_ratio out of range) ---
    anomaly_mask = er_out_of_range.copy()
    anomaly_reason = pd.Series([""] * len(df), index=df.index)
    anomaly_reason.loc[er_out_of_range] += "expense_ratio_out_of_range;"

    lo, hi = RETURN_ANOMALY_BOUNDS
    for col in present_return_cols:
        out_of_bounds = ~df[col].between(lo, hi) & df[col].notna()
        anomaly_mask |= out_of_bounds
        anomaly_reason.loc[out_of_bounds] += f"{col}_out_of_bounds;"

    df["is_anomaly"] = anomaly_mask.astype(int)
    df["anomaly_reason"] = anomaly_reason.str.rstrip(";")
    report["total_rows_flagged_as_anomaly"] = int(anomaly_mask.sum())

    # Rows are KEPT even when flagged -- anomalies are surfaced for review
    # (fact_performance.is_anomaly / anomaly_reason), not silently dropped,
    # since an out-of-range value might reflect a genuine outlier fund rather
    # than bad data.

    # --- Remove exact duplicate (amfi_code, date) snapshots ---
    n_before = len(df)
    df = df.drop_duplicates(subset=["amfi_code", "date"], keep="last")
    report["duplicates_removed"] = int(n_before - len(df))

    df = df.sort_values(["amfi_code", "date"]).reset_index(drop=True)

    log.info(f"Clean rows: {len(df):,}")
    log.info(f"Cleaning report: {report}")
    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw/scheme_performance.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/scheme_performance_clean.csv"))
    args = parser.parse_args()

    if not args.input.exists():
        log.error(
            f"Input file not found: {args.input}\n"
            f"Place the real scheme_performance.csv in data/raw/ and re-run this script."
        )
        sys.exit(1)

    df = load(args.input)
    df_clean = clean(df)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(args.output, index=False)
    log.info(f"Saved cleaned file: {args.output} ({len(df_clean):,} rows)")


if __name__ == "__main__":
    main()
