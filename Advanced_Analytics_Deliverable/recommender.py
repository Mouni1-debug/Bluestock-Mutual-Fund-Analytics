"""
recommender.py
===============
Task 5: Simple fund recommender.

Input: risk appetite (Low / Moderate / High)
Output: top 3 funds by Sharpe ratio within the matching risk_grade, printed
as a recommendation table.

Usage (CLI):
    python recommender.py --risk Moderate
    python recommender.py --risk High --top-n 5

Usage (as a library):
    from recommender import recommend_funds
    table = recommend_funds("Moderate")
"""
import argparse

import numpy as np
import pandas as pd

RF = 0.065  # RBI repo rate proxy, consistent with the rest of this capstone's risk metrics

VALID_RISK_GRADES = ["Low", "Moderate", "High"]


def compute_sharpe(nav_wide: pd.DataFrame, rf: float = RF) -> pd.Series:
    daily_returns = nav_wide.pct_change().dropna(how="all")
    ann_return = daily_returns.mean() * 252
    ann_vol = daily_returns.std() * np.sqrt(252)
    return (ann_return - rf) / ann_vol


def recommend_funds(risk_appetite: str, top_n: int = 3,
                     nav_path: str = "data/nav_history.csv",
                     fund_master_path: str = "data/fund_master.csv") -> pd.DataFrame:
    """
    Returns a DataFrame of the top_n funds (by Sharpe ratio) whose risk_grade
    matches the requested risk_appetite, sorted best-first.
    """
    risk_appetite = risk_appetite.strip().title()
    if risk_appetite not in VALID_RISK_GRADES:
        raise ValueError(f"risk_appetite must be one of {VALID_RISK_GRADES}, got {risk_appetite!r}")

    nav = pd.read_csv(nav_path, parse_dates=["date"])
    fund_master = pd.read_csv(fund_master_path).set_index("amfi_code")

    if "risk_grade" not in fund_master.columns:
        raise ValueError(
            "fund_master.csv has no 'risk_grade' column. Add one (Low/Moderate/High per "
            "scheme, typically derived from the AMFI riskometer or scheme category) before "
            "using the recommender."
        )

    nav_wide = nav.pivot(index="date", columns="amfi_code", values="nav").sort_index()
    sharpe = compute_sharpe(nav_wide)

    matching_codes = fund_master[fund_master["risk_grade"] == risk_appetite].index
    matching_codes = [c for c in matching_codes if c in sharpe.index]

    if not matching_codes:
        raise ValueError(f"No funds found with risk_grade == {risk_appetite!r}.")

    result = pd.DataFrame({"sharpe_ratio": sharpe.loc[matching_codes]})
    result = result.join(fund_master[["fund_name", "fund_house", "category", "expense_ratio", "risk_grade"]])
    result = result.sort_values("sharpe_ratio", ascending=False).head(top_n)
    result.insert(0, "rank", range(1, len(result) + 1))
    return result.reset_index().rename(columns={"index": "amfi_code"})


def print_recommendation_table(risk_appetite: str, top_n: int = 3, **kwargs):
    table = recommend_funds(risk_appetite, top_n=top_n, **kwargs)
    print(f"\n{'=' * 90}")
    print(f"TOP {top_n} FUND RECOMMENDATIONS — Risk Appetite: {risk_appetite.upper()}")
    print(f"{'=' * 90}")
    display_cols = ["rank", "fund_name", "category", "sharpe_ratio", "expense_ratio"]
    print(table[display_cols].to_string(index=False))
    print(f"{'=' * 90}\n")
    return table


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--risk", type=str, required=True, choices=VALID_RISK_GRADES,
                         help="Investor risk appetite: Low, Moderate, or High")
    parser.add_argument("--top-n", type=int, default=3, help="Number of funds to recommend (default 3)")
    parser.add_argument("--nav", type=str, default="data/nav_history.csv")
    parser.add_argument("--fund-master", type=str, default="data/fund_master.csv")
    args = parser.parse_args()

    print_recommendation_table(args.risk, top_n=args.top_n, nav_path=args.nav, fund_master_path=args.fund_master)


if __name__ == "__main__":
    main()
