# tests/test_db_writer.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from db.base import Base
import db.db_writer as db_writer

# Use a separate, in-memory SQLite database for each test session
@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with AsyncSessionLocal() as s:
        yield s
    await engine.dispose()

@pytest.mark.asyncio
async def test_create_wallet(session):
    """Tests ADD-WAL-01, ADD-WAL-02, ADD-WAL-04, ADD-WAL-07"""
    user_id = 101
    # Test simple creation
    wallet1 = await db_writer.create_wallet(session, user_id, "HDFC", "Expense")
    assert wallet1.name == "HDFC" and wallet1.category == "Expense"

    # Test creation with initial balance
    wallet2 = await db_writer.create_wallet(session, user_id, "Zerodha", "Investment", 10000)
    assert wallet2.balance == 10000 and wallet2.category == "Investment"
    
    # Test duplicate creation
    wallet3 = await db_writer.create_wallet(session, user_id, "hdfc", "Expense")
    assert wallet3.id == wallet1.id

@pytest.mark.asyncio
async def test_add_transaction_updates_balance(session):
    """Tests ADD-TXN-01, ADD-TXN-03"""
    user_id = 102
    wallet = await db_writer.create_wallet(session, user_id, "Jupiter", "Expense", 5000)
    
    # Test expense
    await db_writer.add_transaction(session, user_id, {'amount': 500, 'note': 'pizza', 'type': 'expense'}, wallet.id)
    await session.refresh(wallet)
    assert wallet.balance == 4500

    # Test income
    await db_writer.add_transaction(session, user_id, {'amount': 1000, 'note': 'refund', 'type': 'income'}, wallet.id)
    await session.refresh(wallet)
    assert wallet.balance == 5500

@pytest.mark.asyncio
async def test_record_transfer(session):
    """Tests ADD-TRN-01"""
    user_id = 103
    wallet1 = await db_writer.create_wallet(session, user_id, "HDFC", "Expense", 10000)
    wallet2 = await db_writer.create_wallet(session, user_id, "Zerodha", "Investment", 5000)

    await db_writer.record_transfer(session, user_id, wallet1.id, wallet2.id, 2000)
    await session.refresh(wallet1)
    await session.refresh(wallet2)

    assert wallet1.balance == 8000
    assert wallet2.balance == 7000

@pytest.mark.asyncio
async def test_fuzzy_search_transactions(session):
    """Tests ADD-EDG-06, ADD-TRN-02"""
    user_id = 104
    wallet = await db_writer.create_wallet(session, user_id, "Jupiter", "Expense")
    await db_writer.add_transaction(session, user_id, {'amount': 50, 'note': 'chai', 'type': 'expense'}, wallet.id)

    # Test with typo
    results = await db_writer.search_transactions(session, user_id, "chai from jupitr")
    assert len(results) == 1
    assert results[0].note == "chai"

    # Test with no match
    results_none = await db_writer.search_transactions(session, user_id, "coffee")
    assert len(results_none) == 0