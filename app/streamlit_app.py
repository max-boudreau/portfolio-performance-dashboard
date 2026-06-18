import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from portfolio_dashboard.config import DEFAULT_BENCHMARKS, DEFAULT_BLEND
from portfolio_dashboard.transactions import load_transactions
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

st.set_page_config(
    page_title="Portfolio Performance Analytics Dashboard",
    layout="wide",
)

st.title("Portfolio Performance Analytics Dashboard")
st.caption(
    "Transaction-level multi-portfolio analytics with benchmarks, cost basis, "
    "risk metrics, and sector exposure."
)

with st.sidebar:
    st.header("Inputs")
    uploaded = st.file_uploader("Upload transactions CSV", type=["csv"])
    use_sample = st.checkbox("Use sample transactions", value=True)

    primary_benchmark_name = st.selectbox(
        "Primary benchmark",
        list(DEFAULT_BENCHMARKS.keys()),
        index=0,
    )

    run_sector = st.checkbox(
        "Fetch sector data",
        value=False,
        help="Uses Yahoo Finance metadata. This may be slower or rate-limited.",
    )

    st.divider()
    st.caption("Required CSV columns:")
    st.code("portfolio_id, trade_date, ticker, side, quantity, price", language="text")


def format_summary_table(df: pd.DataFrame, primary_ticker: str):
    """Apply readable formatting to the metrics table."""
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
    if uploaded is not None:
        transactions = load_transactions(uploaded)
    elif use_sample:
        transactions = load_transactions(ROOT / "data" / "sample" / "sample_transactions.csv")
    else:
        st.info("Upload a transaction CSV or enable the sample dataset.")
        st.stop()

    st.subheader("Transaction Ledger")
    st.dataframe(transactions, use_container_width=True)

    asset_tickers = sorted(transactions["ticker"].unique())
    benchmark_tickers = list(DEFAULT_BENCHMARKS.values())
    all_tickers = sorted(set(asset_tickers + benchmark_tickers))

    start_date = transactions["trade_date"].min().strftime("%Y-%m-%d")
    end_date = datetime.today().strftime("%Y-%m-%d")

    with st.spinner("Loading market data..."):
        prices = download_prices(all_tickers, start_date, end_date)

    if prices.attrs.get("source") == "demo":
        st.warning(
            "Yahoo Finance is currently unavailable or rate-limited. The app is using "
            "demo price data so the dashboard functionality remains visible."
        )

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
            latest_rows.append(
                {
                    "Portfolio": portfolio,
                    "Ticker": ticker,
                    "Quantity": quantity,
                    "Latest Price": latest_price,
                    "Market Value": quantity * latest_price,
                }
            )

    holdings_df = pd.DataFrame(latest_rows)
    cost_df = average_cost_basis(transactions, prices.iloc[-1])

    metric_cols = st.columns(4)

    total_market_value = holdings_df["Market Value"].sum()
    portfolio_count = holdings_df["Portfolio"].nunique()
    holding_count = len(holdings_df)
    avg_sharpe = summary["Sharpe Ratio"].mean()

    metric_cols[0].metric("Total Market Value", f"${total_market_value:,.0f}")
    metric_cols[1].metric("Portfolios", f"{portfolio_count}")
    metric_cols[2].metric("Current Holdings", f"{holding_count}")
    metric_cols[3].metric("Average Sharpe", f"{avg_sharpe:.2f}")

    st.subheader("Performance Summary")
    st.dataframe(format_summary_table(summary, primary_ticker), use_container_width=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Performance", "Benchmarks", "Risk", "Holdings & Cost Basis", "Exports"]
    )

    with tab1:
        st.plotly_chart(plot_values(values), use_container_width=True)

        selected = st.selectbox(
            "Select portfolio for monthly return heatmap",
            list(values.columns),
            key="monthly_heatmap_portfolio",
        )
        st.plotly_chart(
            plot_monthly_heatmap(p_returns[selected], f"{selected} Monthly Returns"),
            use_container_width=True,
        )

    with tab2:
        st.plotly_chart(
            plot_growth_of_100(values, benchmark_prices, blended_returns),
            use_container_width=True,
        )

    with tab3:
        st.plotly_chart(plot_drawdown(p_returns), use_container_width=True)

    with tab4:
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

        selected_alloc = st.selectbox(
            "Select portfolio for allocation",
            sorted(holdings_df["Portfolio"].unique()),
            key="allocation_portfolio",
        )

        st.plotly_chart(plot_allocation(holdings_df, selected_alloc), use_container_width=True)

        if run_sector:
            with st.spinner("Fetching sector metadata..."):
                sector_map = get_sector_map(sorted(holdings_df["Ticker"].unique()))
                sector_df = sector_allocation(holdings_df, sector_map)

            st.plotly_chart(
                plot_sector_allocation(sector_df, selected_alloc),
                use_container_width=True,
            )

    with tab5:
        st.download_button(
            "Download performance summary CSV",
            summary.to_csv(index=False),
            "portfolio_summary.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download current holdings CSV",
            holdings_df.to_csv(index=False),
            "current_holdings.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download cost basis CSV",
            cost_df.to_csv(index=False),
            "cost_basis.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download daily portfolio values CSV",
            values.to_csv(),
            "portfolio_values.csv",
            mime="text/csv",
        )

except Exception as exc:
    st.error(f"App error: {exc}")
    st.exception(exc)
