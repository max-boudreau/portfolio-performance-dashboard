# Portfolio Performance Analytics Dashboard

Transaction-based portfolio analytics dashboard built in Python and Streamlit.

## What it does

- Tracks multiple portfolios from buy/sell transactions
- Reconstructs holdings and cost basis
- Compares performance against SPY, QQQ, TSX, and a blended benchmark
- Calculates alpha, beta, Sharpe ratio, volatility, drawdown, tracking error, and information ratio
- Displays allocation, cost basis, unrealized P&L, and optional sector exposure
- Exports CSV summaries

## How to run locally

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

## Transaction CSV format

Required columns:

```text
portfolio_id, owner, trade_date, ticker, side, quantity, price, fees, notes
```

Use `BUY` or `SELL` in the `side` column.

## Resume bullet

Built a transaction-based Portfolio Performance Analytics Dashboard in Python and Streamlit to track multiple portfolios from trade-level data, reconstruct holdings and cost basis, benchmark performance versus SPY, QQQ, TSX, and blended indices, and compute risk-adjusted metrics including alpha, beta, Sharpe ratio, volatility, drawdown, tracking error, and information ratio.
