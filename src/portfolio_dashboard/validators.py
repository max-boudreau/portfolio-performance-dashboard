import pandas as pd
REQUIRED_COLUMNS = ["portfolio_id", "trade_date", "ticker", "side", "quantity", "price"]
class PortfolioDataError(ValueError):
    """Raised when portfolio input data is invalid."""
def validate_transactions(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing: raise PortfolioDataError(f"Missing required columns: {missing}")
    clean = df.copy()
    clean["trade_date"] = pd.to_datetime(clean["trade_date"], errors="coerce")
    clean["ticker"] = clean["ticker"].astype(str).str.upper().str.strip()
    clean["side"] = clean["side"].astype(str).str.upper().str.strip()
    clean["quantity"] = pd.to_numeric(clean["quantity"], errors="coerce")
    clean["price"] = pd.to_numeric(clean["price"], errors="coerce")
    if "fees" not in clean.columns: clean["fees"] = 0.0
    clean["fees"] = pd.to_numeric(clean["fees"], errors="coerce").fillna(0.0)
    if clean["trade_date"].isna().any(): raise PortfolioDataError("Some trade_date values could not be parsed.")
    if not clean["side"].isin(["BUY", "SELL"]).all(): raise PortfolioDataError("side must be BUY or SELL.")
    if (clean["quantity"] <= 0).any(): raise PortfolioDataError("All quantities must be positive numbers.")
    if (clean["price"] <= 0).any(): raise PortfolioDataError("All prices must be positive numbers.")
    return clean.sort_values(["portfolio_id", "trade_date", "ticker"]).reset_index(drop=True)
