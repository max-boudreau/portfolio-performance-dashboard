from __future__ import annotations

from datetime import date, datetime
import math
import numpy as np
import pandas as pd
import streamlit as st
from .db import get_admin_client, get_public_client


def _json_safe(value):
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _dataframe_to_json_safe_records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    clean = df.copy()
    clean = clean.replace([np.inf, -np.inf], np.nan)
    clean = clean.where(pd.notnull(clean), None)
    return _json_safe(clean.to_dict(orient="records"))


def create_snapshot(portfolio_uuid: str, snapshot_date: date, snapshot_name: str, total_market_value: float, holdings_df: pd.DataFrame, metrics: dict, notes: str = "") -> None:
    client = get_admin_client()
    payload = {
        "portfolio_id": portfolio_uuid,
        "snapshot_date": str(snapshot_date),
        "snapshot_name": snapshot_name,
        "total_market_value": _json_safe(total_market_value),
        "holdings_json": _dataframe_to_json_safe_records(holdings_df),
        "metrics_json": _json_safe(metrics or {}),
        "notes": notes or "",
    }
    client.table("portfolio_snapshots").insert(payload).execute()
    fetch_snapshots_public.clear()


@st.cache_data(ttl=60, show_spinner=False)
def fetch_snapshots_public() -> pd.DataFrame:
    client = get_public_client()
    response = client.table("portfolio_snapshots").select("id, snapshot_date, snapshot_name, total_market_value, holdings_json, metrics_json, notes, created_at, portfolios(id, portfolio_name, is_public)").order("snapshot_date", desc=True).execute()
    rows = []
    for row in response.data or []:
        p = row.get("portfolios") or {}
        if p.get("is_public") is not True:
            continue
        rows.append({"id": row.get("id"), "portfolio_id": p.get("portfolio_name"), "_db_portfolio_uuid": p.get("id"), "snapshot_date": row.get("snapshot_date"), "snapshot_name": row.get("snapshot_name"), "total_market_value": row.get("total_market_value"), "holdings_json": row.get("holdings_json"), "metrics_json": row.get("metrics_json"), "notes": row.get("notes"), "created_at": row.get("created_at")})
    return pd.DataFrame(rows)
