"""Core data-cleaning and profitability metric functions.

Used by both analysis.py (static report/figures) and app.py (Streamlit dashboard)
so numbers in the paper and the dashboard always agree.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

DATA_PATH = Path(__file__).resolve().parent / "data" / "Nassau_Candy_Distributor.csv"

# Product -> factory mapping given in the project brief
FACTORY_MAP = {
    "Wonka Bar - Nutty Crunch Surprise": "Lot's O' Nuts",
    "Wonka Bar - Fudge Mallows": "Lot's O' Nuts",
    "Wonka Bar - Scrumdiddlyumptious": "Lot's O' Nuts",
    "Wonka Bar - Milk Chocolate": "Wicked Choccy's",
    "Wonka Bar - Triple Dazzle Caramel": "Wicked Choccy's",
    "Laffy Taffy": "Sugar Shack",
    "SweeTARTS": "Sugar Shack",
    "Nerds": "Sugar Shack",
    "Fun Dip": "Sugar Shack",
    "Fizzy Lifting Drinks": "Sugar Shack",
    "Everlasting Gobstopper": "Secret Factory",
    "Hair Toffee": "The Other Factory",
    "Lickable Wallpaper": "Secret Factory",
    "Wonka Gum": "Secret Factory",
    "Kazookles": "The Other Factory",
}

# Defaults used for classification / flagging (all adjustable in the dashboard)
DEFAULT_MARGIN_THRESHOLD = 60.0   # % gross margin considered "healthy"
HIGH_SALES_SHARE = 5.0            # % of revenue -> "high-sales" product
LOW_SALES_SHARE = 0.5             # % of revenue -> "low-sales" product
CRITICAL_MARGIN = 25.0            # % margin below which a product is critical


# --------------------------------------------------------------------------- #
# Loading & cleaning
# --------------------------------------------------------------------------- #
def standardize_label(text: str) -> str:
    """Trim, collapse spaces and fix spacing around hyphens ('Bar -X' -> 'Bar - X')."""
    text = re.sub(r"\s+", " ", str(text)).strip()
    text = re.sub(r"\s*-\s*", " - ", text)
    return text


def load_and_clean(path: Path | str = DATA_PATH, return_log: bool = False):
    """Load the CSV, validate it and return a clean dataframe (+ optional cleaning log)."""
    raw = pd.read_csv(path)
    log = {"rows_raw": len(raw)}
    df = raw.copy()

    # Standardise labels
    for col in ["Product Name", "Division", "Region", "State/Province", "City", "Ship Mode"]:
        df[col] = df[col].astype(str).map(standardize_label)
    df["Division"] = df["Division"].str.title()
    df["Product Name"] = df["Product Name"].map(standardize_label)

    # Dates (file uses dd-mm-yyyy)
    df["Order Date"] = pd.to_datetime(df["Order Date"], dayfirst=True, errors="coerce")
    df["Ship Date"] = pd.to_datetime(df["Ship Date"], dayfirst=True, errors="coerce")
    log["bad_order_dates"] = int(df["Order Date"].isna().sum())

    # Numeric coercion
    for col in ["Sales", "Units", "Gross Profit", "Cost"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    log["missing_units"] = int(df["Units"].isna().sum())

    # Missing units: infer from Sales / typical price of the same product if possible
    if df["Units"].isna().any():
        price = (df["Sales"] / df["Units"]).groupby(df["Product Name"]).median()
        fill = (df["Sales"] / df["Product Name"].map(price)).round()
        df["Units"] = df["Units"].fillna(fill)

    # Remove invalid records
    before = len(df)
    df = df.dropna(subset=["Order Date", "Sales", "Cost", "Gross Profit", "Units"])
    df = df[(df["Sales"] > 0) & (df["Units"] > 0) & (df["Cost"] >= 0)]
    log["rows_removed_invalid"] = before - len(df)

    # Validate Gross Profit = Sales - Cost (tolerance of 2 cents)
    mismatch = (df["Sales"] - df["Cost"] - df["Gross Profit"]).abs() > 0.02
    log["profit_mismatch_rows"] = int(mismatch.sum())
    df.loc[mismatch, "Gross Profit"] = df["Sales"] - df["Cost"]

    # Duplicates
    log["duplicates_removed"] = int(df.duplicated(subset=["Row ID"]).sum())
    df = df.drop_duplicates(subset=["Row ID"])

    # Derived columns
    df["Factory"] = df["Product Name"].map(FACTORY_MAP)
    df["Month"] = df["Order Date"].dt.to_period("M").dt.to_timestamp()
    df["Year"] = df["Order Date"].dt.year
    df["Ship Lag (days)"] = (df["Ship Date"] - df["Order Date"]).dt.days
    log["ship_date_after_2025"] = int((df["Ship Date"] > pd.Timestamp("2025-12-31")).sum())
    log["rows_clean"] = len(df)

    df = df.reset_index(drop=True)
    return (df, log) if return_log else df


# --------------------------------------------------------------------------- #
# Profitability metrics
# --------------------------------------------------------------------------- #
def _safe_div(a, b):
    return np.where(b != 0, a / np.where(b == 0, np.nan, b), np.nan)


def margin_volatility(df: pd.DataFrame, group: str = "Product Name", min_months: int = 3) -> pd.Series:
    """Std-dev (percentage points) of monthly gross margin per group.

    Groups trading in fewer than ``min_months`` months return NaN (too sparse)."""
    m = df.groupby([group, "Month"]).agg(S=("Sales", "sum"), P=("Gross Profit", "sum")).reset_index()
    m["gm"] = m["P"] / m["S"] * 100
    out = m.groupby(group)["gm"].agg(["std", "count"])
    out.loc[out["count"] < min_months, "std"] = np.nan
    return out["std"].round(6).rename("Margin Volatility (pp)")


def product_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """One row per product with the KPIs listed in the brief."""
    g = (
        df.groupby(["Division", "Product Name", "Factory"], dropna=False)
        .agg(Sales=("Sales", "sum"), Cost=("Cost", "sum"), Gross_Profit=("Gross Profit", "sum"),
             Units=("Units", "sum"), Orders=("Order ID", "nunique"))
        .reset_index()
        .rename(columns={"Gross_Profit": "Gross Profit"})
    )
    tot_s, tot_p = g["Sales"].sum(), g["Gross Profit"].sum()
    g["Gross Margin (%)"] = g["Gross Profit"] / g["Sales"] * 100
    g["Profit per Unit"] = g["Gross Profit"] / g["Units"]
    g["Avg Price per Unit"] = g["Sales"] / g["Units"]
    g["Cost per Unit"] = g["Cost"] / g["Units"]
    g["Cost Ratio (%)"] = g["Cost"] / g["Sales"] * 100
    g["Revenue Contribution (%)"] = g["Sales"] / tot_s * 100
    g["Profit Contribution (%)"] = g["Gross Profit"] / tot_p * 100
    g = g.merge(margin_volatility(df).reset_index(), on="Product Name", how="left")
    g["Rank (Profit)"] = g["Gross Profit"].rank(ascending=False, method="min").astype(int)
    g["Rank (Margin)"] = g["Gross Margin (%)"].rank(ascending=False, method="min").astype(int)
    return g.sort_values("Gross Profit", ascending=False).reset_index(drop=True)


def classify_products(pm: pd.DataFrame, margin_threshold: float = DEFAULT_MARGIN_THRESHOLD,
                      high_sales: float = HIGH_SALES_SHARE) -> pd.DataFrame:
    """Quadrant classification (sales level x margin level)."""
    pm = pm.copy()
    hs = pm["Revenue Contribution (%)"] >= high_sales
    hm = pm["Gross Margin (%)"] >= margin_threshold
    pm["Segment"] = np.select(
        [hs & hm, hs & ~hm, ~hs & hm],
        ["High-profit / High-margin", "High-sales / Low-margin", "Low-sales / High-margin"],
        default="Low-sales / Low-profit",
    )
    return pm


def flag_products(pm: pd.DataFrame, margin_threshold: float = DEFAULT_MARGIN_THRESHOLD,
                  low_sales: float = LOW_SALES_SHARE, critical: float = CRITICAL_MARGIN) -> pd.DataFrame:
    """Margin-risk flag and recommended action for each product."""
    pm = pm.copy()
    gm, share = pm["Gross Margin (%)"], pm["Revenue Contribution (%)"]
    conds = [
        gm < critical,
        (gm < margin_threshold) & (share >= 1.0),
        (gm < margin_threshold) & (share < low_sales),
        (share < low_sales),
    ]
    flags = ["Critical - reprice & renegotiate cost", "Below target - cost renegotiation",
             "Discontinuation review", "Low-volume watch"]
    pm["Risk Flag"] = np.select(conds, flags, default="Healthy")
    return pm


def division_metrics(df: pd.DataFrame) -> pd.DataFrame:
    d = (
        df.groupby("Division")
        .agg(Sales=("Sales", "sum"), Cost=("Cost", "sum"), Gross_Profit=("Gross Profit", "sum"),
             Units=("Units", "sum"), Products=("Product Name", "nunique"), Orders=("Order ID", "nunique"))
        .reset_index()
        .rename(columns={"Gross_Profit": "Gross Profit"})
    )
    d["Gross Margin (%)"] = d["Gross Profit"] / d["Sales"] * 100
    d["Profit per Unit"] = d["Gross Profit"] / d["Units"]
    d["Revenue Share (%)"] = d["Sales"] / d["Sales"].sum() * 100
    d["Profit Share (%)"] = d["Gross Profit"] / d["Gross Profit"].sum() * 100
    d["Profit - Revenue Gap (pp)"] = d["Profit Share (%)"] - d["Revenue Share (%)"]
    # Avg of product margins (unweighted) shows whether one star product hides weak ones
    pm = product_metrics(df)
    d = d.merge(pm.groupby("Division")["Gross Margin (%)"].mean().rename("Avg Product Margin (%)").reset_index(),
                on="Division", how="left")
    return d.sort_values("Gross Profit", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Pareto / concentration
# --------------------------------------------------------------------------- #
def pareto(df: pd.DataFrame, value: str = "Sales", by: str = "Product Name") -> pd.DataFrame:
    """Cumulative contribution table sorted descending by ``value``."""
    p = df.groupby(by)[value].sum().sort_values(ascending=False).reset_index()
    p["Share (%)"] = p[value] / p[value].sum() * 100
    p["Cumulative (%)"] = p["Share (%)"].cumsum()
    p["Rank"] = np.arange(1, len(p) + 1)
    p["Items (%)"] = p["Rank"] / len(p) * 100
    return p


def items_for_threshold(p: pd.DataFrame, threshold: float = 80.0) -> tuple[int, float]:
    """Number (and %) of items needed to reach ``threshold`` % cumulative contribution."""
    n = int((p["Cumulative (%)"] < threshold).sum() + 1)
    return n, n / len(p) * 100


def herfindahl(p: pd.DataFrame) -> float:
    """Herfindahl-Hirschman index on shares (0-10,000). >2,500 = highly concentrated."""
    return float(((p["Share (%)"]) ** 2).sum())


def dependency_table(df: pd.DataFrame) -> pd.DataFrame:
    """Share of profit coming from the single largest product / factory / state / region."""
    rows = []
    for label, col in [("Product", "Product Name"), ("Factory", "Factory"),
                       ("State/Province", "State/Province"), ("Region", "Region"), ("Division", "Division")]:
        p = pareto(df, "Gross Profit", col)
        top = p.iloc[0]
        rows.append({"Dimension": label, "Top Item": top[col], "Top Item Profit Share (%)": top["Share (%)"],
                     "Top-3 Share (%)": p["Share (%)"].head(3).sum(), "HHI": herfindahl(p)})
    out = pd.DataFrame(rows)
    out["Risk"] = np.select([out["Top Item Profit Share (%)"] >= 50, out["Top Item Profit Share (%)"] >= 25],
                            ["High", "Moderate"], default="Low")
    return out


def monthly_margin(df: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    keys = ["Month"] + ([by] if by else [])
    m = df.groupby(keys).agg(Sales=("Sales", "sum"), Gross_Profit=("Gross Profit", "sum")).reset_index()
    m["Gross Margin (%)"] = m["Gross_Profit"] / m["Sales"] * 100
    return m.rename(columns={"Gross_Profit": "Gross Profit"})


def headline_kpis(df: pd.DataFrame) -> dict:
    s, p, u = df["Sales"].sum(), df["Gross Profit"].sum(), df["Units"].sum()
    return {"Sales": s, "Gross Profit": p, "Units": u, "Cost": df["Cost"].sum(),
            "Gross Margin (%)": p / s * 100 if s else np.nan, "Profit per Unit": p / u if u else np.nan,
            "Orders": df["Order ID"].nunique()}
