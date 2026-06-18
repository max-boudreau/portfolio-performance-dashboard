import pandas as pd
import yfinance as yf
class MarketDataError(RuntimeError): pass
def download_prices(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    if not tickers: raise MarketDataError("No tickers provided.")
    tickers = sorted(set([t.upper().strip() for t in tickers]))
    try:
        raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
        if raw.empty: raise MarketDataError("Yahoo Finance returned no data.")
        prices = raw["Close"] if "Close" in raw else raw
        if isinstance(prices, pd.Series): prices = prices.to_frame(name=tickers[0])
        prices = prices.ffill().dropna(how="all")
        available = [c for c in prices.columns if prices[c].notna().any()]
        prices = prices[available]
        missing = sorted(set(tickers) - set(available))
        if missing: raise MarketDataError(f"No usable price data for: {missing}")
        return prices
    except Exception as exc:
        if isinstance(exc, MarketDataError): raise
        raise MarketDataError(f"Price download failed: {exc}") from exc
