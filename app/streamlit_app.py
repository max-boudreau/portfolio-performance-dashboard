import sys
from pathlib import Path
from datetime import datetime

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

st.set_page_config(page_title="Portfolio Performance Analytics Dashboard", layout="wide")

st.title("Portfolio Performance Analytics Dashboard")
st.caption("Transaction-level multi-portfolio analytics with benchmarks, cost basis, risk metrics, snapshots, attribution, and admin-only editing.")

is_admin = admin_login()

with st.sidebar:
    st.header("Inputs")
    data_source = st.radio(
        "Data source",
        ["Supabase database", "CSV / sample file"],
        index=0 if supabase_configured() else 1,
    )
    uploaded = st.file_uploader("Upload transactions CSV", type=["csv"])
    use_sample = st.checkbox("Use sample transactions", value=True)
    primary_benchmark_name = st.selectbox("Primary benchmark", list(DEFAULT_BENCHMARKS.keys()), index=0)
    run_sector = st.checkbox("Fetch sector data", value=False, help="Uses Yahoo Finance metadata. This may be slower or rate-limited.")
    st.divider()
    st.caption("Required CSV columns:")
    st.code("portfolio_id, trade_date, ticker, side, quantity, price", language="text")


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


try:
    if data_source == "Supabase database":
        if not supabase_configured():
            st.error("Supabase is not configured in Streamlit Secrets. Switch to CSV / sample file or add secrets.")
            st.stop()
        raw_transactions = fetch_transactions_public()
        if raw_transactions.empty:
            st.warning("Supabase is connected, but no public transactions were found.")
            st.stop()
        transactions = validate_transactions(raw_transactions)
    else:
        if uploaded is not None:
            transactions = load_transactions(uploaded)
        elif use_sample:
            transactions = load_transactions(ROOT / "data" / "sample" / "sample_transactions.csv")
        else:
            st.info("Upload a transaction CSV or enable the sample dataset.")
            st.stop()

    asset_tickers = sorted(transactions["ticker"].unique())
    benchmark_tickers = list(DEFAULT_BENCHMARKS.values())
    all_tickers = sorted(set(asset_tickers + benchmark_tickers))

    start_date = transactions["trade_date"].min().strftime("%Y-%m-%d")
    end_date = datetime.today().strftime("%Y-%m-%d")

    with st.spinner("Loading market data..."):
        prices = download_prices(all_tickers, start_date, end_date)

    if prices.attrs.get("source") == "demo":
        st.warning("Yahoo Finance is currently unavailable or rate-limited. The app is using demo price data so the dashboard functionality remains visible.")

    holdings = build_daily_holdings(transactions, prices)
    values = portfolio_values(holdings, prices)

    if values.empty:
        st.error("No portfolio values were generated. Check transaction dates and tickers.")
        st.stop()

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
            latest_rows.append({"Portfolio": portfolio, "Ticker": ticker, "Quantity": quantity, "Latest Price": latest_price, "Market Value": quantity * latest_price})

    holdings_df = pd.DataFrame(latest_rows)
    cost_df = average_cost_basis(transactions, prices.iloc[-1])

    metric_cols = st.columns(4)
    metric_cols[0].metric("Total Market Value", f"${holdings_df['Market Value'].sum():,.0f}")
    metric_cols[1].metric("Portfolios", f"{holdings_df['Portfolio'].nunique()}")
    metric_cols[2].metric("Current Holdings", f"{len(holdings_df)}")
    metric_cols[3].metric("Average Sharpe", f"{summary['Sharpe Ratio'].mean():.2f}")

    st.subheader("Performance Summary")
    st.dataframe(format_summary_table(summary, primary_ticker), use_container_width=True)

    tab_names = ["Performance", "Benchmarks", "Risk", "Holdings & Cost Basis", "Attribution", "Snapshots", "Transactions", "Exports"]
    if is_admin:
        tab_names.append("Admin")
    tabs = st.tabs(tab_names)
    tab_map = dict(zip(tab_names, tabs))

    with tab_map["Performance"]:
        st.plotly_chart(plot_values(values), use_container_width=True)
        selected = st.selectbox("Select portfolio for monthly return heatmap", list(values.columns), key="monthly_heatmap_portfolio")
        st.plotly_chart(plot_monthly_heatmap(p_returns[selected], f"{selected} Monthly Returns"), use_container_width=True)

    with tab_map["Benchmarks"]:
        st.plotly_chart(plot_growth_of_100(values, benchmark_prices, blended_returns), use_container_width=True)

    with tab_map["Risk"]:
        st.plotly_chart(plot_drawdown(p_returns), use_container_width=True)

    with tab_map["Holdings & Cost Basis"]:
        st.subheader("Current Holdings")
        st.dataframe(holdings_df, use_container_width=True)

        st.subheader("Cost Basis and Unrealized Gain/Loss")
        st.dataframe(
            cost_df.style.format(
                {
                    "Average Cost": "${:,.2f}",
                    "Latest Price": "${:,.2f}",
                    "Cost Basis": "${:,.2f}",
                    "Market Value": "${:,.2f}",
                    "Unrealized Gain/Loss": "${:,.2f}",
                    "Unrealized Return": "{:.2%}",
                },
                na_rep="N/A",
            ),
            use_container_width=True,
        )

        selected_alloc = st.selectbox("Select portfolio for allocation", sorted(holdings_df["Portfolio"].unique()), key="allocation_portfolio")
        st.plotly_chart(plot_allocation(holdings_df, selected_alloc), use_container_width=True)

        if run_sector:
            with st.spinner("Fetching sector metadata..."):
                sector_map = get_sector_map(sorted(holdings_df["Ticker"].unique()))
                sector_df = sector_allocation(holdings_df, sector_map)
            st.plotly_chart(plot_sector_allocation(sector_df, selected_alloc), use_container_width=True)

    with tab_map["Attribution"]:
        st.subheader("Simple Benchmark Attribution")
        selected_attr = st.selectbox("Portfolio", sorted(holdings_df["Portfolio"].unique()), key="attr_portfolio")

        attr_df, attr_summary = simple_benchmark_attribution(
            portfolio_name=selected_attr,
            holdings_by_portfolio=holdings,
            prices=prices,
            portfolio_returns=p_returns,
            benchmark_returns=b_returns,
            benchmark_ticker=primary_ticker,
        )

        if attr_summary:
            c1, c2, c3 = st.columns(3)
            c1.metric("Portfolio Total Return", f"{attr_summary['Portfolio Total Return']:.2%}")
            c2.metric("Benchmark Total Return", f"{attr_summary['Benchmark Total Return']:.2%}")
            c3.metric("Active Return", f"{attr_summary['Active Return']:.2%}")

        if attr_df.empty:
            st.info("No attribution data available.")
        else:
            st.dataframe(
                attr_df.style.format(
                    {
                        "First Price": "${:,.2f}",
                        "Latest Price": "${:,.2f}",
                        "Market Value": "${:,.2f}",
                        "Approx Unrealized P&L": "${:,.2f}",
                        "Approx Holding Return": "{:.2%}",
                        "Current Weight": "{:.2%}",
                        "P&L Contribution %": "{:.2%}",
                    },
                    na_rep="N/A",
                ),
                use_container_width=True,
            )
            fig = px.bar(attr_df, x="Ticker", y="Approx Unrealized P&L", title=f"{selected_attr} Approximate P&L Contribution by Holding")
            st.plotly_chart(fig, use_container_width=True)

    with tab_map["Snapshots"]:
        st.subheader("Portfolio Snapshots")
        if data_source != "Supabase database":
            st.info("Snapshots require Supabase mode.")
        else:
            snapshots = fetch_snapshots_public()
            if snapshots.empty:
                st.info("No snapshots have been created yet. Admin users can create snapshots in the Admin tab.")
            else:
                st.dataframe(snapshots[["portfolio_id", "snapshot_date", "snapshot_name", "total_market_value", "notes"]], use_container_width=True)
                labels = snapshots.apply(lambda r: f"{r['portfolio_id']} | {r['snapshot_date']} | {r['snapshot_name']}", axis=1).tolist()
                selected_snapshot = st.selectbox("Select snapshot", labels)
                selected_idx = labels.index(selected_snapshot)
                snap = snapshots.iloc[selected_idx]

                st.markdown(f"**Notes:** {snap.get('notes') or ''}")
                if isinstance(snap.get("holdings_json"), list):
                    st.dataframe(pd.DataFrame(snap["holdings_json"]), use_container_width=True)
                if isinstance(snap.get("metrics_json"), dict):
                    st.json(snap["metrics_json"])

    with tab_map["Transactions"]:
        st.subheader("Transaction Ledger")
        st.caption("Public users can view transactions. Admin users can add/delete transactions in the Admin tab.")
        st.dataframe(transactions, use_container_width=True)
        st.download_button("Download transaction ledger CSV", transactions.to_csv(index=False), "transaction_ledger.csv", mime="text/csv")

    with tab_map["Exports"]:
        st.download_button("Download performance summary CSV", summary.to_csv(index=False), "portfolio_summary.csv", mime="text/csv")
        st.download_button("Download current holdings CSV", holdings_df.to_csv(index=False), "current_holdings.csv", mime="text/csv")
        st.download_button("Download cost basis CSV", cost_df.to_csv(index=False), "cost_basis.csv", mime="text/csv")
        st.download_button("Download daily portfolio values CSV", values.to_csv(), "portfolio_values.csv", mime="text/csv")

    if is_admin:
        with tab_map["Admin"]:
            if data_source != "Supabase database":
                st.warning("Admin database editing requires Supabase database mode.")
            else:
                render_admin_panel(transactions, holdings_df, summary)

except Exception as exc:
    st.error(f"App error: {exc}")
    st.exception(exc)
