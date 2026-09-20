"""
Run the SQL queries in queries.sql against the SQLite database (retail.db),
then use Pandas to segment customers (RFM), draw charts, and write a summary
of the numbers.

Usage:
    python build_db.py     # once, to create retail.db
    python analysis.py

Outputs:
    figures/*.png          charts
    outputs/*.csv          result tables
    outputs/findings.txt   summary of the numbers found
"""

import re
import sqlite3
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save figures to files, no window needed
import matplotlib.pyplot as plt
import pandas as pd

DB_PATH = Path("retail.db")
QUERY_FILE = Path("queries.sql")
FIG_DIR = Path("figures")
OUT_DIR = Path("outputs")


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------
def load_queries(path: Path) -> dict:
    """Split queries.sql into {name: sql} using the '-- name: xxx' markers."""
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.MULTILINE)
    # parts = [preamble, name1, body1, name2, body2, ...]
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def run(conn, sql: str) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn)


# ---------------------------------------------------------------------------
# RFM segmentation
# ---------------------------------------------------------------------------
def segment(row) -> str:
    if row["r_score"] >= 3 and row["f_score"] >= 3:
        return "Champions"
    if row["r_score"] <= 2 and row["f_score"] >= 3:
        return "Loyal but slipping"
    if row["r_score"] >= 3:
        return "Recent, low frequency"
    return "Lapsed"


SEGMENT_ORDER = ["Champions", "Recent, low frequency", "Loyal but slipping", "Lapsed"]


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG_DIR / name, dpi=150)
    plt.close(fig)


def chart_monthly_revenue(df):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(pd.to_datetime(df["month"]), df["revenue"], marker="o", color="#1F5FA8")
    ax.set_title("Monthly revenue (completed orders)")
    ax.set_ylabel("Revenue (THB)")
    ax.set_ylim(bottom=0)
    fig.autofmt_xdate()
    save(fig, "monthly_revenue.png")


def chart_category_share(df):
    fig, ax = plt.subplots(figsize=(7, 4))
    df.sort_values("revenue").plot(kind="barh", x="category_name", y="revenue", ax=ax, color="#1F5FA8", legend=False)
    ax.set_title("Revenue by category")
    ax.set_xlabel("Revenue (THB)")
    ax.set_ylabel("")
    save(fig, "revenue_by_category.png")


def chart_segments(summary):
    fig, ax = plt.subplots(figsize=(7, 4))
    summary["customers"].plot(kind="bar", ax=ax, color="#1F5FA8")
    ax.set_title("Customers by RFM segment")
    ax.set_ylabel("Customers")
    ax.set_xlabel("")
    plt.setp(ax.get_xticklabels(), rotation=15, ha="right")
    save(fig, "rfm_segments.png")


def chart_new_vs_returning(df):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = pd.to_datetime(df["month"]).dt.strftime("%b")
    ax.bar(labels, df["new_customers"], label="New", color="#1F5FA8")
    ax.bar(labels, df["returning_customers"], bottom=df["new_customers"], label="Returning", color="#9BB8D9")
    ax.set_title("Buying customers per month: new vs returning")
    ax.set_ylabel("Customers")
    ax.legend()
    save(fig, "new_vs_returning.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not QUERY_FILE.exists():
        sys.exit("queries.sql not found. Run this script from the project folder.")
    FIG_DIR.mkdir(exist_ok=True)
    OUT_DIR.mkdir(exist_ok=True)

    if not DB_PATH.exists():
        sys.exit("retail.db not found. Run: python build_db.py")
    conn = sqlite3.connect(DB_PATH)

    queries = load_queries(QUERY_FILE)
    results = {name: run(conn, sql) for name, sql in queries.items()}
    conn.close()

    for name, df in results.items():
        df.to_csv(OUT_DIR / f"{name}.csv", index=False)

    # RFM segments
    rfm = results["rfm"].copy()
    rfm["segment"] = rfm.apply(segment, axis=1)
    rfm.to_csv(OUT_DIR / "rfm_with_segments.csv", index=False)
    summary = (
        rfm.groupby("segment")
        .agg(customers=("customer_id", "size"), avg_orders=("frequency", "mean"), total_spend=("monetary", "sum"))
        .reindex(SEGMENT_ORDER)
        .dropna(how="all")
    )
    summary["share_of_revenue_pct"] = (100 * summary["total_spend"] / summary["total_spend"].sum()).round(1)
    summary["avg_orders"] = summary["avg_orders"].round(1)
    summary.to_csv(OUT_DIR / "segment_summary.csv")

    # Charts
    chart_monthly_revenue(results["monthly_revenue"])
    chart_category_share(results["category_share"])
    chart_segments(summary)
    chart_new_vs_returning(results["new_vs_returning"])

    # Findings (numbers only; you write the conclusions)
    monthly = results["monthly_revenue"]
    best = monthly.loc[monthly["revenue"].idxmax()]
    worst = monthly.loc[monthly["revenue"].idxmin()]
    top_cat = results["category_share"].iloc[0]
    repeat = results["repeat_rate"].iloc[0]
    gaps = results["days_between_orders"].iloc[0]
    pair = results["bought_together"].iloc[0]

    lines = [
        f"Total revenue (completed orders): {monthly['revenue'].sum():,.0f} THB across {int(monthly['orders'].sum()):,} orders.",
        f"Highest month: {best['month']} ({best['revenue']:,.0f} THB). Lowest month: {worst['month']} ({worst['revenue']:,.0f} THB).",
        f"Average order value: {monthly['revenue'].sum() / monthly['orders'].sum():,.1f} THB.",
        f"Top category: {top_cat['category_name']} ({top_cat['revenue_share_pct']}% of revenue).",
        f"Repeat purchase rate: {repeat['repeat_rate_pct']}% ({int(repeat['repeat_buyers'])} of {int(repeat['buyers'])} buyers ordered at least twice).",
        f"Days between orders: average {gaps['avg_days_between_orders']}, median {gaps['median_days_between_orders']}.",
        f"Most common product pair: {pair['product_a']} + {pair['product_b']} ({int(pair['orders_together'])} orders).",
        "",
        "RFM segments:",
    ]
    for name, row in summary.iterrows():
        lines.append(
            f"  {name}: {int(row['customers'])} customers, {row['avg_orders']} orders on average, "
            f"{row['share_of_revenue_pct']}% of revenue."
        )
    (OUT_DIR / "findings.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    print(f"\nSaved charts to {FIG_DIR}/ and tables to {OUT_DIR}/")


if __name__ == "__main__":
    main()
