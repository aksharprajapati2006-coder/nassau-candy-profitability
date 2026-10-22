# 🍬 Nassau Candy - Product Line Profitability & Margin Performance Analysis

Interactive analytics project that shows which Nassau Candy products and divisions really drive profit, and which ones put margin at risk.

**Live dashboard:** _add your Streamlit link here_  
**Research paper:** [`report/Research_Paper_Nassau_Candy.pdf`](report/Research_Paper_Nassau_Candy.pdf)  
**Executive summary:** [`report/Executive_Summary_Nassau_Candy.pdf`](report/Executive_Summary_Nassau_Candy.pdf)

## Key findings
- Sales **$141,784**, gross profit **$93,443**, gross margin **65.9%** (Jan 2024 - Dec 2025, 10,194 order lines).
- Five Wonka Bars generate **92.9% of revenue** and **95.1% of profit**; 5 of 15 products reach 80% of both.
- **Kazookles** earns a 7.7% margin and **Lickable Wallpaper** 50.0%: both need repricing or cost renegotiation.
- Two factories (Lot's O' Nuts, Wicked Choccy's) produce 95% of profit: a supply-concentration risk.
- Unit price and unit cost are constant per product, so margin volatility is zero; mix drives profit.

## Dashboard modules
| Tab | What it shows |
|---|---|
| Product Overview | Leaderboard, profit contribution, sales-vs-margin segmentation |
| Division Performance | Revenue vs profit, margin distribution, monthly margin |
| Cost vs Margin Diagnostics | Cost-sales scatter, unit economics, margin-risk flags |
| Profit Concentration | Pareto charts, HHI, dependency indicators |

Sidebar filters: date range, division, margin-threshold slider, product search.

## Project structure
```
.
├── app.py                    # Streamlit dashboard
├── metrics.py                # Data cleaning + KPI functions (shared)
├── analysis.py               # Regenerates charts/ and outputs/
├── requirements.txt          # Dependencies for the dashboard (used by deployment)
├── requirements-analysis.txt # Adds matplotlib for analysis.py
├── .streamlit/config.toml    # Theme
├── data/Nassau_Candy_Distributor.csv
├── charts/                   # Figures used in the paper
├── outputs/                  # Result tables (CSV) and key_findings.json
└── report/                   # Research paper + executive summary (DOCX and PDF)
```

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
To regenerate the figures and tables:
```bash
pip install -r requirements-analysis.txt
python analysis.py
```

## Method in brief
Clean and validate -> compute Gross Margin %, Profit per Unit, revenue/profit contribution and margin volatility -> rank and segment products -> compare divisions -> Pareto and dependency analysis -> cost diagnostics with rule-based flags (Critical < 25% margin; Below target; Discontinuation review; Low-volume watch).

## Limitations
Gross profit excludes freight and overheads; Sugar products have very few records; Ship Date values are unreliable and were not used.

**Author:** Akshar Prajapati
