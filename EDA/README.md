# Exploratory Data Analysis (EDA)
**Capstone Project I — Mutual Fund Analytics**
Prepared by: MOUNICA K V

---

## ⚠️ Data note

No real dataset was uploaded for this task, so this deliverable uses **synthetic data anchored to the exact figures given in the task brief** — SBI AUM ₹12.5L Cr (2025), SIP all-time-high ₹31,002 Cr (Dec 2025), and folio count growing from 13.26 Cr (Jan 2022) to 26.12 Cr (Dec 2025) are all hit exactly. Everything else (40 schemes' NAV history, AUM by fund house, category-wise inflows, investor demographics, geography, sector weights) is calibrated to be internally consistent and realistic around those anchors. Swap in the real CSVs (same column names — see the notebook's final appendix cell) and every chart reruns unchanged.

## What's inside

```
EDA_Deliverable/
├── notebooks/
│   └── EDA_Analysis.ipynb   <- fully executed, all 10 tasks, 16 charts
├── charts/                   <- all 16 chart PNGs, exported for the final report
├── data/                     <- the 10 synthetic source CSVs used
└── README.md
```

## All 10 tasks, all done

1. **NAV trend** — all 40 schemes, 2022–2026, Plotly, with 2023 bull run / 2024 correction highlighted
2. **AUM growth** — grouped bar by fund house, 2022–2025, Seaborn, SBI's ₹12.5L Cr dominance visible
3. **SIP inflow time-series** — monthly, Jan 2022–Dec 2025, Plotly, ₹31,002 Cr Dec-2025 peak annotated
4. **Category inflow heatmap** — months × categories, Seaborn
5. **Investor demographics** — age-group pie, SIP-by-age box plot, gender split
6. **Geographic distribution** — SIP by state (horizontal bar), T30 vs B30 pie
7. **Folio count growth** — 13.26 Cr → 26.12 Cr, line chart with milestones marked
8. **NAV return correlation matrix** — 10 selected funds, Seaborn heatmap
9. **Sector allocation donut** — aggregated from portfolio holdings across equity funds
10. **10 key findings** — one markdown cell per insight, each citing its supporting chart

## Note on chart generation (Plotly → PNG)

This build environment couldn't install Google Chrome (needed by Plotly's `kaleido` image export — its network access is restricted). Tasks 1 and 3 specifically call for Plotly, so the notebook still builds and displays real, fully interactive `go.Figure` Plotly charts inline — but for the static PNG export, a small helper reconstructs an equivalent Matplotlib rendering directly from the same Plotly figure's trace data, shapes, and annotations (not a different chart — the same data, same highlighted regions, same annotation text). See the `save_plotly()` docstring in the notebook's second cell for the full explanation. If you run the notebook somewhere with Chrome available, `fig.write_image()` will work directly with no changes needed.

## Headline numbers referenced in the findings

- SBI AUM 2025: **₹12,50,000 Cr**
- SIP inflow, Dec 2025 (all-time high): **₹31,002 Cr**
- Folio count: **13.26 Cr (Jan 2022) → 26.12 Cr (Dec 2025)**
- Top sector in equity portfolios: **Financial Services at ~25.4%**
- Investor base: **~71% male / 29% female**, T30 cities hold **~71% of AUM**
