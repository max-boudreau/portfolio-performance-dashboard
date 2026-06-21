from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from .db import get_admin_client, get_public_client


def create_snapshot(
    portfolio_uuid: str,
    snapshot_date: date,
    snapshot_name: str,
    total_market_value: float,
    holdings_df: pd.DataFrame,
    metrics: dict,
    notes: str = "",
) -> None:
    """Create a snapshot record in Supabase."""
    client = get_admin_client()
    payload = {
        "portfolio_id": portfolio_uuid,
        "snapshot_date": str(snapshot_date),
        "snapshot_name": snapshot_name,
        "total_market_value": float(total_market_value),
        "holdings_json": holdings_df.to_dict(orient="records"),
        "metrics_json": metrics,
        "notes": notes,
    }
    client.table("portfolio_snapshots").insert(payload).execute()
    fetch_snapshots_public.clear()


@st.cache_data(ttl=60, show_spinner=False)
def fetch_snapshots_public() -> pd.DataFrame:
    """Fetch public snapshots."""
    client = get_public_client()
    response = (
        client.table("portfolio_snapshots")
        .select(
            "id, snapshot_date, snapshot_name, total_market_value, holdings_json, "
            "metrics_json, notes, created_at, portfolios(id, portfolio_name, is_public)"
        )
        .order("snapshot_date", desc=True)
        .execute()
    )

    rows = []
    for row in response.data or []:
        p = row.get("portfolios") or {}
        if p.get("is_public") is not True:
            continue
        rows.append(
            {
                "id": row.get("id"),
                "portfolio_id": p.get("portfolio_name"),
                "_db_portfolio_uuid": p.get("id"),
                "snapshot_date": row.get("snapshot_date"),
                "snapshot_name": row.get("snapshot_name"),
                "total_market_value": row.get("total_market_value"),
                "holdings_json": row.get("holdings_json"),
                "metrics_json": row.get("metrics_json"),
                "notes": row.get("notes"),
                "created_at": row.get("created_at"),
            }
        )

    return pd.DataFrame(rows)
