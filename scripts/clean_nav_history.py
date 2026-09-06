"""
clean_nav_history.py
=====================
Task 1: Clean nav_history.csv

Steps (per spec):
  1. Parse dates to datetime
  2. Sort by amfi_code + date
  3. Forward-fill missing NAV for holidays/weekends
  4. Remove duplicates
  5. Validate NAV > 0

Expected input columns (adjust EXPECTED_COLUMNS below once the real file
is available -- this is the schema assumed from the task brief):
    amfi_code, date, nav

Usage:
    python scripts/clean_nav_history.py \
        --input data/raw/nav_history.csv \
        --output data/processed/nav_history_clean.csv
"""
import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("clean_nav_history")

EXPECTED_COLUMNS = ["amfi_code", "date", "nav"]


def load(input_path: Path) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    missing = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(
            f"nav_history.csv is missing expected column(s): {sorted(missing)}. "
            f"Found columns: {list(df.columns)}. Update EXPECTED_COLUMNS in this "
            f"script once you've seen the real file's headers."
        )
    log.info(f"Loaded {len(df):,} raw rows, {df.shape[1]} columns from {input_path}")
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    report = {}
    df = df.copy()

    # --- 1. Parse dates to datetime ---
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=False)
    n_bad_dates = df["date"].isna().sum()
    if n_bad_dates:
        log.warning(f"{n_bad_dates} rows had unparseable dates and were dropped.")
        df = df.dropna(subset=["date"])
    report["unparseable_dates_dropped"] = int(n_bad_dates)

    # --- amfi_code should be treated as text, not a numeric type, to preserve
    #     leading zeros / mixed alphanumeric codes ---
    df["amfi_code"] = df["amfi_code"].astype(str).str.strip()

    # --- 4. Remove duplicates (before forward-fill, so we don't fill from a dup) ---
    n_before = len(df)
    df = df.drop_duplicates(subset=["amfi_code", "date"], keep="last")
    n_dupes = n_before - len(df)
    log.info(f"Removed {n_dupes:,} duplicate (amfi_code, date) rows.")
    report["duplicates_removed"] = int(n_dupes)

    # --- 2. Sort by amfi_code + date ---
    df = df.sort_values(["amfi_code", "date"]).reset_index(drop=True)

    # --- 5. Validate NAV > 0 (invalid NAVs are treated as missing, then forward-filled) ---
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    n_invalid_nav = ((df["nav"] <= 0) | df["nav"].isna()).sum()
    df.loc[df["nav"] <= 0, "nav"] = pd.NA
    report["invalid_or_missing_nav_before_fill"] = int(n_invalid_nav)

    # --- 3. Forward-fill missing NAV for holidays/weekends, per fund ---
    # Reindex each fund onto a complete calendar-day range so weekends/holidays
    # that are simply *absent* from the source file also get an explicit,
    # forward-filled row (not just NaNs that happen to already exist).
    filled_frames = []
    for code, g in df.groupby("amfi_code", sort=False):
        g = g.set_index("date").sort_index()
        full_range = pd.date_range(g.index.min(), g.index.max(), freq="D")
        g = g.reindex(full_range)
        g["amfi_code"] = code
        g["is_forward_filled"] = g["nav"].isna()
        g["nav"] = g["nav"].ffill()
        g.index.name = "date"
        filled_frames.append(g.reset_index())
    df = pd.concat(filled_frames, ignore_index=True)

    n_still_missing = df["nav"].isna().sum()
    if n_still_missing:
        log.warning(
            f"{n_still_missing} rows still have no NAV after forward-fill "
            f"(likely the fund's very first record) -- dropping these."
        )
        df = df.dropna(subset=["nav"])
    report["still_missing_after_ffill_dropped"] = int(n_still_missing)

    # Final NAV > 0 assertion
    assert (df["nav"] > 0).all(), "Validation failed: non-positive NAV values remain."

    # --- Derived fields useful downstream (nav_change, nav_change_pct) ---
    df = df.sort_values(["amfi_code", "date"]).reset_index(drop=True)
    df["nav_change"] = df.groupby("amfi_code")["nav"].diff()
    df["nav_change_pct"] = df.groupby("amfi_code")["nav"].pct_change() * 100

    log.info(f"Clean rows: {len(df):,}")
    log.info(f"Cleaning report: {report}")
    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw/nav_history.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/nav_history_clean.csv"))
    args = parser.parse_args()

    if not args.input.exists():
        log.error(
            f"Input file not found: {args.input}\n"
            f"Place the real nav_history.csv in data/raw/ and re-run this script."
        )
        sys.exit(1)

    df = load(args.input)
    df_clean = clean(df)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(args.output, index=False)
    log.info(f"Saved cleaned file: {args.output} ({len(df_clean):,} rows)")


if __name__ == "__main__":
    main()
