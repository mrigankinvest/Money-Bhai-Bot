# db/models.py

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime,
    ForeignKey, Enum as SQLAlchemyEnum, Boolean
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class User(Base):
    """Represents a user in the system."""
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    wallets = relationship("Wallet", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")

# --- This Enum is no longer used by the Wallet model ---
class WalletType(enum.Enum):
    EXPENSE = "Expense"
    INVESTMENT = "Investment"

class Wallet(Base):
    """Represents a user's wallet (e.g., Cash, Bank, Broker)."""
    __tablename__ = 'wallets'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String, nullable=False)
    # --- FIX: Use a simple String for category as expected by your code ---
    category = Column(String, nullable=False) 
    balance = Column(Float, default=0.0)
    # --- FIX: Add the missing is_updating column ---
    is_updating = Column(Boolean, default=False, nullable=False)
    is_deleted = Column(Boolean, default=False)

    user = relationship("User", back_populates="wallets")
    transactions = relationship("Transaction", back_populates="wallet")

class TransactionType(enum.Enum):
    EXPENSE = "Expense"
    INCOME = "Income"
    INVESTMENT = "Investment"
    WITHDRAWAL = "Withdrawal"
    DEPOSIT = "Deposit" # Added for consistency

class Transaction(Base):
    """Represents a single financial transaction."""
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    amount = Column(Float, nullable=False)
    # --- FIX: Use a simple String for type as expected by your code ---
    type = Column(String, nullable=False)
    category = Column(String)
    # --- FIX: Use 'note' instead of 'description' ---
    note = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, default=False)

    user = relationship("User", back_populates="transactions")
    wallet = relationship("Wallet", back_populates="transactions")

class Transfer(Base):
    """Represents a transfer of funds between two wallets."""
    __tablename__ = 'transfers'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    from_wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    to_wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    amount = Column(Float, nullable=False)
    note = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Goal(Base):
    """Represents a financial goal for a user."""
    __tablename__ = 'goals'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String, nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    deadline = Column(DateTime)
    is_completed = Column(Boolean, default=False)
