"""Run the full profitability analysis: cleaning log, KPI tables, charts for the report.

Usage:  python analysis.py
Outputs: outputs/*.csv, charts/*.png, outputs/key_findings.json
"""
import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from metrics import (DEFAULT_MARGIN_THRESHOLD, classify_products, dependency_table, division_metrics,
                         flag_products, headline_kpis, herfindahl, items_for_threshold, load_and_clean,
                         monthly_margin, pareto, product_metrics)

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent
CH, OUT = ROOT / "charts", ROOT / "outputs"
CH.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)

PALETTE = {"Chocolate": "#6F4E37", "Other": "#E07A5F", "Sugar": "#3D85C6"}
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .25, "figure.dpi": 150})
short = lambda s: s.replace("Wonka Bar - ", "WB: ")


def save(fig, name):
    fig.tight_layout(); fig.savefig(CH / name, bbox_inches="tight"); plt.close(fig)


df, log = load_and_clean(return_log=True)
kpi = headline_kpis(df)
pm = flag_products(classify_products(product_metrics(df)))
dm = division_metrics(df)
dep = dependency_table(df)
p_rev, p_prof = pareto(df, "Sales"), pareto(df, "Gross Profit")
n80r, pct80r = items_for_threshold(p_rev)
n80p, pct80p = items_for_threshold(p_prof)
state = pareto(df, "Gross Profit", "State/Province")
n80s, pct80s = items_for_threshold(state)
region = df.groupby("Region").agg(Sales=("Sales", "sum"), GP=("Gross Profit", "sum")).assign(
    GM=lambda x: x.GP / x.Sales * 100)
yearly = df.groupby("Year").agg(Sales=("Sales", "sum"), GP=("Gross Profit", "sum")).assign(
    GM=lambda x: x.GP / x.Sales * 100)
factory = df.groupby("Factory").agg(Sales=("Sales", "sum"), GP=("Gross Profit", "sum")).assign(
    GM=lambda x: x.GP / x.Sales * 100, Share=lambda x: x.GP / x.GP.sum() * 100).sort_values("GP", ascending=False)

pm.to_csv(OUT / "product_metrics.csv", index=False)
dm.to_csv(OUT / "division_metrics.csv", index=False)
dep.to_csv(OUT / "dependency_table.csv", index=False)
p_rev.to_csv(OUT / "pareto_revenue.csv", index=False)
p_prof.to_csv(OUT / "pareto_profit.csv", index=False)
state.to_csv(OUT / "pareto_state_profit.csv", index=False)
factory.to_csv(OUT / "factory_metrics.csv")
df.to_csv(OUT / "clean_data.csv", index=False)

# ------------------------------- charts -------------------------------------
# 1. Product leaderboard: profit and margin
s = pm.sort_values("Gross Profit")
fig, ax = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
col = [PALETTE[d] for d in s["Division"]]
ax[0].barh(s["Product Name"].map(short), s["Gross Profit"], color=col)
ax[0].set_xlabel("Gross profit ($)"); ax[0].set_title("Gross profit by product")
ax[1].barh(s["Product Name"].map(short), s["Gross Margin (%)"], color=col)
ax[1].axvline(kpi["Gross Margin (%)"], color="k", ls="--", lw=1)
ax[1].text(kpi["Gross Margin (%)"] + 1, 0.2, f'portfolio {kpi["Gross Margin (%)"]:.1f}%', fontsize=8)
ax[1].set_xlabel("Gross margin (%)"); ax[1].set_title("Gross margin by product")
save(fig, "01_product_leaderboard.png")

# 2. Sales vs margin bubble (segments)
fig, ax = plt.subplots(figsize=(8, 5.5))
ax.scatter(pm["Revenue Contribution (%)"], pm["Gross Margin (%)"], s=pm["Gross Profit"] / 40 + 30,
           c=[PALETTE[d] for d in pm["Division"]], alpha=.8, edgecolor="k")
ax.set_xscale("symlog", linthresh=0.1)
ax.axhline(DEFAULT_MARGIN_THRESHOLD, color="grey", ls="--"); ax.axvline(5, color="grey", ls="--")
for _, r in pm.iterrows():
    if r["Division"] != "Chocolate" and (r["Revenue Contribution (%)"] > 0.3 or r["Gross Margin (%)"] < 30):
        ax.annotate(short(r["Product Name"]), (r["Revenue Contribution (%)"], r["Gross Margin (%)"]),
                    fontsize=7, xytext=(4, 4), textcoords="offset points")
ax.annotate("5 Wonka Bars\n(93% of revenue)", (18, 60), fontsize=8, ha="center")
ax.set_xlabel("Revenue contribution (%) - symlog scale"); ax.set_ylabel("Gross margin (%)")
ax.set_title("Product segmentation: sales level vs margin (bubble = gross profit)")
for d, c in PALETTE.items():
    ax.scatter([], [], c=c, label=d, edgecolor="k")
ax.legend(title="Division", loc="lower right")
save(fig, "02_segmentation.png")

# 3. Division revenue vs profit share and margin
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
x = np.arange(len(dm)); w = .38
ax[0].bar(x - w / 2, dm["Revenue Share (%)"], w, label="Revenue share", color="#9AA5B1")
ax[0].bar(x + w / 2, dm["Profit Share (%)"], w, label="Profit share", color="#2A9D8F")
ax[0].set_xticks(x, dm["Division"]); ax[0].set_ylabel("% of total"); ax[0].legend()
ax[0].set_title("Revenue vs profit share by division")
ax[1].bar(dm["Division"], dm["Gross Margin (%)"], color=[PALETTE[d] for d in dm["Division"]])
ax[1].axhline(kpi["Gross Margin (%)"], color="k", ls="--", lw=1)
for i, v in enumerate(dm["Gross Margin (%)"]):
    ax[1].text(i, v + 1, f"{v:.1f}%", ha="center")
ax[1].set_ylabel("Gross margin (%)"); ax[1].set_title("Gross margin by division")
save(fig, "03_division.png")

# 4. Margin distribution by division (order-line level)
df["Order-line margin (%)"] = df["Gross Profit"] / df["Sales"] * 100
fig, ax = plt.subplots(figsize=(7, 4.5))
order = list(dm["Division"])
ax.boxplot([df.loc[df.Division == d, "Order-line margin (%)"] for d in order], labels=order, patch_artist=True,
           boxprops=dict(facecolor="#DDE6EE"), medianprops=dict(color="#C0392B"))
ax.set_ylabel("Order-line gross margin (%)"); ax.set_title("Margin distribution by division")
save(fig, "04_margin_distribution.png")

# 5. Pareto charts
fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
for a, p, t, n in [(ax[0], p_rev, "Revenue", n80r), (ax[1], p_prof, "Gross profit", n80p)]:
    a.bar(p["Product Name"].map(short), p["Share (%)"], color="#5B7DB1")
    a.set_ylabel("Share (%)"); a.tick_params(axis="x", rotation=75, labelsize=7)
    b = a.twinx(); b.plot(p["Product Name"].map(short), p["Cumulative (%)"], "o-", color="#C0392B", ms=3)
    b.axhline(80, color="grey", ls="--"); b.set_ylim(0, 105); b.set_ylabel("Cumulative (%)"); b.grid(False)
    b.spines["top"].set_visible(False)
    a.set_title(f"Pareto - {t} ({n} of 15 products reach 80%)")
save(fig, "05_pareto.png")

# 6. Cost vs sales scatter
fig, ax = plt.subplots(figsize=(7, 5.5))
ax.scatter(pm["Sales"], pm["Cost"], c=[PALETTE[d] for d in pm["Division"]], s=70, edgecolor="k")
mx = pm["Sales"].max() * 1.05
ax.plot([1, mx], [1, mx], "k:", lw=1, label="Break-even (cost = sales)")
ax.plot([1, mx], [0.4 * 1, 0.4 * mx], "g--", lw=1, label="40% cost ratio (60% margin target)")
ax.set_xscale("log"); ax.set_yscale("log")
for _, r in pm.iterrows():
    if r["Sales"] > 1000 or r["Gross Margin (%)"] < 30:
        ax.annotate(short(r["Product Name"]), (r["Sales"], r["Cost"]), fontsize=7, xytext=(4, -9),
                    textcoords="offset points")
ax.set_xlabel("Total sales ($, log)"); ax.set_ylabel("Total cost ($, log)")
ax.set_title("Cost vs sales by product"); ax.legend(fontsize=8)
save(fig, "06_cost_vs_sales.png")

# 7. Unit economics (price vs cost per unit) for risk products
fig, ax = plt.subplots(figsize=(9, 4.5))
u = pm.sort_values("Profit per Unit", ascending=False)
x = np.arange(len(u))
ax.bar(x, u["Cost per Unit"], color="#E07A5F", label="Cost / unit")
ax.bar(x, u["Profit per Unit"], bottom=u["Cost per Unit"], color="#2A9D8F", label="Profit / unit")
ax.set_xticks(x, u["Product Name"].map(short), rotation=70, ha="right", fontsize=7)
ax.set_ylabel("$ per unit"); ax.set_title("Unit economics: price = cost + profit"); ax.legend()
save(fig, "07_unit_economics.png")

# 8. Monthly trend
mm = monthly_margin(df)
fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(mm["Month"], mm["Sales"], width=20, color="#C9D3DD", label="Sales")
ax.set_ylabel("Sales ($)")
b = ax.twinx(); b.plot(mm["Month"], mm["Gross Margin (%)"], "o-", color="#C0392B", label="Gross margin %")
b.set_ylim(50, 80); b.set_ylabel("Gross margin (%)"); b.grid(False); b.spines["top"].set_visible(False)
ax.set_title("Monthly sales and portfolio gross margin")
save(fig, "08_monthly_trend.png")

# 9. Factory / state dependency
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
ax[0].bar(factory.index, factory["Share"], color="#6C8EAD"); ax[0].set_ylabel("Profit share (%)")
ax[0].tick_params(axis="x", rotation=25); ax[0].set_title("Profit dependency by factory")
top = state.head(10).iloc[::-1]
ax[1].barh(top["State/Province"], top["Share (%)"], color="#6C8EAD"); ax[1].set_xlabel("Profit share (%)")
ax[1].set_title("Top 10 states/provinces by profit")
save(fig, "09_dependency.png")

# ------------------------------- key findings -------------------------------
f = {
    "cleaning_log": log,
    "kpi": {k: float(v) for k, v in kpi.items()},
    "date_range": [str(df["Order Date"].min().date()), str(df["Order Date"].max().date())],
    "pareto": {"revenue_items_80": n80r, "revenue_pct_80": pct80r, "profit_items_80": n80p, "profit_pct_80": pct80p,
               "state_items_80": n80s, "state_total": int(len(state)), "state_pct_80": pct80s,
               "hhi_rev": herfindahl(p_rev), "hhi_profit": herfindahl(p_prof)},
    "yearly": yearly.round(2).reset_index().to_dict("records"),
    "region": region.round(2).reset_index().to_dict("records"),
    "factory": factory.round(2).reset_index().to_dict("records"),
    "ship_lag_days": {"min": int(df["Ship Lag (days)"].min()), "median": float(df["Ship Lag (days)"].median()),
                      "max": int(df["Ship Lag (days)"].max())},
    "top5_state_profit_share": float(state["Share (%)"].head(5).sum()),
    "top_state": [state.iloc[0]["State/Province"], float(state.iloc[0]["Share (%)"])],
    "canada_rows": int((df["Country/Region"] == "Canada").sum()),
}
(OUT / "key_findings.json").write_text(json.dumps(f, indent=2, default=str))
print(json.dumps(f, indent=2, default=str))
