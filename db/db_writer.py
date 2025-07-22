import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func, case
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import OperationalError
from datetime import datetime, timedelta
from .models import User, Wallet, Transaction, Goal, Transfer
from .database import get_session
from thefuzz import process
import pandas as pd
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# ===================================================================
# User and Onboarding Functions
# ===================================================================

async def get_or_create_user(telegram_id: int) -> Tuple[User, bool]:
    """Retrieves a user by their Telegram ID, creating them if they don't exist."""
    async with get_session() as session:
        result = await session.execute(
            select(User).options(selectinload(User.wallets)).filter_by(telegram_id=telegram_id)
        )
        user = result.scalar_one_or_none()
        created = False
        if not user:
            user = User(telegram_id=telegram_id)
            session.add(user)
            await session.flush()
            cash_wallet = Wallet(user_id=user.id, name="Cash", category="Expense", balance=0)
            zerodha_wallet = Wallet(user_id=user.id, name="Zerodha", category="Investment", balance=0)
            session.add_all([cash_wallet, zerodha_wallet])
            created = True
        if created:
             await session.refresh(user, ['wallets'])
        return user, created

async def update_user_name(telegram_id: int, name: str) -> None:
    """Updates the name of a user."""
    async with get_session() as session:
        stmt = select(User).filter_by(telegram_id=telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            user.name = name

async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    """Retrieves a user by their Telegram ID."""
    async with get_session() as session:
        result = await session.execute(select(User).filter_by(telegram_id=telegram_id))
        return result.scalar_one_or_none()

# ===================================================================
# Transaction Functions
# ===================================================================

async def add_transaction(user_id: int, tx_data: dict, wallet_id: int) -> Transaction:
    """Adds a new transaction to the database and links it to a wallet."""
    async with get_session() as session:
        txn = Transaction(user_id=user_id, wallet_id=wallet_id, amount=abs(tx_data.get("amount")), note=tx_data.get("note"), type=tx_data.get("type", "expense"), category=tx_data.get("category", "Other"))
        session.add(txn)
        await session.flush()
        await session.refresh(txn)
        await update_wallet_balance(wallet_id, txn.amount, txn.type)
        return txn

async def get_transactions(user_id: int, limit: int = 10) -> list[Transaction]:
    async with get_session() as session:
        query = (
            select(Transaction).options(selectinload(Transaction.wallet))
            .filter_by(user_id=user_id).order_by(Transaction.created_at.desc()).limit(limit)
        )
        result = await session.execute(query)
        return result.scalars().all()

async def get_last_transaction(user_id: int) -> Transaction | None:
    async with get_session() as session:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .limit(1)
            .options(selectinload(Transaction.wallet))
        )
        return result.scalars().first()

async def get_last_n_transactions(user_id: int, count: int) -> list[Transaction]:
    async with get_session() as session:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .limit(count)
            .options(selectinload(Transaction.wallet))
        )
        return result.scalars().all()[::-1]

async def get_all_transactions(user_id: int) -> list[Transaction]:
    async with get_session() as session:
        query = (
            select(Transaction).options(selectinload(Transaction.wallet))
            .filter_by(user_id=user_id).order_by(Transaction.created_at.desc())
        )
        result = await session.execute(query)
        return result.scalars().all()

async def get_transaction_by_id(user_id: int, txn_id: int) -> Transaction | None:
    async with get_session() as session:
        query = (
            select(Transaction).options(selectinload(Transaction.wallet))
            .filter_by(user_id=user_id, id=txn_id)
        )
        result = await session.execute(query)
        return result.scalars().first()

async def search_transactions(user_id: int, query_str: str, limit: int = 10) -> list[Transaction]:
    async with get_session() as session:
        all_wallets = await get_wallets(user_id)
        if not all_wallets:
            query = select(Transaction).options(selectinload(Transaction.wallet)).filter(Transaction.user_id == user_id, Transaction.note.ilike(f"%{query_str}%"))
            result = await session.execute(query)
            return result.scalars().all()

        wallet_names = [w.name for w in all_wallets]
        wallet_map = {w.name.lower(): w.id for w in all_wallets}
        
        query_words = query_str.lower().split()
        found_wallet_id = None
        note_keywords = list(query_words)
        word_to_remove = None

        for word in query_words:
            match = process.extractOne(word, wallet_names)
            if match and match[1] > 80:
                matched_name = match[0]
                found_wallet_id = wallet_map[matched_name.lower()]
                word_to_remove = word
                break

        if word_to_remove:
            note_keywords = [kw for kw in note_keywords if kw != word_to_remove and kw not in ['in', 'from', 'on', 'at', 'using']]

        note_search_term = " ".join(note_keywords)
        query = select(Transaction).options(selectinload(Transaction.wallet)).filter(Transaction.user_id == user_id)

        if found_wallet_id:
            query = query.filter(Transaction.wallet_id == found_wallet_id)
        if note_search_term:
            query = query.filter(Transaction.note.ilike(f"%{note_search_term}%"))

        query = query.order_by(Transaction.created_at.desc()).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()

async def update_transaction(user_id: int, txn_id: int, new_data: dict) -> Transaction | None:
    async with get_session() as session:
        updates = {key: value for key, value in new_data.items() if value is not None}
        if not updates:
            return await get_transaction_by_id(user_id, txn_id)
        query = update(Transaction).where(Transaction.id == txn_id, Transaction.user_id == user_id).values(**updates)
        await session.execute(query)
        return await get_transaction_by_id(user_id, txn_id)

async def delete_transaction_and_update_wallet(transaction: Transaction) -> bool:
    async with get_session() as session:
        wallet = await session.get(Wallet, transaction.wallet_id)
        if not wallet:
            return False

        if transaction.type in ['expense', 'withdrawal']:
            wallet.balance += transaction.amount
        elif transaction.type in ['income', 'deposit']:
            wallet.balance -= transaction.amount
        
        await session.delete(transaction)
        return True

async def delete_all_transactions(user_id: int) -> int:
    async with get_session() as session:
        count_query = select(func.count(Transaction.id)).where(Transaction.user_id == user_id)
        result = await session.execute(count_query)
        deleted_count = result.scalar_one_or_none() or 0

        if deleted_count > 0:
            await session.execute(update(Wallet).where(Wallet.user_id == user_id).values(balance=0.0))
            await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
        
        return deleted_count

# ===================================================================
# Wallet and Transfer Functions
# ===================================================================

async def get_wallet_by_id(wallet_id: int) -> Wallet | None:
    async with get_session() as session:
        return await session.get(Wallet, wallet_id)

async def create_wallet(user_id: int, name: str, category: str = 'Expense', initial_balance: float = 0.0) -> Wallet:
    async with get_session() as session:
        existing_wallet = await _get_exact_wallet_by_name(user_id, name)
        if existing_wallet:
            return existing_wallet
            
        new_wallet = Wallet(user_id=user_id, name=name, category=category, balance=initial_balance)
        session.add(new_wallet)
        await session.flush()
        await session.refresh(new_wallet)
        return new_wallet

async def get_wallets(user_id: int) -> list[Wallet]:
    async with get_session() as session:
        query = select(Wallet).filter_by(user_id=user_id).order_by(Wallet.name)
        result = await session.execute(query)
        return result.scalars().all()

async def get_wallet_by_name(user_id: int, name: str) -> Wallet | None:
    async with get_session() as session:
        all_wallets = await get_wallets(user_id)
        if not all_wallets:
            return None
        wallet_map = {wallet.name: wallet for wallet in all_wallets}
        best_match = process.extractOne(name, wallet_map.keys())
        if best_match and best_match[1] > 80:
            return wallet_map[best_match[0]]
        return None

async def update_wallet_balance(wallet_id: int, amount: float, transaction_type: str):
    async with get_session() as session:
        wallet = await session.get(Wallet, wallet_id)
        if wallet:
            if transaction_type in ['expense', 'withdrawal']:
                wallet.balance -= amount
            elif transaction_type in ['income', 'deposit']:
                wallet.balance += amount

async def record_transfer(user_id: int, from_wallet_id: int, to_wallet_id: int, amount: float, note: str = None) -> Transfer:
    async with get_session() as session:
        from_wallet = await session.get(Wallet, from_wallet_id)
        to_wallet = await session.get(Wallet, to_wallet_id)
        from_wallet.balance -= amount
        to_wallet.balance += amount
        new_transfer = Transfer(user_id=user_id, from_wallet_id=from_wallet_id, to_wallet_id=to_wallet_id, amount=amount, note=note)
        session.add(new_transfer)
        await session.flush()
        await session.refresh(new_transfer)
        return new_transfer

async def get_transactions_for_wallet_period(user_id: int, wallet_id: int, period: str) -> list[Transaction]:
    async with get_session() as session:
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
    max_retries = 3
    retry_delay = 0.5
    for attempt in range(max_retries):
        try:
            async with get_session() as session:
                sum_query = select(func.sum(case((Transaction.type.in_(['expense', 'withdrawal']), -Transaction.amount), else_=Transaction.amount))).where(Transaction.wallet_id == wallet_id)
                result = await session.execute(sum_query)
                new_balance = result.scalar_one_or_none() or 0.0
                wallet_update_stmt = update(Wallet).where(Wallet.id == wallet_id).values(balance=new_balance, is_updating=False)
                await session.execute(wallet_update_stmt)
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

async def add_transaction_and_flag(user_id: int, tx_data: dict, wallet_id: int) -> Transaction:
    async with get_session() as session:
        txn = Transaction(user_id=user_id, wallet_id=wallet_id, amount=abs(tx_data.get("amount")), note=tx_data.get("note"), type=tx_data.get("type", "expense"), category=tx_data.get("category", "Other"))
        session.add(txn)
        wallet_update_stmt = update(Wallet).where(Wallet.id == wallet_id).values(is_updating=True)
        await session.execute(wallet_update_stmt)
        await session.flush()
        await session.refresh(txn)
        return txn

async def _get_exact_wallet_by_name(user_id: int, name: str) -> Wallet | None:
    async with get_session() as session:
        query = select(Wallet).filter(Wallet.user_id == user_id, Wallet.name.ilike(name))
        result = await session.execute(query)
        return result.scalars().first()

# ===================================================================
# Data Analysis and Summary Functions
# ===================================================================

async def get_financial_summary(user_id: int) -> dict:
    async with get_session() as session:
        summary = {"total_expense": 0.0, "total_income": 0.0, "net_investment": 0.0, "goal_status": "Not Set"}
        expense_tx_query = (
            select(Transaction.type, func.sum(Transaction.amount).label("total_amount"))
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

        investment_balance_query = (
            select(func.sum(Wallet.balance).label("total_balance"))
            .where(Wallet.user_id == user_id, Wallet.category == 'Investment')
        )
        investment_result = await session.execute(investment_balance_query)
        summary['net_investment'] = investment_result.scalar_one_or_none() or 0.0

        goal_query = select(Goal).where(Goal.user_id == user_id)
        goal_result = await session.execute(goal_query)
        user_goal = goal_result.scalars().first()

        if user_goal and user_goal.target_amount > 0:
            percentage = (summary['net_investment'] / user_goal.target_amount) * 100
            summary['goal_status'] = f"{percentage:.1f}% Achieved"

        return summary

async def delete_wallet_and_associated_data(wallet_id: int) -> bool:
    async with get_session() as session:
        try:
            wallet = await session.get(Wallet, wallet_id)
            if not wallet:
                logger.warning(f"Attempted to delete a non-existent wallet with ID: {wallet_id}")
                return False
            await session.execute(delete(Transfer).where((Transfer.from_wallet_id == wallet_id) | (Transfer.to_wallet_id == wallet_id)))
            await session.execute(delete(Transaction).where(Transaction.wallet_id == wallet_id))
            await session.delete(wallet)
            return True
        except Exception as e:
            logger.error(f"Error during wallet deletion for ID {wallet_id}: {e}", exc_info=True)
            await session.rollback()
            return False
    
async def delete_all_user_data(user_id: int) -> bool:
    async with get_session() as session:
        try:
            await session.execute(delete(Transfer).where(Transfer.user_id == user_id))
            await session.execute(delete(Goal).where(Goal.user_id == user_id))
            await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
            await session.execute(delete(Wallet).where(Wallet.user_id == user_id))
            return True
        except Exception as e:
            logger.error(f"Error during complete data deletion for user {user_id}: {e}", exc_info=True)
            await session.rollback()
            return False
    
async def update_wallet(wallet_id: int, updates: dict) -> Wallet | None:
    async with get_session() as session:
        if not updates:
            return await session.get(Wallet, wallet_id)
        await session.execute(update(Wallet).where(Wallet.id == wallet_id).values(**updates))
        return await session.get(Wallet, wallet_id)

async def get_trend_data(user_id: int, period: str, wallet_category: str) -> pd.DataFrame:
    async with get_session() as session:
        if period == 'monthly': period_format = '%Y-%m'
        elif period == 'yearly': period_format = '%Y'
        elif period == 'quarterly': period_format = "strftime('%Y', created_at) || '-Q' || ((strftime('%m', created_at) - 1) / 3 + 1)"
        else: return pd.DataFrame()

        period_expression = func.strftime(period_format, Transaction.created_at) if '||' not in period_format else func.literal_column(period_format)

        query = (
            select(
                period_expression.label("period"),
                func.sum(case((Transaction.type.in_(['income', 'deposit']), Transaction.amount), else_=0)).label("income"),
                func.sum(case((Transaction.type.in_(['expense', 'withdrawal']), Transaction.amount), else_=0)).label("expense")
            )
            .join(Wallet, Wallet.id == Transaction.wallet_id)
            .where(Transaction.user_id == user_id, Wallet.category == wallet_category)
            .group_by("period").order_by("period")
        )
        result = await session.execute(query)
        df = pd.DataFrame(result.all(), columns=['Period', 'Income', 'Expense'])
        return df

def _get_period_filter(period_type: str, period_value: str):
    if period_type == 'monthly': return func.strftime('%Y-%m', Transaction.created_at) == period_value
    elif period_type == 'yearly': return func.strftime('%Y', Transaction.created_at) == period_value
    elif period_type == 'quarterly':
        year, quarter = period_value.split('-Q')
        q_start_month = (int(quarter) - 1) * 3 + 1
        q_end_month = q_start_month + 2
        return ((func.strftime('%Y', Transaction.created_at) == year) & (func.strftime('%m', Transaction.created_at).between(f'{q_start_month:02}', f'{q_end_month:02}')))
    return None

async def get_period_comparison_data(user_id: int, wallet_category: str, period_type: str, period1_val: str, period2_val: str) -> dict:
    async def _get_metrics(period_value):
        async with get_session() as session:
            period_filter = _get_period_filter(period_type, period_value)
            if period_filter is None: return {"income": 0, "expense": 0}
            query = (
                select(
                    func.sum(case((Transaction.type.in_(['income', 'deposit']), Transaction.amount), else_=0)).label("income"),
                    func.sum(case((Transaction.type.in_(['expense', 'withdrawal']), Transaction.amount), else_=0)).label("expense")
                )
                .join(Wallet, Wallet.id == Transaction.wallet_id)
                .where(Transaction.user_id == user_id, Wallet.category == wallet_category, period_filter)
            )
            result = await session.execute(query)
            data = result.first()
            return {"income": data.income or 0, "expense": data.expense or 0}

    data1 = await _get_metrics(period1_val)
    data2 = await _get_metrics(period2_val)
    return {"period1": data1, "period2": data2}
