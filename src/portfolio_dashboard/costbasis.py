import pandas as pd
from .validators import validate_transactions

def average_cost_basis(transactions: pd.DataFrame, latest_prices: pd.Series) -> pd.DataFrame:
    tx = validate_transactions(transactions); rows=[]
    for (portfolio, ticker), subset in tx.groupby(["portfolio_id", "ticker"]):
        qty=0.0; cost=0.0
        for _, row in subset.sort_values("trade_date").iterrows():
            if row["side"] == "BUY": qty += row["quantity"]; cost += row["quantity"] * row["price"] + row["fees"]
            else:
                if qty <= 0: continue
                avg = cost / qty; qty -= row["quantity"]; cost -= row["quantity"] * avg
        if qty > 1e-9:
            latest=float(latest_prices[ticker]); mv=qty*latest
            rows.append({"Portfolio":portfolio,"Ticker":ticker,"Quantity":qty,"Average Cost":cost/qty,"Latest Price":latest,"Cost Basis":cost,"Market Value":mv,"Unrealized Gain/Loss":mv-cost,"Unrealized Return":(mv-cost)/cost if cost else None})
    return pd.DataFrame(rows)
