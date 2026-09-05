"""
generate_data_quality_report.py
================================
Produces data/processed/data_quality_report.csv -- a one-row-per-source-file
summary of what the cleaning step changed, for the data dictionary / handover
notes. Recomputed independently from the raw vs. cleaned files rather than
parsed out of log output, so it stays accurate even if the clean_*.py scripts
are edited later.

Usage:
    python scripts/generate_data_quality_report.py \
        --rawdir data/raw --cleandir data/processed --out data/processed/data_quality_report.csv
"""
import argparse
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("data_quality_report")

SOURCES = [
    ("nav_history", "nav_history.csv", "nav_history_clean.csv"),
    ("investor_transactions", "investor_transactions.csv", "investor_transactions_clean.csv"),
    ("scheme_performance", "scheme_performance.csv", "scheme_performance_clean.csv"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rawdir", type=Path, default=Path("data/raw"))
    parser.add_argument("--cleandir", type=Path, default=Path("data/processed"))
    parser.add_argument("--out", type=Path, default=Path("data/processed/data_quality_report.csv"))
    args = parser.parse_args()

    rows = []
    for name, raw_file, clean_file in SOURCES:
        raw_path = args.rawdir / raw_file
        clean_path = args.cleandir / clean_file
        if not raw_path.exists() or not clean_path.exists():
            log.warning(f"Skipping {name}: missing {raw_path if not raw_path.exists() else clean_path}")
            continue
        raw = pd.read_csv(raw_path)
        clean = pd.read_csv(clean_path)
        rows.append({
            "source_file": raw_file,
            "cleaned_file": clean_file,
            "raw_row_count": len(raw),
            "raw_column_count": raw.shape[1],
            "raw_null_cells": int(raw.isnull().sum().sum()),
            "raw_duplicate_rows": int(raw.duplicated().sum()),
            "cleaned_row_count": len(clean),
            "cleaned_column_count": clean.shape[1],
            "cleaned_null_cells": int(clean.isnull().sum().sum()),
            "rows_dropped": len(raw) - len(clean) if len(raw) >= len(clean) else 0,
            "rows_added_by_ffill_reindex": max(0, len(clean) - len(raw)),
        })

    report = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.out, index=False)
    log.info(f"Saved data quality report: {args.out} ({len(report)} source files summarised)")
    if not report.empty:
        print(report.to_string(index=False))


if __name__ == "__main__":
    main()
