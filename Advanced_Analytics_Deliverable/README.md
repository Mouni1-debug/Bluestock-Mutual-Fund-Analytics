# Advanced Analytics + Risk Metrics
**Capstone Project I — Mutual Fund Analytics**
Prepared by: MOUNICA K V

---

## ⚠️ Data note

No real dataset was uploaded for this task. This deliverable reuses the same synthetic 40-scheme NAV/fund-master/portfolio-holdings data built for the earlier EDA and Performance Analytics tasks in this capstone (kept consistent across notebooks), and adds two new pieces built specifically for this task: a `risk_grade` column on `fund_master.csv` (Low/Moderate/High, derived from category) and a new `investor_transactions.csv` (800 investors, ~18,000 transactions, with realistic SIP-continuity behaviour patterns — some investors consistent, some lapsed, some irregular — so the cohort/continuity analysis has genuine signal to find). Swap in real files with the same column names and every notebook cell reruns unchanged (see the notebook's final appendix cell).

## Deliverables (all 4, top level of this folder)

- **`Advanced_Analytics.ipynb`** — fully executed, all 7 tasks
- **`var_cvar_report.csv`** — VaR(95%) and CVaR(95%) for all 40 schemes
- **`recommender.py`** — standalone, runnable fund recommender (`python recommender.py --risk Moderate`)
- **`rolling_sharpe_chart.png`** — 90-day rolling Sharpe for 5 key funds

Plus supporting folders: `data/` (all source CSVs) and `charts/` (all 5 chart PNGs referenced in the notebook).

## All 7 tasks, done

1. **Historical VaR (95%) + CVaR** for all 40 schemes
2. **Rolling 90-day Sharpe** plotted for 5 key funds (one per major equity category) — clearly shows the same 2023 bull-run / 2024-correction pattern from the earlier EDA notebook, a good cross-notebook consistency check
3. **Investor cohort analysis** — grouped by first-transaction year, with avg SIP, total invested, and top fund preference per cohort
4. **SIP continuity analysis** — investors with 6+ SIPs, average gap between dates, flagged at-risk if gap > 35 days (**23% of eligible investors flagged**)
5. **Fund recommender** — risk appetite in, top-3-by-Sharpe out, both as a notebook cell and a standalone CLI script
6. **Sector HHI concentration** — computed for all equity funds, compared by category
7. **5 advanced insights**, each citing real numbers and its supporting chart

## How to run the recommender yourself

```bash
python recommender.py --risk Low
python recommender.py --risk Moderate
python recommender.py --risk High --top-n 5
```

## Headline findings

- Small Cap funds have the worst VaR/CVaR by a clear margin; Debt - Short Duration funds the best — the risk hierarchy the fund categories were designed around holds up in the actual data
- **23% of eligible SIP investors (167 of 725) are flagged at-risk** of lapsing (avg gap > 35 days between SIPs)
- Average sector-concentration HHI across all 40 equity funds is **0.135** (moderate diversification), with a few large-cap-leaning funds (Aditya Birla SL Large Cap, Axis Flexi Cap, Axis Large Cap) crossing 0.17
