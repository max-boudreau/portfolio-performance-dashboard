import yfinance as yf

def get_sector_map(tickers):
    out={}
    for ticker in tickers:
        try: out[ticker] = yf.Ticker(ticker).info.get("sector", "Unknown")
        except Exception: out[ticker] = "Unknown"
    return out

def sector_allocation(holdings_df, sector_map):
    df=holdings_df.copy(); df["Sector"] = df["Ticker"].map(sector_map).fillna("Unknown")
    out=df.groupby(["Portfolio","Sector"], as_index=False)["Market Value"].sum()
    out["Weight"] = out["Market Value"] / out.groupby("Portfolio")["Market Value"].transform("sum")
    return out
