"""
clean_investor_transactions.py
===============================
Task 2: Clean investor_transactions.csv

Steps (per spec):
  1. Standardise transaction_type values (SIP / Lumpsum / Redemption)
  2. Validate amount > 0
  3. Fix date formats
  4. Check KYC status enum values

Expected input columns (adjust EXPECTED_COLUMNS below once the real file
is available -- this is the schema assumed from the task brief):
    transaction_id, amfi_code, investor_id, date, transaction_type, amount,
    units, kyc_status, state, channel

Usage:
    python scripts/clean_investor_transactions.py \
        --input data/raw/investor_transactions.csv \
        --output data/processed/investor_transactions_clean.csv
"""
import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("clean_investor_transactions")

EXPECTED_COLUMNS = ["amfi_code", "date", "transaction_type", "amount", "kyc_status"]

# --- Standardisation maps -----------------------------------------------
# Real-world exports are inconsistent (case, abbreviations, synonyms).
# Extend these maps as soon as the real file's raw values are known --
# run `df['transaction_type'].value_counts()` / `df['kyc_status'].value_counts()`
# on the raw file first and add any unmapped values here.
TRANSACTION_TYPE_MAP = {
    "sip": "SIP",
    "systematic investment plan": "SIP",
    "lumpsum": "Lumpsum",
    "lump sum": "Lumpsum",
    "one time": "Lumpsum",
    "onetime": "Lumpsum",
    "purchase": "Lumpsum",
    "redemption": "Redemption",
    "redeem": "Redemption",
    "withdrawal": "Redemption",
}
VALID_TRANSACTION_TYPES = {"SIP", "Lumpsum", "Redemption"}

KYC_STATUS_MAP = {
    "verified": "Verified",
    "kyc verified": "Verified",
    "complete": "Verified",
    "completed": "Verified",
    "pending": "Pending",
    "in progress": "Pending",
    "rejected": "Rejected",
    "failed": "Rejected",
    "not initiated": "Not Initiated",
    "not started": "Not Initiated",
    "na": "Not Initiated",
}
VALID_KYC_STATUSES = {"Verified", "Pending", "Rejected", "Not Initiated"}


def load(input_path: Path) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    missing = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(
            f"investor_transactions.csv is missing expected column(s): {sorted(missing)}. "
            f"Found columns: {list(df.columns)}. Update EXPECTED_COLUMNS in this "
            f"script once you've seen the real file's headers."
        )
    log.info(f"Loaded {len(df):,} raw rows, {df.shape[1]} columns from {input_path}")
    return df


def standardise_enum(series: pd.Series, mapping: dict, valid_values: set, col_name: str) -> pd.Series:
    original = series.astype(str).str.strip()
    lowered = original.str.lower()
    mapped = lowered.map(mapping)
    # Anything already in the valid set (correct case) passes through unchanged
    already_valid = original.where(original.isin(valid_values))
    result = mapped.fillna(already_valid)
    unmapped_mask = result.isna()
    if unmapped_mask.any():
        bad_values = sorted(original[unmapped_mask].unique())
        log.warning(
            f"{unmapped_mask.sum()} rows have a {col_name} value not covered by the "
            f"standardisation map: {bad_values}. Add these to the mapping once confirmed "
            f"with the source system; flagging as 'Unknown' for now."
        )
        result = result.fillna("Unknown")
    return result


def clean(df: pd.DataFrame) -> pd.DataFrame:
    report = {}
    df = df.copy()

    # --- amfi_code as text ---
    df["amfi_code"] = df["amfi_code"].astype(str).str.strip()

    # --- 3. Fix date formats ---
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=False)
    n_bad_dates = df["date"].isna().sum()
    if n_bad_dates:
        log.warning(f"{n_bad_dates} rows had unparseable dates and were dropped.")
        df = df.dropna(subset=["date"])
    report["unparseable_dates_dropped"] = int(n_bad_dates)

    # --- 1. Standardise transaction_type ---
    df["transaction_type"] = standardise_enum(
        df["transaction_type"], TRANSACTION_TYPE_MAP, VALID_TRANSACTION_TYPES, "transaction_type"
    )
    n_unknown_type = (df["transaction_type"] == "Unknown").sum()
    if n_unknown_type:
        log.warning(f"Dropping {n_unknown_type} rows with unresolvable transaction_type.")
        df = df[df["transaction_type"] != "Unknown"]
    report["unresolvable_transaction_type_dropped"] = int(n_unknown_type)

    # --- 4. Check KYC status enum values ---
    df["kyc_status"] = standardise_enum(
        df["kyc_status"], KYC_STATUS_MAP, VALID_KYC_STATUSES, "kyc_status"
    )
    # KYC rows that map to "Unknown" are kept (not dropped) but flagged, since a
    # transaction record shouldn't be discarded just because KYC metadata is odd --
    # only the KYC field itself is suspect.
    n_unknown_kyc = (df["kyc_status"] == "Unknown").sum()
    report["kyc_status_unresolved_flagged"] = int(n_unknown_kyc)

    # --- 2. Validate amount > 0 ---
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    n_invalid_amount = ((df["amount"] <= 0) | df["amount"].isna()).sum()
    if n_invalid_amount:
        log.warning(f"Dropping {n_invalid_amount} rows with amount <= 0 or non-numeric.")
        df = df[(df["amount"] > 0) & df["amount"].notna()]
    report["invalid_amount_dropped"] = int(n_invalid_amount)

    # --- Remove exact duplicate transactions ---
    n_before = len(df)
    dedup_cols = [c for c in ["source_transaction_id"] if c in df.columns] or list(df.columns)
    df = df.drop_duplicates(subset=dedup_cols, keep="last")
    report["duplicates_removed"] = int(n_before - len(df))

    df = df.sort_values(["amfi_code", "date"]).reset_index(drop=True)

    log.info(f"Clean rows: {len(df):,}")
    log.info(f"Cleaning report: {report}")
    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw/investor_transactions.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/investor_transactions_clean.csv"))
    args = parser.parse_args()

    if not args.input.exists():
        log.error(
            f"Input file not found: {args.input}\n"
            f"Place the real investor_transactions.csv in data/raw/ and re-run this script."
        )
        sys.exit(1)

    df = load(args.input)
    df_clean = clean(df)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(args.output, index=False)
    log.info(f"Saved cleaned file: {args.output} ({len(df_clean):,} rows)")


if __name__ == "__main__":
    main()
