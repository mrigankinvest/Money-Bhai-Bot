import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func, case
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import OperationalError
from datetime import datetime, timedelta
from .models import Wallet, Transaction, Goal, Transfer
from .database import AsyncSessionLocal
from thefuzz import process
import pandas as pd

logger = logging.getLogger(__name__)

# --- Transaction Functions ---

async def add_transaction(session: AsyncSession, user_id: int, tx_data: dict, wallet_id: int) -> Transaction:
    """Adds a new transaction to the database and links it to a wallet."""
    txn = Transaction(
        user_id=user_id,
        wallet_id=wallet_id,
        amount=abs(tx_data.get("amount")), # Always store amount as a positive number
        note=tx_data.get("note"),
        type=tx_data.get("type", "expense"),
        category=tx_data.get("category", "Other")
    )
    session.add(txn)
    await session.commit()
    await session.refresh(txn)
    await update_wallet_balance(session, wallet_id, txn.amount, txn.type)
    return txn

async def get_transactions(session: AsyncSession, user_id: int, limit: int = 10) -> list[Transaction]:
    query = (
        select(Transaction).options(selectinload(Transaction.wallet))
        .filter_by(user_id=user_id).order_by(Transaction.created_at.desc()).limit(limit)
    )
    result = await session.execute(query)
    return result.scalars().all()

async def get_last_transaction(session: AsyncSession, user_id: int) -> Transaction | None:
    """Retrieves the most recent transaction for a given user from the database."""
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(1)
        .options(selectinload(Transaction.wallet))
    )
    return result.scalars().first()

async def get_last_n_transactions(session: AsyncSession, user_id: int, count: int) -> list[Transaction]:
    """Retrieves the last 'n' transactions for a given user from the database."""
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(count)
        .options(selectinload(Transaction.wallet))
    )
    # We reverse the list so the most recent transaction appears last
    return result.scalars().all()[::-1]

async def get_all_transactions(session: AsyncSession, user_id: int) -> list[Transaction]:
    query = (
        select(Transaction).options(selectinload(Transaction.wallet))
        .filter_by(user_id=user_id).order_by(Transaction.created_at.desc())
    )
    result = await session.execute(query)
    return result.scalars().all()

async def get_transaction_by_id(session: AsyncSession, user_id: int, txn_id: int) -> Transaction | None:
    query = (
        select(Transaction).options(selectinload(Transaction.wallet))
        .filter_by(user_id=user_id, id=txn_id)
    )
    result = await session.execute(query)
    return result.scalars().first()

async def search_transactions(session: AsyncSession, user_id: int, query_str: str, limit: int = 10) -> list[Transaction]:
    """
    Intelligently searches transactions by parsing a query string to separate
    a wallet name from the transaction note, handling spelling errors.
    """
    all_wallets = await get_wallets(session, user_id)
    if not all_wallets:
        # If there are no wallets, just search the note
        query = select(Transaction).options(selectinload(Transaction.wallet)).filter(Transaction.user_id == user_id, Transaction.note.ilike(f"%{query_str}%"))
        result = await session.execute(query)
        return result.scalars().all()

    wallet_names = [w.name for w in all_wallets]
    wallet_map = {w.name.lower(): w.id for w in all_wallets}
    
    query_words = query_str.lower().split()
    found_wallet_id = None
    note_keywords = list(query_words)
    word_to_remove = None

    # --- NEW: Fuzzy search logic for typos ---
    for word in query_words:
        # Find the best wallet name match for each word in the query
        match = process.extractOne(word, wallet_names)
        # If the match is strong (e.g., > 80% similarity), we've found our wallet
        if match and match[1] > 80:
            matched_name = match[0]
            found_wallet_id = wallet_map[matched_name.lower()]
            word_to_remove = word # Mark the misspelled word for removal
            break

    if word_to_remove:
        # If a wallet was found, remove the (potentially misspelled) word and prepositions
        note_keywords = [
            kw for kw in note_keywords 
            if kw != word_to_remove and kw not in ['in', 'from', 'on', 'at', 'using']
        ]

    note_search_term = " ".join(note_keywords)

    # Build the database query dynamically
    query = (
        select(Transaction)
        .options(selectinload(Transaction.wallet))
        .filter(Transaction.user_id == user_id)
    )

    if found_wallet_id:
        query = query.filter(Transaction.wallet_id == found_wallet_id)

    if note_search_term:
        query = query.filter(Transaction.note.ilike(f"%{note_search_term}%"))

    query = query.order_by(Transaction.created_at.desc()).limit(limit)
    
    result = await session.execute(query)
    return result.scalars().all()

async def update_transaction(session: AsyncSession, user_id: int, txn_id: int, new_data: dict) -> Transaction | None:
    # This function would need more complex logic to recalculate balances,
    # for now it just updates the data.
    updates = {key: value for key, value in new_data.items() if value is not None}
    if not updates:
        return await get_transaction_by_id(session, user_id, txn_id)
    query = update(Transaction).where(Transaction.id == txn_id, Transaction.user_id == user_id).values(**updates)
    await session.execute(query)
    await session.commit()
    return await get_transaction_by_id(session, user_id, txn_id)

async def delete_transaction_and_update_wallet(session: AsyncSession, transaction: Transaction) -> bool:
    """Deletes a transaction and reverses its effect on the wallet balance."""
    wallet = await session.get(Wallet, transaction.wallet_id)
    if not wallet:
        return False

    # Reverse the transaction's effect on the balance
    if transaction.type in ['expense', 'withdrawal']:
        wallet.balance += transaction.amount
    elif transaction.type in ['income', 'deposit']:
        wallet.balance -= transaction.amount
    
    # Now delete the transaction object
    await session.delete(transaction)
    await session.commit()
    return True

async def delete_all_transactions(session: AsyncSession, user_id: int) -> int:
    """Deletes all transactions for a user and resets all wallet balances to zero."""
    count_query = select(func.count(Transaction.id)).where(Transaction.user_id == user_id)
    result = await session.execute(count_query)
    deleted_count = result.scalar_one_or_none() or 0

    if deleted_count > 0:
        # Reset all wallet balances for the user to 0
        await session.execute(update(Wallet).where(Wallet.user_id == user_id).values(balance=0.0))
        # Delete all transactions
        await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
        await session.commit()
    
    return deleted_count

# --- Wallet and Transfer Functions ---


async def get_wallet_by_id(session: AsyncSession, wallet_id: int) -> Wallet | None:
    """Retrieves a single wallet by its primary key (ID)."""
    return await session.get(Wallet, wallet_id)


async def create_wallet(session: AsyncSession, user_id: int, name: str, category: str = 'Expense', initial_balance: float = 0.0) -> Wallet:
    existing_wallet = await _get_exact_wallet_by_name(session, user_id, name)
    if existing_wallet:
        return existing_wallet
        
    new_wallet = Wallet(user_id=user_id, name=name, category=category, balance=initial_balance)
    session.add(new_wallet)
    await session.commit()
    await session.refresh(new_wallet)
    return new_wallet

async def get_wallets(session: AsyncSession, user_id: int) -> list[Wallet]:
    query = select(Wallet).filter_by(user_id=user_id).order_by(Wallet.name)
    result = await session.execute(query)
    return result.scalars().all()

async def get_wallet_by_name(session: AsyncSession, user_id: int, name: str) -> Wallet | None:
    """
    Finds the best wallet match for a user's input, allowing for typos.
    """
    all_wallets_query = select(Wallet).filter_by(user_id=user_id)
    result = await session.execute(all_wallets_query)
    all_wallets = result.scalars().all()

    if not all_wallets:
        return None

    wallet_map = {wallet.name: wallet for wallet in all_wallets}
    best_match = process.extractOne(name, wallet_map.keys())

    if best_match and best_match[1] > 80:
        return wallet_map[best_match[0]]
    
    return None

async def update_wallet_balance(session: AsyncSession, wallet_id: int, amount: float, transaction_type: str):
    wallet = await session.get(Wallet, wallet_id)
    if wallet:
        if transaction_type in ['expense', 'withdrawal']:
            wallet.balance -= amount
        elif transaction_type in ['income', 'deposit']:
            wallet.balance += amount
        await session.commit()

async def record_transfer(session: AsyncSession, user_id: int, from_wallet_id: int, to_wallet_id: int, amount: float, note: str = None) -> Transfer:
    from_wallet = await session.get(Wallet, from_wallet_id)
    to_wallet = await session.get(Wallet, to_wallet_id)
    from_wallet.balance -= amount
    to_wallet.balance += amount
    new_transfer = Transfer(user_id=user_id, from_wallet_id=from_wallet_id, to_wallet_id=to_wallet_id, amount=amount, note=note)
    session.add(new_transfer)
    await session.commit()
    await session.refresh(new_transfer)
    return new_transfer

async def get_transactions_for_wallet_period(session: AsyncSession, user_id: int, wallet_id: int, period: str) -> list[Transaction]:
    now = datetime.now()
    if period == 'weekly': start_date = now - timedelta(days=7)
    elif period == 'monthly': start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'yearly': start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else: start_date = None
    query = select(Transaction).options(selectinload(Transaction.wallet)).filter_by(user_id=user_id, wallet_id=wallet_id)
    if start_date: query = query.filter(Transaction.created_at >= start_date)
    query = query.order_by(Transaction.created_at.desc())
    result = await session.execute(query)
    return result.scalars().all()

async def recalculate_wallet_balance(wallet_id: int):
    """
    Recalculates a wallet's balance from scratch and removes the 'is_updating' flag.
    This is designed to be run as a resilient background task.
    """
    max_retries = 3
    retry_delay = 0.5

    for attempt in range(max_retries):
        try:
            async with AsyncSessionLocal() as session:
                sum_query = select(
                    func.sum(
                        case(
                            (Transaction.type.in_(['expense', 'withdrawal']), -Transaction.amount),
                            else_=Transaction.amount
                        )
                    )
                ).where(Transaction.wallet_id == wallet_id)

                result = await session.execute(sum_query)
                new_balance = result.scalar_one_or_none() or 0.0

                wallet_update_stmt = update(Wallet).where(Wallet.id == wallet_id).values(
                    balance=new_balance,
                    is_updating=False
                )
                await session.execute(wallet_update_stmt)
                await session.commit()
                
                logger.info(f"Successfully recalculated balance for wallet_id: {wallet_id}")
                return

        except OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logger.warning(f"Database locked on attempt {attempt + 1} for wallet {wallet_id}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error(f"Failed to recalculate balance for wallet {wallet_id} after {max_retries} retries: {e}", exc_info=True)
                break
        except Exception as e:
            logger.error(f"An unexpected error occurred during balance recalculation for wallet {wallet_id}: {e}", exc_info=True)
            break

async def add_transaction_and_flag(session: AsyncSession, user_id: int, tx_data: dict, wallet_id: int) -> Transaction:
    """
    Adds a new transaction and flags the wallet for a background balance update.
    """
    txn = Transaction(
        user_id=user_id,
        wallet_id=wallet_id,
        amount=abs(tx_data.get("amount")),
        note=tx_data.get("note"),
        type=tx_data.get("type", "expense"),
        category=tx_data.get("category", "Other")
    )
    session.add(txn)

    wallet_update_stmt = update(Wallet).where(Wallet.id == wallet_id).values(is_updating=True)
    await session.execute(wallet_update_stmt)
    
    await session.commit()
    await session.refresh(txn)
    return txn

async def _get_exact_wallet_by_name(session: AsyncSession, user_id: int, name: str) -> Wallet | None:
    """
    Finds a wallet with an exact, case-insensitive name match.
    Used internally to prevent creating duplicates.
    """
    query = select(Wallet).filter(Wallet.user_id == user_id, Wallet.name.ilike(name))
    result = await session.execute(query)
    return result.scalars().first()


async def get_financial_summary(session: AsyncSession, user_id: int) -> dict:
    """
    Calculates total income/expense from 'Expense' wallets and sums the
    current balance of 'Investment' wallets.
    """
    summary = {
        "total_expense": 0.0,
        "total_income": 0.0,
        "net_investment": 0.0,
        "goal_status": "Not Set"
    }

    # --- Part 1: Calculate Income & Expense from 'Expense' wallets' transactions ---
    expense_tx_query = (
        select(
            Transaction.type,
            func.sum(Transaction.amount).label("total_amount")
        )
        .join(Wallet, Wallet.id == Transaction.wallet_id)
        .where(Wallet.user_id == user_id, Wallet.category == 'Expense')
        .group_by(Transaction.type)
    )
    expense_result = await session.execute(expense_tx_query)
    for row in expense_result.all():
        if row.type in ['income', 'deposit']:
            summary['total_income'] = row.total_amount or 0.0
        elif row.type in ['expense', 'withdrawal']:
            summary['total_expense'] = row.total_amount or 0.0

    # --- Part 2: Calculate Net Investment by summing the BALANCES of 'Investment' wallets ---
    investment_balance_query = (
        select(func.sum(Wallet.balance).label("total_balance"))
        .where(Wallet.user_id == user_id, Wallet.category == 'Investment')
    )
    investment_result = await session.execute(investment_balance_query)
    summary['net_investment'] = investment_result.scalar_one_or_none() or 0.0

    # --- Part 3: Fetch goal information ---
    goal_query = select(Goal).where(Goal.user_id == user_id)
    goal_result = await session.execute(goal_query)
    user_goal = goal_result.scalars().first()

    if user_goal and user_goal.target_amount > 0:
        # Use the newly calculated net_investment for goal tracking
        percentage = (summary['net_investment'] / user_goal.target_amount) * 100
        summary['goal_status'] = f"{percentage:.1f}% Achieved"

    return summary

# In db/db_writer.py

async def delete_wallet_and_associated_data(session: AsyncSession, wallet_id: int) -> bool:
    """
    Deletes a wallet, all of its transactions, and all associated transfers.
    This is a destructive and irreversible action.
    """
    try:
        # Get the wallet to confirm it exists before proceeding
        wallet = await session.get(Wallet, wallet_id)
        if not wallet:
            logger.warning(f"Attempted to delete a non-existent wallet with ID: {wallet_id}")
            return False

        # Delete all transfers to or from this wallet
        await session.execute(
            delete(Transfer).where((Transfer.from_wallet_id == wallet_id) | (Transfer.to_wallet_id == wallet_id))
        )

        # Delete all transactions associated with this wallet
        await session.execute(
            delete(Transaction).where(Transaction.wallet_id == wallet_id)
        )
        
        # Finally, delete the wallet itself
        await session.delete(wallet)
        
        await session.commit()
        logger.info(f"Successfully deleted wallet '{wallet.name}' (ID: {wallet_id}) and all associated data.")
        return True
    except Exception as e:
        logger.error(f"Error during wallet deletion for ID {wallet_id}: {e}", exc_info=True)
        await session.rollback()
        return False
    
async def delete_all_user_data(session: AsyncSession, user_id: int) -> bool:
    """
    Deletes absolutely all data for a user: wallets, transactions, transfers, and goals.
    """
    try:
        # The order is important to respect database constraints
        await session.execute(delete(Transfer).where(Transfer.user_id == user_id))
        await session.execute(delete(Goal).where(Goal.user_id == user_id))
        await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
        await session.execute(delete(Wallet).where(Wallet.user_id == user_id))
        
        await session.commit()
        logger.info(f"Successfully deleted all data for user_id: {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error during complete data deletion for user {user_id}: {e}", exc_info=True)
        await session.rollback()
        return False
    
async def update_wallet(session: AsyncSession, wallet_id: int, updates: dict) -> Wallet | None:
    """Updates a wallet's data."""
    if not updates:
        return await session.get(Wallet, wallet_id)
        
    await session.execute(
        update(Wallet).where(Wallet.id == wallet_id).values(**updates)
    )
    await session.commit()
    return await session.get(Wallet, wallet_id)

async def get_trend_data(session: AsyncSession, user_id: int, period: str, wallet_category: str) -> pd.DataFrame:
    """
    Fetches and aggregates transaction data for trend analysis.
    Groups data by month, quarter, or year.
    """
    if period == 'monthly':
        period_format = '%Y-%m'
    elif period == 'yearly':
        period_format = '%Y'
    elif period == 'quarterly':
        # SQLite expression to calculate year and quarter
        period_format = "strftime('%Y', created_at) || '-Q' || ((strftime('%m', created_at) - 1) / 3 + 1)"
    else:
        return pd.DataFrame()

    # Use a raw SQL expression for the dynamic grouping
    period_expression = func.strftime(period_format, Transaction.created_at) if '||' not in period_format else func.literal_column(period_format)

    query = (
        select(
            period_expression.label("period"),
            func.sum(case((Transaction.type.in_(['income', 'deposit']), Transaction.amount), else_=0)).label("income"),
            func.sum(case((Transaction.type.in_(['expense', 'withdrawal']), Transaction.amount), else_=0)).label("expense")
        )
        .join(Wallet, Wallet.id == Transaction.wallet_id)
        .where(
            Transaction.user_id == user_id,
            Wallet.category == wallet_category
        )
        .group_by("period")
        .order_by("period")
    )

    result = await session.execute(query)
    df = pd.DataFrame(result.all(), columns=['Period', 'Income', 'Expense'])
    return df

def _get_period_filter(period_type: str, period_value: str):
    """Helper to create a SQL filter for a specific period."""
    if period_type == 'monthly':
        # YYYY-MM
        return func.strftime('%Y-%m', Transaction.created_at) == period_value
    elif period_type == 'yearly':
        # YYYY
        return func.strftime('%Y', Transaction.created_at) == period_value
    elif period_type == 'quarterly':
        # YYYY-Q#
        year, quarter = period_value.split('-Q')
        q_start_month = (int(quarter) - 1) * 3 + 1
        q_end_month = q_start_month + 2
        return (
            (func.strftime('%Y', Transaction.created_at) == year) &
            (func.strftime('%m', Transaction.created_at).between(f'{q_start_month:02}', f'{q_end_month:02}'))
        )
    return None

async def get_period_comparison_data(session: AsyncSession, user_id: int, wallet_category: str, period_type: str, period1_val: str, period2_val: str) -> dict:
    """Fetches aggregated income/expense data for two distinct periods."""
    
    async def _get_metrics(period_value):
        period_filter = _get_period_filter(period_type, period_value)
        if period_filter is None:
            return {"income": 0, "expense": 0}

        query = (
            select(
                func.sum(case((Transaction.type.in_(['income', 'deposit']), Transaction.amount), else_=0)).label("income"),
                func.sum(case((Transaction.type.in_(['expense', 'withdrawal']), Transaction.amount), else_=0)).label("expense")
            )
            .join(Wallet, Wallet.id == Transaction.wallet_id)
            .where(
                Transaction.user_id == user_id,
                Wallet.category == wallet_category,
                period_filter
            )
        )
        result = await session.execute(query)
        data = result.first()
        return {"income": data.income or 0, "expense": data.expense or 0}

    data1 = await _get_metrics(period1_val)
    data2 = await _get_metrics(period2_val)
    
    return {"period1": data1, "period2": data2}