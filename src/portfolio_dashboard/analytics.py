import numpy as np
import pandas as pd
from scipy import stats
from .config import TRADING_DAYS, RISK_FREE_RATE

def daily_returns(values: pd.DataFrame) -> pd.DataFrame:
    return values.pct_change().replace([np.inf, -np.inf], np.nan).dropna(how="all")
def annualized_return(r):
    r = r.dropna()
    if len(r) == 0: return np.nan
    return (1 + r).prod() ** (TRADING_DAYS / len(r)) - 1
def annualized_volatility(r): return r.dropna().std() * np.sqrt(TRADING_DAYS)
def sharpe_ratio(r, rf=RISK_FREE_RATE):
    vol = annualized_volatility(r)
    return np.nan if vol == 0 or np.isnan(vol) else (annualized_return(r) - rf) / vol
def max_drawdown(r):
    cumulative = (1 + r.dropna()).cumprod(); return (cumulative / cumulative.cummax() - 1).min()
def beta_alpha(portfolio_r, benchmark_r):
    df = pd.concat([portfolio_r, benchmark_r], axis=1).dropna(); df.columns = ["portfolio", "benchmark"]
    if len(df) < 30: return np.nan, np.nan, np.nan
    slope, intercept, r_value, _, _ = stats.linregress(df["benchmark"], df["portfolio"])
    return slope, intercept * TRADING_DAYS, r_value ** 2
def tracking_error(portfolio_r, benchmark_r): return (portfolio_r - benchmark_r).dropna().std() * np.sqrt(TRADING_DAYS)
def information_ratio(portfolio_r, benchmark_r):
    active = (portfolio_r - benchmark_r).dropna(); te = tracking_error(portfolio_r, benchmark_r)
    return np.nan if te == 0 or np.isnan(te) else active.mean() * TRADING_DAYS / te
def summary_table(portfolio_returns, benchmark_returns, primary_benchmark="SPY"):
    rows=[]; b=benchmark_returns[primary_benchmark].dropna()
    for portfolio in portfolio_returns.columns:
        p=portfolio_returns[portfolio].dropna(); beta, alpha, r2 = beta_alpha(p,b)
        rows.append({"Portfolio":portfolio,"Annualized Return":annualized_return(p),"Annualized Volatility":annualized_volatility(p),"Sharpe Ratio":sharpe_ratio(p),"Max Drawdown":max_drawdown(p),f"Beta vs {primary_benchmark}":beta,f"Annualized Alpha vs {primary_benchmark}":alpha,f"R-Squared vs {primary_benchmark}":r2,f"Tracking Error vs {primary_benchmark}":tracking_error(p,b),f"Information Ratio vs {primary_benchmark}":information_ratio(p,b)})
    return pd.DataFrame(rows)
