import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from portfolio_dashboard.config import DEFAULT_BENCHMARKS, DEFAULT_BLEND
from portfolio_dashboard.transactions import load_transactions
from portfolio_dashboard.validators import validate_transactions
from portfolio_dashboard.market_data import download_prices
from portfolio_dashboard.holdings import build_daily_holdings, portfolio_values
from portfolio_dashboard.analytics import daily_returns, summary_table
from portfolio_dashboard.benchmarks import build_blended_benchmark
from portfolio_dashboard.costbasis import average_cost_basis
from portfolio_dashboard.sectors import get_sector_map, sector_allocation
from portfolio_dashboard.plots import (
    plot_values,
    plot_growth_of_100,
    plot_drawdown,
    plot_allocation,
    plot_sector_allocation,
    plot_monthly_heatmap,
)
from portfolio_dashboard.db import supabase_configured, fetch_transactions_public
from portfolio_dashboard.admin import admin_login, render_admin_panel
from portfolio_dashboard.snapshots import fetch_snapshots_public
from portfolio_dashboard.attribution import simple_benchmark_attribution

st.set_page_config(page_title="Portfolio Performance Analytics Dashboard", page_icon="📈", layout="wide")

st.markdown(
    """
<style>
.block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1280px;}
[data-testid="stMetricValue"] {font-size: 1.75rem;}
div[data-testid="stHorizontalBlock"] > div {min-width: 0;}
.dashboard-card {border: 1px solid rgba(120,140,170,.28); border-radius: 18px; padding: 18px; background: linear-gradient(180deg, rgba(255,255,255,.035), rgba(255,255,255,.015)); min-height: 175px;}
.dashboard-card h3 {margin: 0 0 8px 0; font-size: 1.05rem;}
.dashboard-card .big {font-size: 1.55rem; font-weight: 800; margin: 4px 0;}
.dashboard-card .muted {color: rgba(250,250,250,.64); font-size: .88rem; margin-top: 6px;}
.pill {display: inline-block; padding: 3px 9px; border-radius: 999px; border: 1px solid rgba(120,140,170,.35); font-size: .78rem; color: rgba(250,250,250,.70); margin: 2px 4px 2px 0;}
.section-caption {color: rgba(250,250,250,.66); margin-top: -.45rem; margin-bottom: 1.1rem;}
hr {margin-top: 1.5rem; margin-bottom: 1.5rem;}
</style>
""",
    unsafe_allow_html=True,
)


def money(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"${float(value):,.0f}"
    except Exception:
        return "N/A"


def pct(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.2%}"
    except Exception:
        return "N/A"


def num(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.2f}"
    except Exception:
        return "N/A"


def clean_metric_value(value):
    try:
        if value is None or pd.isna(value):
            return np.nan
        return float(value)
    except Exception:
        return np.nan


def format_summary_table(df: pd.DataFrame, primary_ticker: str):
    format_map = {
        "Annualized Return": "{:.2%}",
        "Annualized Volatility": "{:.2%}",
        "Sharpe Ratio": "{:.2f}",
        "Max Drawdown": "{:.2%}",
        f"Beta vs {primary_ticker}": "{:.2f}",
        f"Annualized Alpha vs {primary_ticker}": "{:.2%}",
        f"R-Squared vs {primary_ticker}": "{:.2f}",
        f"Tracking Error vs {primary_ticker}": "{:.2%}",
        f"Information Ratio vs {primary_ticker}": "{:.2f}",
    }
    return df.style.format(format_map, na_rep="N/A")


def render_page_title(title: str, caption: str | None = None):
    st.title(title)
    if caption:
        st.markdown(f"<div class='section-caption'>{caption}</div>", unsafe_allow_html=True)


@st.cache_data(ttl=45, show_spinner=False)
def load_dashboard_data(data_source, uploaded_file, use_sample, primary_benchmark_name):
    if data_source == "Supabase database":
        if not supabase_configured():
            raise RuntimeError("Supabase is not configured in Streamlit Secrets.")
        raw_transactions = fetch_transactions_public()
        if raw_transactions.empty:
            raise RuntimeError("Supabase is connected, but no public transactions were found.")
        transactions = validate_transactions(raw_transactions)
    else:
        if uploaded_file is not None:
            transactions = load_transactions(uploaded_file)
        elif use_sample:
            transactions = load_transactions(ROOT / "data" / "sample" / "sample_transactions.csv")
        else:
            raise RuntimeError("Upload a transaction CSV or enable the sample dataset.")

    asset_tickers = sorted(transactions["ticker"].unique())
    benchmark_tickers = list(DEFAULT_BENCHMARKS.values())
    all_tickers = sorted(set(asset_tickers + benchmark_tickers))

    start_date = transactions["trade_date"].min().strftime("%Y-%m-%d")
    end_date = datetime.today().strftime("%Y-%m-%d")
    prices = download_prices(all_tickers, start_date, end_date)

    holdings = build_daily_holdings(transactions, prices)
    values = portfolio_values(holdings, prices)
    if values.empty:
        raise RuntimeError("No portfolio values were generated. Check transaction dates and tickers.")

    p_returns = daily_returns(values)
    benchmark_prices = prices[benchmark_tickers]
    b_returns = benchmark_prices.pct_change().dropna()
    blended_returns = build_blended_benchmark(benchmark_prices, DEFAULT_BLEND)
    b_returns["Blended Benchmark"] = blended_returns

    primary_ticker = DEFAULT_BENCHMARKS[primary_benchmark_name]
    summary = summary_table(p_returns, b_returns, primary_ticker)

    latest_rows = []
    for portfolio, h in holdings.items():
        current = h.iloc[-1]
        current = current[current > 0]
        for ticker, quantity in current.items():
            latest_price = float(prices[ticker].iloc[-1])
            latest_rows.append({"Portfolio": portfolio, "Ticker": ticker, "Quantity": float(quantity), "Latest Price": latest_price, "Market Value": float(quantity) * latest_price})

    holdings_df = pd.DataFrame(latest_rows)
    cost_df = average_cost_basis(transactions, prices.iloc[-1])

    return {"transactions": transactions, "prices": prices, "holdings": holdings, "values": values, "p_returns": p_returns, "benchmark_prices": benchmark_prices, "b_returns": b_returns, "blended_returns": blended_returns, "primary_ticker": primary_ticker, "summary": summary, "holdings_df": holdings_df, "cost_df": cost_df, "using_demo_prices": prices.attrs.get("source") == "demo"}


def portfolio_card(portfolio, holdings_df, summary_df):
    p_holdings = holdings_df[holdings_df["Portfolio"] == portfolio].copy()
    row = summary_df[summary_df["Portfolio"] == portfolio]
    market_value = p_holdings["Market Value"].sum() if not p_holdings.empty else np.nan
    if row.empty:
        ret = sharpe = dd = np.nan
    else:
        record = row.iloc[0]
        ret = clean_metric_value(record.get("Annualized Return"))
        sharpe = clean_metric_value(record.get("Sharpe Ratio"))
        dd = clean_metric_value(record.get("Max Drawdown"))
    top_holdings = p_holdings.sort_values("Market Value", ascending=False)["Ticker"].head(3).tolist() if not p_holdings.empty else []
    top_holdings_html = "".join([f"<span class='pill'>{t}</span>" for t in top_holdings]) or "<span class='pill'>No holdings</span>"
    st.markdown(f"""
        <div class="dashboard-card">
            <h3>{portfolio}</h3>
            <div class="big">{money(market_value)}</div>
            <div class="muted">Market value</div>
            <div style="margin-top:12px;">
                <span class="pill">Return: {pct(ret)}</span>
                <span class="pill">Sharpe: {num(sharpe)}</span>
                <span class="pill">Max DD: {pct(dd)}</span>
            </div>
            <div class="muted" style="margin-top:10px;">Top holdings</div>
            <div>{top_holdings_html}</div>
        </div>
    """, unsafe_allow_html=True)


def overview_page(data):
    render_page_title("Portfolio Overview", "High-level dashboard with summary metrics, portfolio cards, and performance comparison.")
    holdings_df, summary, values = data["holdings_df"], data["summary"], data["values"]
    total_market_value = holdings_df["Market Value"].sum() if not holdings_df.empty else 0
    portfolio_count = holdings_df["Portfolio"].nunique() if not holdings_df.empty else 0
    current_holdings = len(holdings_df)
    best = summary.sort_values("Annualized Return", ascending=False).iloc[0]["Portfolio"] if not summary.empty and "Annualized Return" in summary.columns else "N/A"
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Market Value", money(total_market_value))
    c2.metric("Portfolios", f"{portfolio_count}")
    c3.metric("Current Holdings", f"{current_holdings}")
    c4.metric("Best Performer", str(best))
    st.divider()
    st.subheader("Portfolio Cards")
    portfolios = sorted(holdings_df["Portfolio"].unique()) if not holdings_df.empty else []
    for i in range(0, len(portfolios), 3):
        cols = st.columns(3)
        for col, portfolio in zip(cols, portfolios[i:i+3]):
            with col:
                portfolio_card(portfolio, holdings_df, summary)
    st.divider()
    st.subheader("Portfolio Value Over Time")
    st.plotly_chart(plot_values(values), use_container_width=True)
    with st.expander("View full performance summary table"):
        st.dataframe(format_summary_table(summary, data["primary_ticker"]), use_container_width=True)


def portfolio_detail_page(data):
    render_page_title("Portfolio Detail", "Select one portfolio to analyze holdings, allocation, returns, benchmark performance, risk, attribution, and snapshots.")
    holdings_df, summary, values = data["holdings_df"], data["summary"], data["values"]
    p_returns, benchmark_prices, b_returns = data["p_returns"], data["benchmark_prices"], data["b_returns"]
    blended_returns, holdings, prices = data["blended_returns"], data["holdings"], data["prices"]
    cost_df, primary_ticker = data["cost_df"], data["primary_ticker"]
    portfolios = sorted(holdings_df["Portfolio"].unique()) if not holdings_df.empty else []
    if not portfolios:
        st.info("No portfolios available.")
        return
    selected = st.selectbox("Select portfolio", portfolios, key="portfolio_detail_selector")
    p_holdings = holdings_df[holdings_df["Portfolio"] == selected].copy()
    p_summary = summary[summary["Portfolio"] == selected]
    p_cost = cost_df[cost_df["Portfolio"] == selected].copy() if "Portfolio" in cost_df.columns else pd.DataFrame()
    record = p_summary.iloc[0] if not p_summary.empty else {}
    market_value = p_holdings["Market Value"].sum() if not p_holdings.empty else np.nan
    ann_return = clean_metric_value(record.get("Annualized Return", np.nan)) if len(record) else np.nan
    volatility = clean_metric_value(record.get("Annualized Volatility", np.nan)) if len(record) else np.nan
    sharpe = clean_metric_value(record.get("Sharpe Ratio", np.nan)) if len(record) else np.nan
    max_dd = clean_metric_value(record.get("Max Drawdown", np.nan)) if len(record) else np.nan
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Market Value", money(market_value)); c2.metric("Annualized Return", pct(ann_return)); c3.metric("Volatility", pct(volatility)); c4.metric("Sharpe", num(sharpe)); c5.metric("Max Drawdown", pct(max_dd))
    st.divider()
    section = st.radio("View", ["Performance", "Holdings", "Risk", "Attribution", "Snapshots"], horizontal=True, key="portfolio_detail_section")
    if section == "Performance":
        left, right = st.columns([1.2, .8])
        with left:
            st.subheader("Portfolio Value")
            st.plotly_chart(plot_values(values[[selected]]), use_container_width=True)
        with right:
            st.subheader("Monthly Returns")
            if selected in p_returns.columns:
                st.plotly_chart(plot_monthly_heatmap(p_returns[selected], f"{selected} Monthly Returns"), use_container_width=True)
        st.subheader("Growth of $100 vs Benchmarks")
        st.plotly_chart(plot_growth_of_100(values[[selected]], benchmark_prices, blended_returns), use_container_width=True)
    elif section == "Holdings":
        st.subheader("Current Holdings")
        st.dataframe(p_holdings.style.format({"Quantity":"{:,.4f}", "Latest Price":"${:,.2f}", "Market Value":"${:,.2f}"}, na_rep="N/A"), use_container_width=True)
        st.subheader("Allocation")
        st.plotly_chart(plot_allocation(holdings_df, selected), use_container_width=True)
        st.subheader("Cost Basis and Unrealized Gain/Loss")
        if p_cost.empty:
            st.info("Cost basis data is not available for this portfolio.")
        else:
            st.dataframe(p_cost.style.format({"Average Cost":"${:,.2f}", "Latest Price":"${:,.2f}", "Cost Basis":"${:,.2f}", "Market Value":"${:,.2f}", "Unrealized Gain/Loss":"${:,.2f}", "Unrealized Return":"{:.2%}"}, na_rep="N/A"), use_container_width=True)
    elif section == "Risk":
        st.subheader("Drawdown")
        if selected in p_returns.columns:
            st.plotly_chart(plot_drawdown(p_returns[[selected]]), use_container_width=True)
        st.subheader("Risk Metrics")
        if p_summary.empty: st.info("No risk metrics available.")
        else: st.dataframe(format_summary_table(p_summary, primary_ticker), use_container_width=True)
    elif section == "Attribution":
        st.subheader("Simple Benchmark Attribution")
        attr_df, attr_summary = simple_benchmark_attribution(selected, holdings, prices, p_returns, b_returns, primary_ticker)
        if attr_summary:
            c1, c2, c3 = st.columns(3); c1.metric("Portfolio Total Return", pct(attr_summary.get("Portfolio Total Return"))); c2.metric("Benchmark Total Return", pct(attr_summary.get("Benchmark Total Return"))); c3.metric("Active Return", pct(attr_summary.get("Active Return")))
        if attr_df.empty:
            st.info("No attribution data available.")
        else:
            st.dataframe(attr_df.style.format({"First Price":"${:,.2f}", "Latest Price":"${:,.2f}", "Market Value":"${:,.2f}", "Approx Unrealized P&L":"${:,.2f}", "Approx Holding Return":"{:.2%}", "Current Weight":"{:.2%}", "P&L Contribution %":"{:.2%}"}, na_rep="N/A"), use_container_width=True)
            fig = px.bar(attr_df, x="Ticker", y="Approx Unrealized P&L", title=f"{selected} Approximate P&L Contribution by Holding")
            st.plotly_chart(fig, use_container_width=True)
    elif section == "Snapshots":
        st.subheader("Portfolio Snapshots")
        snapshots = fetch_snapshots_public()
        if snapshots.empty:
            st.info("No snapshots have been created yet."); return
        p_snaps = snapshots[snapshots["portfolio_id"] == selected].copy()
        if p_snaps.empty:
            st.info(f"No snapshots found for {selected}."); return
        st.dataframe(p_snaps[["snapshot_date", "snapshot_name", "total_market_value", "notes"]], use_container_width=True)
        labels = p_snaps.apply(lambda r: f"{r['snapshot_date']} | {r['snapshot_name']}", axis=1).tolist()
        selected_snapshot = st.selectbox("Select snapshot", labels)
        snap = p_snaps.iloc[labels.index(selected_snapshot)]
        st.markdown(f"**Notes:** {snap.get('notes') or ''}")
        if isinstance(snap.get("holdings_json"), list):
            st.subheader("Snapshot Holdings"); st.dataframe(pd.DataFrame(snap["holdings_json"]), use_container_width=True)
        if isinstance(snap.get("metrics_json"), dict):
            st.subheader("Snapshot Metrics"); st.json(snap["metrics_json"])


def transactions_page(data):
    render_page_title("Transactions", "Read-only ledger of the transactions used to calculate holdings and performance.")
    transactions = data["transactions"].copy()
    portfolios = ["All"] + sorted(transactions["portfolio_id"].unique().tolist())
    selected = st.selectbox("Filter by portfolio", portfolios)
    if selected != "All": transactions = transactions[transactions["portfolio_id"] == selected]
    st.dataframe(transactions, use_container_width=True)
    st.download_button("Download transaction ledger CSV", transactions.to_csv(index=False), "transaction_ledger.csv", mime="text/csv")


def methodology_page(data):
    render_page_title("Methodology", "Definitions and calculation notes for the dashboard's portfolio analytics.")
    st.markdown("""
### Return calculation
Portfolio value is calculated from transaction-level holdings multiplied by daily closing prices. Daily portfolio returns are calculated from the change in portfolio value.

### Risk metrics
- **Annualized Return:** compounded daily return annualized over a 252-trading-day year.
- **Annualized Volatility:** standard deviation of daily returns multiplied by √252.
- **Sharpe Ratio:** annualized excess return divided by annualized volatility.
- **Maximum Drawdown:** largest peak-to-trough portfolio decline.
- **Beta:** portfolio sensitivity to the selected benchmark.
- **Alpha:** annualized excess return not explained by benchmark exposure.
- **Tracking Error:** annualized standard deviation of active returns.
- **Information Ratio:** active return divided by tracking error.

### Attribution
Current attribution is a simplified holding-level contribution view. It is not yet full Brinson attribution.

### Data notes
The app can fall back to demo price data when Yahoo Finance is unavailable or rate-limited. The production version should read daily prices from Supabase first.
""")


def admin_console_page(data):
    render_page_title("Admin Console", "Admin-only tools for portfolio creation, transaction management, imports, visibility controls, and snapshots.")
    render_admin_panel(data["transactions"], data["holdings_df"], data["summary"])


is_admin = admin_login()
with st.sidebar:
    st.divider(); st.header("Navigation")
    nav_options = ["Overview", "Portfolio Detail", "Transactions", "Methodology"]
    if is_admin: nav_options.append("Admin Console")
    page = st.radio("Go to", nav_options, label_visibility="collapsed")
    st.divider(); st.header("Dashboard Settings")
    primary_benchmark_name = st.selectbox("Primary benchmark", list(DEFAULT_BENCHMARKS.keys()), index=0)
    default_source = "Supabase database" if supabase_configured() else "CSV / sample file"
    if is_admin:
        data_source = st.radio("Data source", ["Supabase database", "CSV / sample file"], index=0 if default_source == "Supabase database" else 1)
    else:
        data_source = default_source
    uploaded = None; use_sample = False
    if data_source == "CSV / sample file":
        st.warning("CSV mode is mainly for development/testing.")
        uploaded = st.file_uploader("Upload transactions CSV", type=["csv"])
        use_sample = st.checkbox("Use sample transactions", value=True)
    if is_admin:
        with st.expander("Developer options"):
            st.caption("Required CSV columns:")
            st.code("portfolio_id, trade_date, ticker, side, quantity, price", language="text")

try:
    data = load_dashboard_data(data_source, uploaded, use_sample, primary_benchmark_name)
    if data["using_demo_prices"]:
        st.sidebar.warning("Using demo price data because Yahoo Finance is unavailable or rate-limited.")
    if page == "Overview": overview_page(data)
    elif page == "Portfolio Detail": portfolio_detail_page(data)
    elif page == "Transactions": transactions_page(data)
    elif page == "Methodology": methodology_page(data)
    elif page == "Admin Console":
        if not is_admin: st.error("Admin access required.")
        else: admin_console_page(data)
except Exception as exc:
    st.error(f"App error: {exc}")
    st.exception(exc)
