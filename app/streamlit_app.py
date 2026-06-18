import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st
ROOT = Path(__file__).resolve().parents[1]; SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))
from portfolio_dashboard.config import DEFAULT_BENCHMARKS, DEFAULT_BLEND
from portfolio_dashboard.transactions import load_transactions
from portfolio_dashboard.market_data import download_prices, MarketDataError
from portfolio_dashboard.holdings import build_daily_holdings, portfolio_values
from portfolio_dashboard.analytics import daily_returns, summary_table
from portfolio_dashboard.benchmarks import build_blended_benchmark
from portfolio_dashboard.costbasis import average_cost_basis
from portfolio_dashboard.sectors import get_sector_map, sector_allocation
from portfolio_dashboard.plots import plot_values, plot_growth_of_100, plot_drawdown, plot_allocation, plot_sector_allocation, plot_monthly_heatmap
st.set_page_config(page_title="Portfolio Performance Analytics Dashboard", layout="wide")
st.title("Portfolio Performance Analytics Dashboard")
st.caption("Transaction-level multi-portfolio analytics with benchmarks, cost basis, risk metrics, and sector exposure.")
with st.sidebar:
    st.header("Inputs")
    uploaded = st.file_uploader("Upload transactions CSV", type=["csv"])
    use_sample = st.checkbox("Use sample transactions", value=True)
    primary_benchmark_name = st.selectbox("Primary benchmark", list(DEFAULT_BENCHMARKS.keys()), index=0)
    run_sector = st.checkbox("Fetch sector data", value=False, help="Uses Yahoo Finance metadata. This can be slower.")
try:
    if uploaded is not None: transactions = load_transactions(uploaded)
    elif use_sample: transactions = load_transactions(ROOT / "data" / "sample" / "sample_transactions.csv")
    else: st.info("Upload a transaction CSV or enable the sample dataset."); st.stop()
    st.subheader("Transaction Ledger"); st.dataframe(transactions, use_container_width=True)
    asset_tickers = sorted(transactions["ticker"].unique()); benchmark_tickers=list(DEFAULT_BENCHMARKS.values()); all_tickers=sorted(set(asset_tickers+benchmark_tickers))
    start_date=transactions["trade_date"].min().strftime("%Y-%m-%d"); end_date=datetime.today().strftime("%Y-%m-%d")
    with st.spinner("Downloading market data..."): prices=download_prices(all_tickers, start_date, end_date)
    holdings=build_daily_holdings(transactions, prices); values=portfolio_values(holdings, prices); p_returns=daily_returns(values)
    benchmark_prices=prices[benchmark_tickers]; b_returns=benchmark_prices.pct_change().dropna(); blended_returns=build_blended_benchmark(benchmark_prices, DEFAULT_BLEND); b_returns["Blended Benchmark"]=blended_returns
    primary_ticker=DEFAULT_BENCHMARKS[primary_benchmark_name]; summary=summary_table(p_returns, b_returns, primary_ticker)
    latest_rows=[]
    for portfolio, h in holdings.items():
        current=h.iloc[-1]; current=current[current>0]
        for ticker, quantity in current.items():
            latest_price=float(prices[ticker].iloc[-1]); latest_rows.append({"Portfolio":portfolio,"Ticker":ticker,"Quantity":quantity,"Latest Price":latest_price,"Market Value":quantity*latest_price})
    holdings_df=pd.DataFrame(latest_rows); cost_df=average_cost_basis(transactions, prices.iloc[-1])
    st.subheader("Performance Summary"); st.dataframe(summary, use_container_width=True)
    tab1,tab2,tab3,tab4,tab5=st.tabs(["Performance","Benchmarks","Risk","Holdings","Exports"])
    with tab1:
        st.plotly_chart(plot_values(values), use_container_width=True)
        selected=st.selectbox("Select portfolio for monthly heatmap", list(values.columns))
        st.plotly_chart(plot_monthly_heatmap(p_returns[selected], f"{selected} Monthly Returns"), use_container_width=True)
    with tab2: st.plotly_chart(plot_growth_of_100(values, benchmark_prices, blended_returns), use_container_width=True)
    with tab3: st.plotly_chart(plot_drawdown(p_returns), use_container_width=True)
    with tab4:
        st.dataframe(holdings_df, use_container_width=True); st.dataframe(cost_df, use_container_width=True)
        selected_alloc=st.selectbox("Select portfolio for allocation", sorted(holdings_df["Portfolio"].unique()))
        st.plotly_chart(plot_allocation(holdings_df, selected_alloc), use_container_width=True)
        if run_sector:
            sector_df=sector_allocation(holdings_df, get_sector_map(sorted(holdings_df["Ticker"].unique())))
            st.plotly_chart(plot_sector_allocation(sector_df, selected_alloc), use_container_width=True)
    with tab5:
        st.download_button("Download performance summary CSV", summary.to_csv(index=False), "portfolio_summary.csv")
        st.download_button("Download current holdings CSV", holdings_df.to_csv(index=False), "current_holdings.csv")
        st.download_button("Download cost basis CSV", cost_df.to_csv(index=False), "cost_basis.csv")
        st.download_button("Download daily portfolio values CSV", values.to_csv(), "portfolio_values.csv")
except MarketDataError as exc: st.error(f"Market data error: {exc}")
except Exception as exc: st.error(f"App error: {exc}")
