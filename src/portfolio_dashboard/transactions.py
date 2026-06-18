import pandas as pd
from .validators import validate_transactions

def load_transactions(file_or_path) -> pd.DataFrame:
    return validate_transactions(pd.read_csv(file_or_path))

def signed_transactions(transactions: pd.DataFrame) -> pd.DataFrame:
    tx = validate_transactions(transactions)
    tx["signed_quantity"] = tx["quantity"].where(tx["side"] == "BUY", -tx["quantity"])
    return tx
