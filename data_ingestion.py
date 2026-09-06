"""
data_ingestion.py
==================
Day 1, Task 3: Load all provided CSV datasets, profile each one, and note
anomalies.

Design note: rather than hardcode the names of "10 provided CSV datasets"
(which weren't available when this script was written), this script
auto-discovers every *.csv file under data/raw/ and profiles it generically.
Drop the real 10 files into data/raw/ and run this script as-is -- no
filename changes needed.

For each file it prints/logs:
    - .shape
    - .dtypes
    - .head()
    - anomaly flags: null counts, duplicate rows, all-null columns,
      constant columns, mixed-type columns, negative values in columns
      that look monetary/quantity, unparseable date-like columns,
      whitespace-only strings

Usage:
    python src/data_ingestion.py --rawdir data/raw --report reports/day1_ingestion_report.md
"""
import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("data_ingestion")

# Column-name substrings that suggest a value should never be negative
MONEY_QTY_HINTS = ["amount", "nav", "aum", "price", "value", "units", "quantity", "revenue", "expense_ratio"]
# Column-name substrings that suggest the column holds a date, even if dtype is object
DATE_HINTS = ["date", "_dt", "timestamp"]


def profile_dataframe(name: str, df: pd.DataFrame) -> dict:
    anomalies = []

    # Shape / dtypes / head -- required by the task spec
    print(f"\n{'=' * 90}\n{name}\n{'=' * 90}")
    print(f"shape: {df.shape}")
    print("dtypes:")
    print(df.dtypes)
    print("head():")
    print(df.head())

    # --- Nulls ---
    null_counts = df.isnull().sum()
    cols_with_nulls = null_counts[null_counts > 0]
    if not cols_with_nulls.empty:
        anomalies.append(f"Null values in {len(cols_with_nulls)} column(s): "
                          + ", ".join(f"{c} ({n})" for c, n in cols_with_nulls.items()))

    all_null_cols = null_counts[null_counts == len(df)].index.tolist()
    if all_null_cols:
        anomalies.append(f"Entirely-null column(s): {all_null_cols}")

    # --- Duplicates ---
    dup_count = df.duplicated().sum()
    if dup_count:
        anomalies.append(f"{dup_count} fully duplicate row(s)")

    # --- Constant columns (zero variance -- likely a data issue or a dead field) ---
    constant_cols = [c for c in df.columns if df[c].nunique(dropna=True) <= 1]
    if constant_cols:
        anomalies.append(f"Constant (single-value or empty) column(s): {constant_cols}")

    # --- Mixed-type object columns (e.g. a numeric column with stray text) ---
    for c in df.select_dtypes(include=["object", "string"]).columns:
        sample = df[c].dropna()
        if sample.empty:
            continue
        types_seen = sample.map(lambda v: type(v).__name__).unique()
        if len(types_seen) > 1:
            anomalies.append(f"Column '{c}' has mixed Python types: {list(types_seen)}")
        # whitespace-only strings
        if sample.astype(str).str.strip().eq("").any():
            anomalies.append(f"Column '{c}' contains whitespace-only/empty string values")

    # --- Negative values in monetary/quantity-like columns ---
    for c in df.select_dtypes(include=[np.number]).columns:
        if any(hint in c.lower() for hint in MONEY_QTY_HINTS):
            n_neg = (df[c] < 0).sum()
            if n_neg:
                anomalies.append(f"Column '{c}' (money/qty-like) has {n_neg} negative value(s)")

    # --- Date-like columns that don't parse cleanly ---
    for c in df.columns:
        if any(hint in c.lower() for hint in DATE_HINTS) and not pd.api.types.is_numeric_dtype(df[c]) \
                and not pd.api.types.is_datetime64_any_dtype(df[c]):
            parsed = pd.to_datetime(df[c], errors="coerce")
            n_bad = parsed.isna().sum() - df[c].isna().sum()
            if n_bad > 0:
                anomalies.append(f"Column '{c}' looks like a date but {n_bad} value(s) fail to parse")

    if anomalies:
        print("ANOMALIES FLAGGED:")
        for a in anomalies:
            print(f"  - {a}")
    else:
        print("No anomalies flagged.")

    return {
        "file": name,
        "rows": df.shape[0],
        "columns": df.shape[1],
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rawdir", type=Path, default=Path("data/raw"))
    parser.add_argument("--report", type=Path, default=Path("reports/day1_ingestion_report.md"))
    args = parser.parse_args()

    csv_files = sorted(args.rawdir.glob("*.csv"))
    if not csv_files:
        log.error(
            f"No CSV files found in {args.rawdir}. Place the 10 provided datasets there "
            f"(any filenames) and re-run -- this script auto-discovers every *.csv."
        )
        return

    log.info(f"Found {len(csv_files)} CSV file(s) in {args.rawdir}: {[p.name for p in csv_files]}")

    summaries = []
    for path in csv_files:
        try:
            df = pd.read_csv(path)
        except Exception as e:
            log.error(f"Failed to load {path.name}: {e}")
            summaries.append({"file": path.name, "rows": None, "columns": None,
                               "anomaly_count": None, "anomalies": [f"FAILED TO LOAD: {e}"]})
            continue
        summaries.append(profile_dataframe(path.name, df))

    # --- Write a markdown summary report ---
    args.report.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Day 1 — Data Ingestion Report\n",
             f"**Files discovered:** {len(csv_files)} in `{args.rawdir}`\n",
             "| File | Rows | Columns | Anomalies Flagged |",
             "|---|---|---|---|"]
    for s in summaries:
        lines.append(f"| {s['file']} | {s['rows']} | {s['columns']} | {s['anomaly_count']} |")
    lines.append("\n## Anomaly detail\n")
    for s in summaries:
        if s["anomalies"]:
            lines.append(f"### {s['file']}")
            for a in s["anomalies"]:
                lines.append(f"- {a}")
            lines.append("")
    args.report.write_text("\n".join(lines))
    log.info(f"Report saved: {args.report}")

    total_anomalies = sum(s["anomaly_count"] or 0 for s in summaries)
    log.info(f"Ingestion complete: {len(csv_files)} files, {total_anomalies} total anomalies flagged.")


if __name__ == "__main__":
    main()
