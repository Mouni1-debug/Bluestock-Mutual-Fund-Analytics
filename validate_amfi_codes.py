"""
validate_amfi_codes.py
========================
Day 1, Task 7: Confirm every amfi_code in fund_master exists in nav_history,
and write a short data quality summary.

Usage:
    python validate_amfi_codes.py \
        --fund-master data/raw/fund_master.csv \
        --nav-history data/raw/nav_history.csv \
        --out reports/day1_data_quality_summary.md
"""
import argparse
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("validate_amfi_codes")


def resolve_code_column(df: pd.DataFrame) -> str:
    for candidate in ["amfi_code", "scheme_code", "code"]:
        for col in df.columns:
            if col.lower() == candidate:
                return col
    raise ValueError(f"No amfi_code/scheme_code column found among: {list(df.columns)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fund-master", type=Path, default=Path("data/raw/fund_master.csv"))
    parser.add_argument("--nav-history", type=Path, default=Path("data/raw/nav_history.csv"))
    parser.add_argument("--out", type=Path, default=Path("reports/day1_data_quality_summary.md"))
    args = parser.parse_args()

    missing_inputs = [p for p in [args.fund_master, args.nav_history] if not p.exists()]
    if missing_inputs:
        log.error(f"Missing input file(s): {[str(p) for p in missing_inputs]}. "
                  f"Place the real fund_master.csv and nav_history.csv in data/raw/ and re-run.")
        return

    fund_master = pd.read_csv(args.fund_master)
    nav_history = pd.read_csv(args.nav_history)

    fm_code_col = resolve_code_column(fund_master)
    nav_code_col = resolve_code_column(nav_history)

    fm_codes = set(fund_master[fm_code_col].astype(str).str.strip())
    nav_codes = set(nav_history[nav_code_col].astype(str).str.strip())

    missing_in_nav = sorted(fm_codes - nav_codes)
    orphan_in_nav = sorted(nav_codes - fm_codes)
    matched = fm_codes & nav_codes

    coverage_pct = round(100 * len(matched) / len(fm_codes), 2) if fm_codes else 0.0

    print(f"fund_master unique codes : {len(fm_codes)}")
    print(f"nav_history unique codes : {len(nav_codes)}")
    print(f"Matched (present in both): {len(matched)} ({coverage_pct}%)")
    print(f"In fund_master but MISSING from nav_history: {len(missing_in_nav)}")
    if missing_in_nav:
        print(f"  e.g. {missing_in_nav[:10]}")
    print(f"In nav_history but NOT in fund_master (orphans): {len(orphan_in_nav)}")
    if orphan_in_nav:
        print(f"  e.g. {orphan_in_nav[:10]}")

    lines = [
        "# Day 1 — Data Quality Summary\n",
        "## AMFI Code Coverage: fund_master vs nav_history\n",
        f"- fund_master unique codes: **{len(fm_codes)}**",
        f"- nav_history unique codes: **{len(nav_codes)}**",
        f"- Matched (present in both): **{len(matched)}** ({coverage_pct}% of fund_master)",
        f"- In fund_master but missing from nav_history: **{len(missing_in_nav)}**",
        f"- In nav_history but not in fund_master (orphan codes): **{len(orphan_in_nav)}**",
        "",
        "### Verdict",
        (
            "✅ Every amfi_code in fund_master has matching NAV history."
            if not missing_in_nav else
            f"⚠️ {len(missing_in_nav)} fund(s) in fund_master have NO NAV history at all -- "
            f"these funds cannot be used in any NAV-based analysis (returns, charts, dashboards) "
            f"until nav_history is backfilled or the funds are confirmed genuinely inactive/delisted."
        ),
        "",
        "### Missing codes (first 20)" if missing_in_nav else "",
    ]
    if missing_in_nav:
        lines += [f"- {c}" for c in missing_in_nav[:20]]
    lines += ["", "### Orphan codes in nav_history (first 20)" if orphan_in_nav else ""]
    if orphan_in_nav:
        lines += [f"- {c}" for c in orphan_in_nav[:20]]

    lines += [
        "",
        "## Known live-fetch discrepancy (see live_nav_fetch.py)",
        "While building live_nav_fetch.py, scheme code **125497** was live-queried against "
        "https://api.mfapi.in and the API returned `scheme_name = \"SBI SMALL CAP FUND - "
        "Direct Plan - Growth\"` (SBI Mutual Fund), **not** \"HDFC Top 100 Direct\" as the "
        "Day 1 task brief labels it. The other 5 scheme codes should be re-verified against "
        "the live API / the official AMFI scheme master the same way before being treated as "
        "confirmed -- do not assume the brief's fund-name labels are correct without checking "
        "the API's own `meta.scheme_name` for each code (see nav_raw_*_NAME_MISMATCH.csv in "
        "data/raw/ for the one code that was checked and flagged).",
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines))
    log.info(f"Data quality summary saved: {args.out}")


if __name__ == "__main__":
    main()
