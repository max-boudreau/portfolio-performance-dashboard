from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from .db import (
    add_transaction,
    create_portfolio,
    delete_transaction,
    fetch_portfolios_admin,
    fetch_transactions_admin,
    import_transactions_for_portfolio,
    update_portfolio_visibility,
)
from .validators import validate_transactions
from .snapshots import create_snapshot


def admin_login() -> bool:
    """Simple password-only admin mode."""
    if "is_admin" not in st.session_state:
        st.session_state["is_admin"] = False

    try:
        admin_password = st.secrets["admin"]["password"]
    except Exception:
        admin_password = None

    with st.sidebar:
        st.divider()
        st.subheader("Admin")
        if st.session_state["is_admin"]:
            st.success("Admin mode unlocked")
            if st.button("Lock admin mode"):
                st.session_state["is_admin"] = False
                st.rerun()
        else:
            entered = st.text_input("Admin password", type="password")
            if st.button("Unlock admin mode"):
                if admin_password and entered == admin_password:
                    st.session_state["is_admin"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password")

    return bool(st.session_state["is_admin"])


def render_admin_panel(transactions_df: pd.DataFrame, holdings_df: pd.DataFrame, summary_df: pd.DataFrame) -> None:
    """Render admin tools for editing portfolios and trades."""
    st.subheader("Admin Panel")
    st.caption("This section is visible only after admin login.")

    portfolios = fetch_portfolios_admin()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["Add Portfolio", "Add Transaction", "Delete Transaction", "Bulk Import", "Visibility", "Create Snapshot"]
    )

    with tab1:
        st.markdown("### Add Portfolio")
        name = st.text_input("Portfolio name")
        owner = st.text_input("Owner name")
        description = st.text_area("Description")
        is_public = st.checkbox("Publicly visible", value=True)

        if st.button("Create portfolio"):
            if not name.strip():
                st.error("Portfolio name is required.")
            else:
                create_portfolio(name, owner, description, is_public)
                st.success("Portfolio created.")
                st.rerun()

    with tab2:
        st.markdown("### Add Transaction")
        if portfolios.empty:
            st.warning("Create a portfolio first.")
        else:
            selected_name = st.selectbox("Portfolio", portfolios["portfolio_name"].tolist(), key="add_tx_portfolio")
            selected_id = portfolios.loc[portfolios["portfolio_name"] == selected_name, "id"].iloc[0]

            col1, col2 = st.columns(2)
            with col1:
                trade_date = st.date_input("Trade date", value=date.today())
                ticker = st.text_input("Ticker", value="AAPL")
                side = st.selectbox("Side", ["BUY", "SELL"])
            with col2:
                quantity = st.number_input("Quantity", min_value=0.0001, value=1.0, step=1.0)
                price = st.number_input("Price", min_value=0.0001, value=100.0, step=1.0)
                fees = st.number_input("Fees", min_value=0.0, value=0.0, step=1.0)

            notes = st.text_input("Notes")

            if st.button("Add transaction"):
                add_transaction(selected_id, trade_date, ticker, side, quantity, price, fees, notes)
                st.success("Transaction added.")
                st.rerun()

    with tab3:
        st.markdown("### Delete Transaction")
        admin_tx = fetch_transactions_admin()
        if admin_tx.empty:
            st.info("No transactions found.")
        else:
            st.dataframe(admin_tx, use_container_width=True)
            labels = admin_tx.apply(
                lambda r: f"{r['portfolio_name']} | {r['trade_date']} | {r['side']} {r['quantity']} {r['ticker']} @ {r['price']}",
                axis=1,
            ).tolist()
            selected_label = st.selectbox("Select transaction to delete", labels)
            selected_idx = labels.index(selected_label)
            selected_tx_id = admin_tx.iloc[selected_idx]["transaction_id"]

            confirm = st.checkbox("I understand this will permanently delete the transaction")
            if st.button("Delete selected transaction", disabled=not confirm):
                delete_transaction(selected_tx_id)
                st.success("Transaction deleted.")
                st.rerun()

    with tab4:
        st.markdown("### Bulk Import CSV Into a Portfolio")
        st.caption("CSV columns needed: trade_date, ticker, side, quantity, price, fees, notes.")
        if portfolios.empty:
            st.warning("Create a portfolio first.")
        else:
            selected_name = st.selectbox("Destination portfolio", portfolios["portfolio_name"].tolist(), key="bulk_portfolio")
            selected_id = portfolios.loc[portfolios["portfolio_name"] == selected_name, "id"].iloc[0]
            upload = st.file_uploader("Upload trades CSV", type=["csv"], key="bulk_upload")

            if upload is not None:
                raw = pd.read_csv(upload)
                raw["portfolio_id"] = selected_name
                if "owner" not in raw.columns:
                    raw["owner"] = selected_name

                try:
                    clean = validate_transactions(raw)
                    st.dataframe(clean, use_container_width=True)
                    if st.button("Import CSV transactions"):
                        count = import_transactions_for_portfolio(selected_id, clean)
                        st.success(f"Imported {count} transactions.")
                        st.rerun()
                except Exception as exc:
                    st.error(f"CSV validation failed: {exc}")

    with tab5:
        st.markdown("### Portfolio Visibility")
        if portfolios.empty:
            st.warning("No portfolios found.")
        else:
            st.dataframe(portfolios, use_container_width=True)
            selected_name = st.selectbox("Portfolio to update", portfolios["portfolio_name"].tolist(), key="vis_portfolio")
            selected_row = portfolios[portfolios["portfolio_name"] == selected_name].iloc[0]
            visible = st.checkbox("Publicly visible", value=bool(selected_row["is_public"]), key="vis_checkbox")

            if st.button("Update visibility"):
                update_portfolio_visibility(selected_row["id"], visible)
                st.success("Visibility updated.")
                st.rerun()

    with tab6:
        st.markdown("### Create Portfolio Snapshot")
        if portfolios.empty:
            st.warning("No portfolios found.")
        else:
            public_portfolios = sorted(holdings_df["Portfolio"].unique()) if not holdings_df.empty else []
            if not public_portfolios:
                st.warning("No holdings available to snapshot.")
            else:
                selected_name = st.selectbox("Portfolio to snapshot", public_portfolios, key="snap_portfolio")
                portfolio_row = portfolios[portfolios["portfolio_name"] == selected_name]
                if portfolio_row.empty:
                    st.warning("This portfolio is not in the admin portfolio table.")
                else:
                    portfolio_uuid = portfolio_row["id"].iloc[0]
                    snapshot_date = st.date_input("Snapshot date", value=date.today())
                    snapshot_name = st.text_input("Snapshot name", value=f"{selected_name} Snapshot")
                    notes = st.text_area("Snapshot notes")

                    portfolio_holdings = holdings_df[holdings_df["Portfolio"] == selected_name].copy()
                    total_mv = float(portfolio_holdings["Market Value"].sum())
                    metrics_row = summary_df[summary_df["Portfolio"] == selected_name]
                    metrics = metrics_row.iloc[0].to_dict() if not metrics_row.empty else {}

                    st.dataframe(portfolio_holdings, use_container_width=True)

                    if st.button("Create snapshot"):
                        create_snapshot(
                            portfolio_uuid=portfolio_uuid,
                            snapshot_date=snapshot_date,
                            snapshot_name=snapshot_name,
                            total_market_value=total_mv,
                            holdings_df=portfolio_holdings,
                            metrics=metrics,
                            notes=notes,
                        )
                        st.success("Snapshot created.")
