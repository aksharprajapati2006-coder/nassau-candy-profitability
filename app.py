"""Nassau Candy - Product Line Profitability & Margin Performance dashboard.

Run:  streamlit run app.py
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from metrics import (DEFAULT_MARGIN_THRESHOLD, classify_products, dependency_table, division_metrics,
                         flag_products, headline_kpis, items_for_threshold, load_and_clean, monthly_margin,
                         pareto, product_metrics, herfindahl)

st.set_page_config(page_title="Nassau Candy - Profitability", page_icon="🍬", layout="wide")

COLORS = {"Chocolate": "#6F4E37", "Other": "#E07A5F", "Sugar": "#3D85C6"}
FLAG_COLORS = {"Critical - reprice & renegotiate cost": "#C0392B", "Below target - cost renegotiation": "#E67E22",
               "Discontinuation review": "#8E44AD", "Low-volume watch": "#7F8C8D", "Healthy": "#27AE60"}


@st.cache_data(show_spinner="Loading data...")
def get_data() -> pd.DataFrame:
    return load_and_clean()


df_all = get_data()

# ------------------------------ sidebar filters ------------------------------
st.sidebar.title("🍬 Filters")
dmin, dmax = df_all["Order Date"].min().date(), df_all["Order Date"].max().date()
date_range = st.sidebar.date_input("Order date range", (dmin, dmax), min_value=dmin, max_value=dmax)
divisions = sorted(df_all["Division"].unique())
sel_div = st.sidebar.multiselect("Division", divisions, default=divisions)
margin_thr = st.sidebar.slider("Margin threshold (%)", 0, 100, int(DEFAULT_MARGIN_THRESHOLD),
                               help="Products below this gross margin are treated as low-margin / at risk.")
search = st.sidebar.text_input("Product search", placeholder="e.g. Wonka, Kazookles")

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start, end = date_range
else:  # user is mid-selection
    start = end = date_range[0] if isinstance(date_range, (tuple, list)) else date_range

mask = (df_all["Order Date"].dt.date >= start) & (df_all["Order Date"].dt.date <= end) & \
       (df_all["Division"].isin(sel_div))
if search:
    mask &= df_all["Product Name"].str.contains(search, case=False, regex=False)
df = df_all[mask]

st.title("Product Line Profitability & Margin Performance")
st.caption("Nassau Candy Distributor - gross profit, margin and concentration analytics")

if df.empty:
    st.warning("No records match the current filters. Widen the date range, division or search term.")
    st.stop()

pm = flag_products(classify_products(product_metrics(df), margin_threshold=margin_thr), margin_threshold=margin_thr)
kpi = headline_kpis(df)

k = st.columns(6)
k[0].metric("Sales", f"${kpi['Sales']:,.0f}")
k[1].metric("Gross profit", f"${kpi['Gross Profit']:,.0f}")
k[2].metric("Gross margin", f"{kpi['Gross Margin (%)']:.1f}%")
k[3].metric("Profit / unit", f"${kpi['Profit per Unit']:.2f}")
k[4].metric("Units", f"{kpi['Units']:,.0f}")
k[5].metric("Products at risk", int((~pm["Risk Flag"].isin(["Healthy", "Low-volume watch"])).sum()))

tab1, tab2, tab3, tab4 = st.tabs(["📊 Product Overview", "🏭 Division Performance",
                                  "🔎 Cost vs Margin Diagnostics", "📈 Profit Concentration"])

# ------------------------------- Tab 1 ---------------------------------------
with tab1:
    c1, c2 = st.columns([3, 2])
    rank_by = c1.radio("Rank products by", ["Gross Profit", "Gross Margin (%)", "Profit per Unit"], horizontal=True)
    lb = pm.sort_values(rank_by, ascending=True)
    fig = px.bar(lb, x=rank_by, y="Product Name", color="Division", color_discrete_map=COLORS, orientation="h",
                 hover_data=["Sales", "Gross Profit", "Gross Margin (%)", "Units"], height=480)
    fig.update_layout(margin=dict(l=0, r=0, t=30, b=0), yaxis_title=None)
    c1.plotly_chart(fig, use_container_width=True)

    pie = px.pie(pm, names="Product Name", values="Gross Profit", hole=.45, title="Profit contribution")
    pie.update_traces(textposition="inside", textinfo="percent")
    pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=40, b=0), height=480)
    c2.plotly_chart(pie, use_container_width=True)

    st.subheader("Product leaderboard")
    cols = ["Rank (Profit)", "Product Name", "Division", "Factory", "Sales", "Gross Profit", "Gross Margin (%)",
            "Profit per Unit", "Revenue Contribution (%)", "Profit Contribution (%)", "Margin Volatility (pp)",
            "Segment"]
    st.dataframe(pm[cols].style.format({"Sales": "${:,.0f}", "Gross Profit": "${:,.0f}", "Gross Margin (%)": "{:.1f}",
                                        "Profit per Unit": "${:.2f}", "Revenue Contribution (%)": "{:.2f}",
                                        "Profit Contribution (%)": "{:.2f}", "Margin Volatility (pp)": "{:.2f}"},
                                       na_rep="n/a"), use_container_width=True, hide_index=True)

    seg = px.scatter(pm, x="Revenue Contribution (%)", y="Gross Margin (%)", size="Gross Profit", color="Segment",
                     hover_name="Product Name", log_x=True, size_max=45, height=420,
                     title="Segmentation: revenue share vs margin")
    seg.add_hline(y=margin_thr, line_dash="dash", line_color="grey")
    seg.add_vline(x=5, line_dash="dash", line_color="grey")
    st.plotly_chart(seg, use_container_width=True)
    st.caption("Margin volatility is the standard deviation of monthly gross margin (percentage points). "
               "It is ~0 for every product because unit price and unit cost are constant in this dataset; "
               "n/a = fewer than 3 months of sales.")

# ------------------------------- Tab 2 ---------------------------------------
with tab2:
    dm = division_metrics(df)
    c1, c2 = st.columns(2)
    long = dm.melt(id_vars="Division", value_vars=["Sales", "Gross Profit"], var_name="Metric", value_name="$")
    c1.plotly_chart(px.bar(long, x="Division", y="$", color="Metric", barmode="group",
                           title="Revenue vs profit by division", height=380), use_container_width=True)
    share = dm.melt(id_vars="Division", value_vars=["Revenue Share (%)", "Profit Share (%)"],
                    var_name="Metric", value_name="%")
    c2.plotly_chart(px.bar(share, x="Division", y="%", color="Metric", barmode="group",
                           title="Revenue share vs profit share (imbalance)", height=380), use_container_width=True)

    c3, c4 = st.columns(2)
    dfm = df.assign(**{"Order-line margin (%)": df["Gross Profit"] / df["Sales"] * 100})
    c3.plotly_chart(px.box(dfm, x="Division", y="Order-line margin (%)", color="Division",
                           color_discrete_map=COLORS, title="Margin distribution by division", height=380)
                    .update_layout(showlegend=False), use_container_width=True)
    c4.plotly_chart(px.bar(dm, x="Division", y="Gross Margin (%)", color="Division", color_discrete_map=COLORS,
                           text=dm["Gross Margin (%)"].round(1), title="Gross margin by division", height=380)
                    .update_layout(showlegend=False), use_container_width=True)

    st.dataframe(dm.style.format({c: "{:,.1f}" for c in dm.columns if c not in ["Division", "Products", "Orders"]}),
                 use_container_width=True, hide_index=True)
    weak = dm[dm["Gross Margin (%)"] < margin_thr]
    if len(weak):
        st.error("Structural margin issue (below threshold): " + ", ".join(weak["Division"]))
    else:
        st.success("All selected divisions are at or above the margin threshold.")

    mm = monthly_margin(df, by="Division")
    st.plotly_chart(px.line(mm, x="Month", y="Gross Margin (%)", color="Division", color_discrete_map=COLORS,
                            markers=True, title="Monthly gross margin by division", height=360),
                    use_container_width=True)

# ------------------------------- Tab 3 ---------------------------------------
with tab3:
    c1, c2 = st.columns(2)
    sc = px.scatter(pm, x="Sales", y="Cost", size="Units", color="Risk Flag", color_discrete_map=FLAG_COLORS,
                    hover_name="Product Name", log_x=True, log_y=True, size_max=40, height=450,
                    title="Cost vs sales (log scale)")
    lim = [max(pm["Sales"].min(), 1), pm["Sales"].max()]
    sc.add_trace(go.Scatter(x=lim, y=[l * (1 - margin_thr / 100) for l in lim], mode="lines",
                            line=dict(dash="dash", color="green"), name=f"Cost at {margin_thr}% margin"))
    sc.add_trace(go.Scatter(x=lim, y=lim, mode="lines", line=dict(dash="dot", color="black"), name="Break-even"))
    c1.plotly_chart(sc, use_container_width=True)

    u = pm.sort_values("Profit per Unit", ascending=False)
    ue = go.Figure([go.Bar(x=u["Product Name"], y=u["Cost per Unit"], name="Cost / unit", marker_color="#E07A5F"),
                    go.Bar(x=u["Product Name"], y=u["Profit per Unit"], name="Profit / unit", marker_color="#2A9D8F")])
    ue.update_layout(barmode="stack", title="Unit economics (price = cost + profit)", height=450,
                     xaxis_tickangle=-60)
    c2.plotly_chart(ue, use_container_width=True)

    st.subheader("Margin risk flags & recommended action")
    flagged = pm[pm["Risk Flag"] != "Healthy"].sort_values("Gross Margin (%)")
    st.dataframe(flagged[["Product Name", "Division", "Factory", "Sales", "Gross Profit", "Gross Margin (%)",
                          "Cost Ratio (%)", "Revenue Contribution (%)", "Risk Flag"]]
                 .style.format({"Sales": "${:,.0f}", "Gross Profit": "${:,.0f}", "Gross Margin (%)": "{:.1f}",
                                "Cost Ratio (%)": "{:.1f}", "Revenue Contribution (%)": "{:.2f}"}),
                 use_container_width=True, hide_index=True)
    st.caption("Rules: Critical = margin < 25%; Below target = margin < threshold and revenue share >= 1%; "
               "Discontinuation review = margin < threshold and revenue share < 0.5%; "
               "Low-volume watch = healthy margin but revenue share < 0.5%.")

# ------------------------------- Tab 4 ---------------------------------------
with tab4:
    metric = st.radio("Pareto on", ["Sales", "Gross Profit"], horizontal=True)
    p = pareto(df, metric)
    n80, pct80 = items_for_threshold(p)
    a, b, c = st.columns(3)
    a.metric(f"Products for 80% of {metric.lower()}", f"{n80} of {len(p)}", f"{pct80:.0f}% of portfolio")
    b.metric("Top product share", f"{p['Share (%)'].iloc[0]:.1f}%", p["Product Name"].iloc[0], delta_color="off")
    c.metric("HHI (concentration)", f"{herfindahl(p):,.0f}", "> 2,500 = highly concentrated", delta_color="off")

    par = go.Figure()
    par.add_trace(go.Bar(x=p["Product Name"], y=p["Share (%)"], name="Share (%)", marker_color="#5B7DB1"))
    par.add_trace(go.Scatter(x=p["Product Name"], y=p["Cumulative (%)"], name="Cumulative (%)", yaxis="y2",
                             mode="lines+markers", line=dict(color="#C0392B")))
    par.add_hline(y=80, line_dash="dash", line_color="grey", yref="y2")
    par.update_layout(title=f"Pareto chart - {metric} by product", height=470, xaxis_tickangle=-60,
                      yaxis=dict(title="Share (%)"), yaxis2=dict(title="Cumulative (%)", overlaying="y",
                                                                  side="right", range=[0, 105]))
    st.plotly_chart(par, use_container_width=True)

    st.subheader("Dependency indicators")
    dep = dependency_table(df)
    st.dataframe(dep.style.format({"Top Item Profit Share (%)": "{:.1f}", "Top-3 Share (%)": "{:.1f}",
                                   "HHI": "{:,.0f}"}), use_container_width=True, hide_index=True)
    for _, r in dep[dep["Risk"] == "High"].iterrows():
        st.warning(f"**{r['Dimension']} dependency:** {r['Top Item']} generates "
                   f"{r['Top Item Profit Share (%)']:.1f}% of gross profit.")

    st_p = pareto(df, "Gross Profit", "State/Province").head(10)
    st.plotly_chart(px.bar(st_p, x="State/Province", y="Share (%)", title="Top 10 states/provinces by profit share",
                           height=360), use_container_width=True)

with st.expander("Download filtered product metrics"):
    st.download_button("Download CSV", pm.to_csv(index=False).encode(), "product_metrics.csv", "text/csv")
