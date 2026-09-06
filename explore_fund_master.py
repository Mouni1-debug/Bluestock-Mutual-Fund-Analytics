"""
explore_fund_master.py
=======================
Day 1, Task 6: Explore fund master -- print unique fund houses, categories,
sub-categories, risk grades, and summarize the AMFI scheme code structure.

Expects a fund master CSV in data/raw/ containing at least an amfi_code /
scheme_code column, plus whichever of fund_house / category / sub_category /
risk_grade are present. Column names are matched flexibly (case-insensitive,
common synonyms) since the exact fund_master.csv wasn't available when this
script was written -- update COLUMN_ALIASES below on first contact with the
real file if any of its headers aren't picked up automatically.

Usage:
    python explore_fund_master.py --file data/raw/fund_master.csv
"""
import argparse
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("explore_fund_master")

COLUMN_ALIASES = {
    "amfi_code": ["amfi_code", "scheme_code", "code"],
    "fund_house": ["fund_house", "amc", "amc_name", "mutual_fund"],
    "category": ["category", "scheme_category"],
    "sub_category": ["sub_category", "subcategory", "scheme_sub_category"],
    "risk_grade": ["risk_grade", "risk", "riskometer", "risk_level"],
}


def resolve_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in df.columns}
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    return None


def explain_amfi_code_structure(codes: pd.Series):
    print("\n--- AMFI Scheme Code Structure ---")
    codes = codes.dropna().astype(str)
    lengths = codes.str.len().value_counts().sort_index()
    print("Code length distribution:")
    print(lengths)
    print(
        "\nAMFI scheme codes are typically 5-6 digit numeric identifiers assigned by AMFI "
        "(Association of Mutual Funds in India) to each individual scheme/plan/option "
        "combination -- i.e. the SAME underlying fund gets a DIFFERENT amfi_code for its "
        "Direct vs Regular plan, and again for Growth vs IDCW option. This is why a fund "
        "house can have far more distinct amfi_codes than distinct 'funds' in the "
        "everyday sense -- always join on amfi_code, never on fund name, since names are "
        "not guaranteed unique or stable across a fund's disclosure history."
    )
    print(f"\nSample codes: {codes.head(10).tolist()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=Path("data/raw/fund_master.csv"))
    args = parser.parse_args()

    if not args.file.exists():
        log.error(
            f"{args.file} not found. Place the fund master CSV in data/raw/ "
            f"(any of the 10 provided datasets that looks like a fund master/reference "
            f"table) and re-run, e.g.: python explore_fund_master.py --file data/raw/<actual_filename>.csv"
        )
        return

    df = pd.read_csv(args.file)
    print(f"Fund master shape: {df.shape}")

    amfi_col = resolve_column(df, COLUMN_ALIASES["amfi_code"])
    house_col = resolve_column(df, COLUMN_ALIASES["fund_house"])
    cat_col = resolve_column(df, COLUMN_ALIASES["category"])
    subcat_col = resolve_column(df, COLUMN_ALIASES["sub_category"])
    risk_col = resolve_column(df, COLUMN_ALIASES["risk_grade"])

    if house_col:
        print(f"\n--- Unique fund houses ({df[house_col].nunique()}) ---")
        print(sorted(df[house_col].dropna().unique().tolist()))
    else:
        log.warning("No fund_house-like column found -- update COLUMN_ALIASES['fund_house'].")

    if cat_col:
        print(f"\n--- Unique categories ({df[cat_col].nunique()}) ---")
        print(sorted(df[cat_col].dropna().unique().tolist()))
    else:
        log.warning("No category-like column found -- update COLUMN_ALIASES['category'].")

    if subcat_col:
        print(f"\n--- Unique sub-categories ({df[subcat_col].nunique()}) ---")
        print(sorted(df[subcat_col].dropna().unique().tolist()))
    else:
        log.warning("No sub_category-like column found -- update COLUMN_ALIASES['sub_category'].")

    if risk_col:
        print(f"\n--- Unique risk grades ({df[risk_col].nunique()}) ---")
        print(sorted(df[risk_col].dropna().unique().tolist()))
    else:
        log.warning("No risk_grade-like column found -- update COLUMN_ALIASES['risk_grade'].")

    if amfi_col:
        explain_amfi_code_structure(df[amfi_col])
    else:
        log.error("No amfi_code/scheme_code-like column found -- cannot validate against nav_history.")


if __name__ == "__main__":
    main()
