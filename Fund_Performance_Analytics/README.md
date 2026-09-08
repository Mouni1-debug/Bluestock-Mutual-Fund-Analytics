# Fund Performance Analytics
**Capstone Project I — Mutual Fund Analytics**
Prepared by: MOUNICA K V

---

## ⚠️ Data note

The real 40-scheme dataset for this task wasn't available, so this deliverable was built with **synthetic NAV data** calibrated to realistic Indian mutual fund behaviour: category-appropriate drift/volatility (Large Cap, Mid Cap, Small Cap, Flexi Cap, ELSS, Hybrid Aggressive, Debt - Short Duration), realistic beta ranges vs a simulated Nifty 100, expense-ratio drag, and fat-tailed daily shocks (Student-t) rather than plain normal noise. `data/nav_history.csv`, `data/fund_master.csv`, and `data/benchmark_index.csv` follow the exact column schema real data would need — swap them in and every notebook cell reruns unchanged (see the notebook's final appendix cell for the exact columns expected).

## What's inside

```
Fund_Performance_Analytics/
├── data/
│   ├── nav_history.csv        (40 schemes x 1,304 trading days, 2021-09-01 to 2026-08-31)
│   ├── fund_master.csv        (fund_name, fund_house, category, expense_ratio)
│   └── benchmark_index.csv    (Nifty 50, Nifty 100 daily levels)
├── notebooks/
│   └── Performance_Analytics.ipynb   <- fully executed, all 8 tasks
├── outputs/
│   ├── fund_scorecard.csv     <- deliverable
│   ├── alpha_beta.csv         <- deliverable
│   └── benchmark_comparison_chart.png  <- deliverable
├── charts/                     (4 charts, incl. the 2 extra diagnostic ones from the notebook)
└── README.md
```

## What's implemented (all 8 tasks)

1. **Daily returns** for all 40 schemes, with a distribution sanity check (skew ≈ 0.17, excess kurtosis ≈ 2.4 — fat tails, as expected for real equity fund returns)
2. **CAGR** 1yr/3yr/5yr comparison table across all 40 funds
3. **Sharpe Ratio** (Rf = 6.5%), ranked 1–40
4. **Sortino Ratio** (downside deviation only), ranked 1–40
5. **Alpha/Beta** via `scipy.stats.linregress` of each fund's daily returns on Nifty 100, alpha annualized (×252)
6. **Maximum Drawdown** per fund, with the peak/trough date range of the worst drawdown
7. **Fund Scorecard (0–100)** — exact weighting from the brief: 30% 3yr-return rank + 25% Sharpe rank + 20% Alpha rank + 15% expense-ratio rank (inverse) + 10% max-DD rank (inverse)
8. **Benchmark comparison chart** — top 5 scorecard funds vs Nifty 50/Nifty 100, trailing 3 years, plus tracking error = `std(fund_return − benchmark_return) × √252`

## Headline result & a methodology caveat worth knowing

**#1 fund by scorecard:** ICICI Pru Large Cap Fund - Direct Growth (score 89.4, 3yr CAGR 37.3%, Sharpe 0.61).

**Caveat flagged in the notebook:** a debt fund (Sundaram Debt - Short Duration) lands at **#5 overall** despite a 3yr CAGR of only 10.1% vs 36–37% for the equity funds around it — because low volatility inflates its Sharpe/expense/drawdown ranks under this composite formula. That's a mathematically correct output of the specified weighting, but it's a real limitation of scoring debt and equity funds on one shared 0–100 scale for investor-facing fund selection. The notebook recommends computing the scorecard **within each category** if it'll be used for that purpose. See the notebook's markdown note right after the scorecard table for the full discussion.

## How to reproduce with real data

1. Replace the 3 files in `data/` with the real ones (same column names)
2. Re-run `notebooks/Performance_Analytics.ipynb` top to bottom — nothing else needs to change
