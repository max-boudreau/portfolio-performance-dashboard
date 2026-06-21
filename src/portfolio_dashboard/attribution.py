from __future__ import annotations

import numpy as np
import pandas as pd


def simple_benchmark_attribution(
    portfolio_name: str,
    holdings_by_portfolio: dict[str, pd.DataFrame],
    prices: pd.DataFrame,
    portfolio_returns: pd.DataFrame,
    benchmark_returns: pd.DataFrame,
    benchmark_ticker: str = "SPY",
) -> tuple[pd.DataFrame, dict]:
    """
    Simple benchmark attribution.

    This is not full Brinson attribution. It shows:
    - total return vs benchmark
    - active return
    - approximate current holding P&L contribution
    """
    if portfolio_name not in holdings_by_portfolio:
        return pd.DataFrame(), {}

    holdings = holdings_by_portfolio[portfolio_name]
    current = holdings.iloc[-1]
    current = current[current > 0]

    rows = []
    for ticker, quantity in current.items():
        if ticker not in prices.columns:
            continue

        owned_dates = holdings.index[holdings[ticker] > 0]
        if len(owned_dates) == 0:
            continue

        first_date = owned_dates[0]
        first_price = float(prices.loc[first_date:, ticker].dropna().iloc[0])
        latest_price = float(prices[ticker].dropna().iloc[-1])
        market_value = float(quantity) * latest_price
        pnl = float(quantity) * (latest_price - first_price)
        holding_return = (latest_price / first_price - 1) if first_price else np.nan

        rows.append(
            {
                "Ticker": ticker,
                "Quantity": float(quantity),
                "First Owned Date": first_date.date(),
                "First Price": first_price,
                "Latest Price": latest_price,
                "Market Value": market_value,
                "Approx Unrealized P&L": pnl,
                "Approx Holding Return": holding_return,
            }
        )

    attribution = pd.DataFrame(rows)
    if not attribution.empty:
        total_mv = attribution["Market Value"].sum()
        total_pnl = attribution["Approx Unrealized P&L"].sum()
        attribution["Current Weight"] = attribution["Market Value"] / total_mv if total_mv else np.nan
        attribution["P&L Contribution %"] = attribution["Approx Unrealized P&L"] / total_pnl if total_pnl else np.nan
        attribution = attribution.sort_values("Approx Unrealized P&L", ascending=False)

    p = portfolio_returns[portfolio_name].dropna()
    b = benchmark_returns[benchmark_ticker].dropna()
    aligned = pd.concat([p, b], axis=1).dropna()
    aligned.columns = ["portfolio", "benchmark"]

    if aligned.empty:
        summary = {}
    else:
        p_total = (1 + aligned["portfolio"]).prod() - 1
        b_total = (1 + aligned["benchmark"]).prod() - 1
        summary = {
            "Portfolio Total Return": p_total,
            "Benchmark Total Return": b_total,
            "Active Return": p_total - b_total,
            "Benchmark": benchmark_ticker,
        }

    return attribution, summary
