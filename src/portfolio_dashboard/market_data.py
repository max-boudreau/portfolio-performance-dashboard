from __future__ import annotations

import hashlib
import time
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf


class MarketDataError(RuntimeError):
    """Raised when market data cannot be downloaded or generated."""


def _normalize_tickers(tickers: list[str]) -> list[str]:
    """Clean and de-duplicate ticker symbols."""
    return sorted(set(str(t).upper().strip() for t in tickers if str(t).strip()))


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def download_prices(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """
    Download adjusted close prices from Yahoo Finance.

    Defensive sequence:
    1. Batch download
    2. One-ticker-at-a-time download
    3. Deterministic demo data fallback if Yahoo rate-limits Streamlit Cloud
    """
    tickers = _normalize_tickers(tickers)

    if not tickers:
        raise MarketDataError("No tickers provided.")

    try:
        raw = yf.download(
            tickers=tickers,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        prices = _extract_close_prices(raw, tickers)

        if _is_valid_price_frame(prices):
            prices = prices.ffill().dropna(how="all")
            prices.attrs["source"] = "yahoo"
            return prices

    except Exception:
        pass

    frames = []

    for ticker in tickers:
        try:
            raw = yf.download(
                ticker,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                threads=False,
            )
            price = _extract_single_close(raw, ticker)

            if price is not None and price.notna().sum().sum() > 20:
                frames.append(price)

            time.sleep(0.2)

        except Exception:
            continue

    if frames:
        prices = pd.concat(frames, axis=1).ffill().dropna(how="all")

        if prices.shape[1] >= max(1, len(tickers) // 2):
            prices.attrs["source"] = "yahoo_partial"
            return prices

    prices = generate_demo_prices(tickers, start, end)
    prices.attrs["source"] = "demo"
    return prices


def _extract_close_prices(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """Handle Yahoo Finance output shape for single-index and multi-index data."""
    if raw is None or raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            prices = raw["Close"]
        elif "Adj Close" in raw.columns.get_level_values(0):
            prices = raw["Adj Close"]
        else:
            return pd.DataFrame()
    else:
        if "Close" in raw.columns:
            prices = raw[["Close"]].rename(columns={"Close": tickers[0]})
        elif "Adj Close" in raw.columns:
            prices = raw[["Adj Close"]].rename(columns={"Adj Close": tickers[0]})
        else:
            return pd.DataFrame()

    if isinstance(prices, pd.Series):
        prices = prices.to_frame(name=tickers[0])

    prices.columns = [str(c).upper() for c in prices.columns]
    return prices


def _extract_single_close(raw: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    """Extract a one-column close-price DataFrame for one ticker."""
    if raw is None or raw.empty:
        return None

    if "Close" in raw.columns:
        return raw[["Close"]].rename(columns={"Close": ticker})

    if "Adj Close" in raw.columns:
        return raw[["Adj Close"]].rename(columns={"Adj Close": ticker})

    return None


def _is_valid_price_frame(prices: pd.DataFrame) -> bool:
    """Check that a downloaded price frame has usable price history."""
    return (
        isinstance(prices, pd.DataFrame)
        and not prices.empty
        and prices.shape[1] > 0
        and prices.notna().sum().sum() > 20
    )


def generate_demo_prices(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """
    Generate deterministic demo prices when Yahoo Finance is rate-limited.

    This is not real market data. It keeps the dashboard functional so the
    analytics engine, visuals, and exports can be demonstrated.
    """
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)

    if end_dt <= start_dt:
        end_dt = pd.Timestamp(datetime.today())

    dates = pd.bdate_range(start_dt, end_dt)

    if len(dates) < 30:
        dates = pd.bdate_range(end=pd.Timestamp(datetime.today()), periods=252)

    price_data = {}

    for ticker in tickers:
        seed = int(hashlib.sha256(ticker.encode()).hexdigest(), 16) % (2**32)
        rng = np.random.default_rng(seed)

        starting_price = 50 + (seed % 450)
        drift = 0.00025 + ((seed % 10) / 100000)
        volatility = 0.015 + ((seed % 20) / 2000)

        returns = rng.normal(loc=drift, scale=volatility, size=len(dates))
        prices = starting_price * np.cumprod(1 + returns)

        price_data[ticker] = prices

    return pd.DataFrame(price_data, index=dates)
