from __future__ import annotations

import pandas as pd
import streamlit as st
from supabase import create_client, Client


def supabase_configured() -> bool:
    """Return True if Supabase secrets are configured in Streamlit."""
    try:
        url = st.secrets["supabase"]["url"]
        publishable_key = st.secrets["supabase"]["publishable_key"]
        return bool(url and publishable_key)
    except Exception:
        return False


def get_public_client() -> Client:
    """Supabase client for public read-only access."""
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["publishable_key"]
    return create_client(url, key)


def get_admin_client() -> Client:
    """Supabase client for admin write access. Keep secret_key only in Streamlit Secrets."""
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"].get("secret_key", "")
    if not key:
        raise RuntimeError("Missing supabase.secret_key in Streamlit Secrets.")
    return create_client(url, key)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_portfolios_public() -> pd.DataFrame:
    """Fetch public portfolios."""
    client = get_public_client()
    response = (
        client.table("portfolios")
        .select("id, portfolio_name, owner_name, description, is_public, created_at")
        .eq("is_public", True)
        .order("portfolio_name")
        .execute()
    )
    return pd.DataFrame(response.data or [])


@st.cache_data(ttl=60, show_spinner=False)
def fetch_transactions_public() -> pd.DataFrame:
    """
    Fetch transactions for public portfolios and map them into the existing
    app transaction-ledger format.
    """
    client = get_public_client()
    response = (
        client.table("transactions")
        .select(
            "id, trade_date, ticker, side, quantity, price, fees, notes, "
            "portfolios(id, portfolio_name, owner_name, is_public)"
        )
        .order("trade_date")
        .execute()
    )

    rows = []
    for row in response.data or []:
        portfolio = row.get("portfolios") or {}
        if portfolio.get("is_public") is not True:
            continue

        rows.append(
            {
                "_db_transaction_id": row.get("id"),
                "_db_portfolio_uuid": portfolio.get("id"),
                "portfolio_id": portfolio.get("portfolio_name"),
                "owner": portfolio.get("owner_name") or "",
                "trade_date": row.get("trade_date"),
                "ticker": row.get("ticker"),
                "side": row.get("side"),
                "quantity": float(row.get("quantity", 0)),
                "price": float(row.get("price", 0)),
                "fees": float(row.get("fees", 0) or 0),
                "notes": row.get("notes") or "",
            }
        )

    return pd.DataFrame(rows)


def fetch_portfolios_admin() -> pd.DataFrame:
    """Fetch all portfolios for admin UI."""
    client = get_admin_client()
    response = (
        client.table("portfolios")
        .select("id, portfolio_name, owner_name, description, is_public, created_at")
        .order("portfolio_name")
        .execute()
    )
    return pd.DataFrame(response.data or [])


def fetch_transactions_admin() -> pd.DataFrame:
    """Fetch all transactions for admin delete/review table."""
    client = get_admin_client()
    response = (
        client.table("transactions")
        .select(
            "id, trade_date, ticker, side, quantity, price, fees, notes, "
            "portfolios(id, portfolio_name, owner_name)"
        )
        .order("trade_date", desc=True)
        .execute()
    )

    rows = []
    for row in response.data or []:
        p = row.get("portfolios") or {}
        rows.append(
            {
                "transaction_id": row.get("id"),
                "portfolio_name": p.get("portfolio_name"),
                "owner_name": p.get("owner_name"),
                "trade_date": row.get("trade_date"),
                "ticker": row.get("ticker"),
                "side": row.get("side"),
                "quantity": float(row.get("quantity", 0)),
                "price": float(row.get("price", 0)),
                "fees": float(row.get("fees", 0) or 0),
                "notes": row.get("notes") or "",
            }
        )

    return pd.DataFrame(rows)


def create_portfolio(portfolio_name: str, owner_name: str, description: str, is_public: bool) -> None:
    """Create a portfolio."""
    client = get_admin_client()
    payload = {
        "portfolio_name": portfolio_name.strip(),
        "owner_name": owner_name.strip() if owner_name else None,
        "description": description.strip() if description else None,
        "is_public": bool(is_public),
    }
    client.table("portfolios").insert(payload).execute()
    clear_db_cache()


def update_portfolio_visibility(portfolio_id: str, is_public: bool) -> None:
    """Set portfolio public/private visibility."""
    client = get_admin_client()
    client.table("portfolios").update({"is_public": bool(is_public)}).eq("id", portfolio_id).execute()
    clear_db_cache()


def add_transaction(
    portfolio_id: str,
    trade_date,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    fees: float = 0.0,
    notes: str = "",
) -> None:
    """Add one transaction."""
    client = get_admin_client()
    payload = {
        "portfolio_id": portfolio_id,
        "trade_date": str(trade_date),
        "ticker": ticker.upper().strip(),
        "side": side.upper().strip(),
        "quantity": float(quantity),
        "price": float(price),
        "fees": float(fees or 0),
        "notes": notes or "",
    }
    client.table("transactions").insert(payload).execute()
    clear_db_cache()


def delete_transaction(transaction_id: str) -> None:
    """Delete transaction by Supabase UUID."""
    client = get_admin_client()
    client.table("transactions").delete().eq("id", transaction_id).execute()
    clear_db_cache()


def import_transactions_for_portfolio(portfolio_id: str, transactions: pd.DataFrame) -> int:
    """Bulk import transactions into a chosen portfolio."""
    client = get_admin_client()
    payload = []

    for _, row in transactions.iterrows():
        payload.append(
            {
                "portfolio_id": portfolio_id,
                "trade_date": str(pd.to_datetime(row["trade_date"]).date()),
                "ticker": str(row["ticker"]).upper().strip(),
                "side": str(row["side"]).upper().strip(),
                "quantity": float(row["quantity"]),
                "price": float(row["price"]),
                "fees": float(row.get("fees", 0) or 0),
                "notes": str(row.get("notes", "") or ""),
            }
        )

    if payload:
        client.table("transactions").insert(payload).execute()
        clear_db_cache()

    return len(payload)


def clear_db_cache() -> None:
    """Clear cached Supabase reads after writes."""
    fetch_portfolios_public.clear()
    fetch_transactions_public.clear()
