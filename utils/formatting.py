# /utils/formatting.py
import pandas as pd
from db.models import Transaction

def transactions_to_dataframe(transactions: list[Transaction]) -> pd.DataFrame:
    """Converts a list of Transaction objects to a pandas DataFrame."""
    if not transactions:
        return pd.DataFrame()
    return pd.DataFrame([
        {
            "Date": txn.created_at.strftime('%Y-%m-%d %H:%M'),
            "Type": txn.type.capitalize(),
            "Category": txn.category,
            "Note": txn.note,
            "Amount": txn.amount,
            "Wallet": txn.wallet.name if txn.wallet else "N/A"
        }
        for txn in transactions
    ])

def format_transaction_details(txn: Transaction) -> str:
    """Formats a single transaction's details into a readable string."""
    wallet_name = txn.wallet.name if txn.wallet else "N/A"
    return (
        f"✅ Transaction Details:\n"
        f"----------------------\n"
        f"Note: {txn.note}\n"
        f"Amount: ₹{txn.amount}\n"
        f"Category: {txn.category}\n"
        f"Type: {txn.type.capitalize()}\n"
        f"Wallet: {wallet_name}\n"
        f"Date: {txn.created_at.strftime('%d %b %Y, %I:%M %p')}\n"
        f"----------------------"
    )