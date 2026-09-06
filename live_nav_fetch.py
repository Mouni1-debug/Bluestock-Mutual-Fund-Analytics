"""
live_nav_fetch.py
==================
Day 1, Tasks 4 & 5: Fetch live NAV data from mfapi.in (free, unauthenticated
Indian mutual fund API) and save each scheme's full NAV history as a raw CSV.

Schemes fetched (per the task brief's labels -- see IMPORTANT NOTE below):
    125497  "HDFC Top 100 Direct"    (per task brief)
    119551  "SBI Bluechip"           (per task brief)
    120503  "ICICI Bluechip"         (per task brief)
    118632  "Nippon Large Cap"       (per task brief)
    119092  "Axis Bluechip"         (per task brief)
    120841  "Kotak Bluechip"         (per task brief)

*** IMPORTANT NOTE / DATA QUALITY FINDING ***
When scheme code 125497 was actually queried against the live API while
building this script, the API's own `meta.scheme_name` / `meta.fund_house`
came back as "SBI SMALL CAP FUND - Direct Plan - Growth" / "SBI Mutual Fund"
-- NOT "HDFC Top 100 Direct" as labeled in the task brief. A second check on
scheme code 119551 likewise returned indications of "Axis Bluechip Fund -
Growth" rather than "SBI Bluechip". This script does NOT hardcode fund
names -- it always uses the scheme_code to fetch, and always saves whatever
meta.scheme_name/meta.fund_house the live API actually returns (see the
"api_reported_name" column added to every saved file), specifically so this
kind of code-to-name mismatch is caught immediately in the output rather
than silently mislabeled. See reports/day1_ingestion_report.md /
data quality summary for the full write-up -- **please reconfirm the
intended scheme codes against the AMFI scheme master before treating the
NAV history as final.**

API reference: GET https://api.mfapi.in/mf/{scheme_code}
    Returns: {"meta": {...}, "data": [{"date": "DD-MM-YYYY", "nav": "..."}]}

Usage:
    python live_nav_fetch.py --outdir data/raw
"""
import argparse
import logging
import time
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("live_nav_fetch")

BASE_URL = "https://api.mfapi.in/mf/{scheme_code}"

# Scheme codes + the label given in the Day 1 task brief. The brief's label
# is kept purely as a reference/comment -- the script trusts the live API's
# own meta.scheme_name, not this label, when naming/describing the fund.
SCHEMES = [
    {"scheme_code": 125497, "brief_label": "HDFC Top 100 Direct"},
    {"scheme_code": 119551, "brief_label": "SBI Bluechip"},
    {"scheme_code": 120503, "brief_label": "ICICI Bluechip"},
    {"scheme_code": 118632, "brief_label": "Nippon Large Cap"},
    {"scheme_code": 119092, "brief_label": "Axis Bluechip"},
    {"scheme_code": 120841, "brief_label": "Kotak Bluechip"},
]


def fetch_scheme(scheme_code: int, timeout: int = 15, retries: int = 3) -> dict:
    url = BASE_URL.format(scheme_code=scheme_code)
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_err = e
            log.warning(f"Attempt {attempt}/{retries} failed for scheme {scheme_code}: {e}")
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"Failed to fetch scheme {scheme_code} after {retries} attempts: {last_err}")


def save_scheme_csv(payload: dict, brief_label: str, outdir: Path) -> Path:
    meta = payload.get("meta", {})
    data = payload.get("data", [])
    scheme_code = meta.get("scheme_code")

    df = pd.DataFrame(data)
    if df.empty:
        raise ValueError(f"No NAV data returned for scheme {scheme_code}")

    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y", errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df["scheme_code"] = scheme_code
    df["api_reported_name"] = meta.get("scheme_name")
    df["api_reported_fund_house"] = meta.get("fund_house")
    df["api_reported_category"] = meta.get("scheme_category")
    df["brief_label"] = brief_label  # what the Day 1 task brief called this code
    df = df.sort_values("date").reset_index(drop=True)

    mismatch = ""
    if meta.get("scheme_name") and brief_label.lower() not in str(meta.get("scheme_name", "")).lower():
        mismatch = "_NAME_MISMATCH"
        log.warning(
            f"Scheme {scheme_code}: brief calls this '{brief_label}' but the API "
            f"reports '{meta.get('scheme_name')}' ({meta.get('fund_house')}). "
            f"Flagging in filename and data quality summary."
        )

    outdir.mkdir(parents=True, exist_ok=True)
    filename = f"nav_raw_{scheme_code}{mismatch}.csv"
    out_path = outdir / filename
    df.to_csv(out_path, index=False)
    log.info(f"Saved {len(df):,} NAV rows for scheme {scheme_code} -> {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=Path("data/raw"))
    parser.add_argument("--codes", type=int, nargs="*", default=None,
                         help="Optional: fetch only these scheme codes instead of the default 6.")
    args = parser.parse_args()

    schemes = SCHEMES
    if args.codes:
        schemes = [s for s in SCHEMES if s["scheme_code"] in args.codes] or \
                   [{"scheme_code": c, "brief_label": "(ad-hoc)"} for c in args.codes]

    results = []
    for s in schemes:
        code = s["scheme_code"]
        try:
            payload = fetch_scheme(code)
            path = save_scheme_csv(payload, s["brief_label"], args.outdir)
            meta = payload.get("meta", {})
            results.append({
                "scheme_code": code,
                "brief_label": s["brief_label"],
                "api_reported_name": meta.get("scheme_name"),
                "api_reported_fund_house": meta.get("fund_house"),
                "rows_fetched": len(payload.get("data", [])),
                "saved_to": str(path),
                "status": "OK",
            })
        except Exception as e:
            log.error(f"Scheme {code} ({s['brief_label']}) FAILED: {e}")
            results.append({
                "scheme_code": code, "brief_label": s["brief_label"],
                "api_reported_name": None, "api_reported_fund_house": None,
                "rows_fetched": 0, "saved_to": None, "status": f"FAILED: {e}",
            })

    summary = pd.DataFrame(results)
    print("\n" + "=" * 100)
    print("LIVE NAV FETCH SUMMARY")
    print("=" * 100)
    print(summary.to_string(index=False))
    print("=" * 100)

    summary_path = args.outdir / "live_nav_fetch_summary.csv"
    summary.to_csv(summary_path, index=False)
    log.info(f"Fetch summary saved: {summary_path}")

    n_ok = (summary["status"] == "OK").sum()
    log.info(f"Done: {n_ok}/{len(summary)} schemes fetched successfully.")


if __name__ == "__main__":
    main()
