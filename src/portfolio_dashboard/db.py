from __future__ import annotations

import pandas as pd
import streamlit as st
from supabase import create_client, Client


def supabase_configured() -> bool:
    """Return True if the required Supabase secrets exist."""
    try:
        return bool(st.secrets["supabase"]["url"] and st.secrets["supabase"]["publishable_key"])
    except Exception:
        return False


def get_public_client() -> Client:
    """Client used for public read-only dashboard access."""
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["publishable_key"]
    return create_client(url, key)


def get_admin_client() -> Client:
    """Admin client used for write operations. Keep the secret key only in Streamlit Secrets."""
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["secret_key"]
    if not key:
        raise RuntimeError("Missing Supabase secret_key in Streamlit Secrets.")
    return create_client(url, key)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_portfolios_public() -> pd.DataFrame:
    """Fetch public portfolios from Supabase."""
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
    """Fetch public transactions and convert them into the app's transaction-ledger schema."""
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
                "owner": portfolio.get("owner_name"),
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
    """Fetch all portfolios using the admin key."""
    client = get_admin_client()
    response = (
        client.table("portfolios")
        .select("id, portfolio_name, owner_name, description, is_public, created_at")
        .order("portfolio_name")
        .execute()
    )
    return pd.DataFrame(response.data or [])


def create_portfolio(portfolio_name: str, owner_name: str | None = None, description: str | None = None, is_public: bool = True) -> None:
    """Create a new portfolio."""
    client = get_admin_client()
    payload = {
        "portfolio_name": portfolio_name.strip(),
        "owner_name": owner_name.strip() if owner_name else None,
        "description": description.strip() if description else None,
        "is_public": is_public,
    }
    client.table("portfolios").insert(payload).execute()
    clear_db_cache()


def update_portfolio_visibility(portfolio_id: str, is_public: bool) -> None:
    """Show or hide a portfolio from the public dashboard."""
    client = get_admin_client()
    client.table("portfolios").update({"is_public": is_public}).eq("id", portfolio_id).execute()
    clear_db_cache()


def add_transaction(portfolio_id: str, trade_date, ticker: str, side: str, quantity: float, price: float, fees: float = 0.0, notes: str | None = None) -> None:
    """Add one BUY or SELL transaction."""
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
    """Delete a transaction by database ID."""
    client = get_admin_client()
    client.table("transactions").delete().eq("id", transaction_id).execute()
    clear_db_cache()


def import_transactions_for_portfolio(portfolio_id: str, transactions: pd.DataFrame) -> int:
    """Bulk import uploaded CSV transactions into one Supabase portfolio."""
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
    """Clear cached Supabase reads after database writes."""
    fetch_portfolios_public.clear()
    fetch_transactions_public.clear()
