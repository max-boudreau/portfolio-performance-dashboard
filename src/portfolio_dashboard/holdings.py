import pandas as pd
from .transactions import signed_transactions
from .validators import PortfolioDataError

def build_daily_holdings(transactions: pd.DataFrame, prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    tx = signed_transactions(transactions)
    all_dates = prices.index
    output = {}
    for portfolio in tx["portfolio_id"].unique():
        subset = tx[tx["portfolio_id"] == portfolio]
        holdings = pd.DataFrame(0.0, index=all_dates, columns=tx["ticker"].unique())
        for _, row in subset.iterrows():
            valid_dates = holdings.index[holdings.index >= row["trade_date"]]
            if len(valid_dates) == 0: continue
            holdings.loc[valid_dates, row["ticker"]] += row["signed_quantity"]
            if (holdings[row["ticker"]] < -1e-9).any():
                raise PortfolioDataError(f"{portfolio} sells more {row['ticker']} than it owns.")
        output[portfolio] = holdings.loc[:, (holdings.abs().sum(axis=0) > 0)]
    return output

def portfolio_values(holdings_by_portfolio: dict[str, pd.DataFrame], prices: pd.DataFrame) -> pd.DataFrame:
    values = {}
    for portfolio, holdings in holdings_by_portfolio.items():
        aligned = prices[holdings.columns].reindex(holdings.index).ffill()
        values[portfolio] = (holdings * aligned).sum(axis=1)
    df = pd.DataFrame(values)
    return df[df.sum(axis=1) > 0]
