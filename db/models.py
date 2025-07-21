# db/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, func, BigInteger, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from sqlalchemy.orm import declarative_base

# Create the Base class that all models will inherit
Base = declarative_base()

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    name = Column(String, nullable=False)
    balance = Column(Float, default=0.0)
    category = Column(String, nullable=False, default='Expense') # 'Expense' or 'Investment'
    is_updating = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transactions = relationship("Transaction", back_populates="wallet")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    wallet = relationship("Wallet", back_populates="transactions")
    amount = Column(Float, nullable=False)
    note = Column(String, nullable=False)
    type = Column(String, default="expense", nullable=False)
    category = Column(String, default="Other", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# --- NEW: Transfer Model ---
class Transfer(Base):
    __tablename__ = "transfers"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    from_wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    to_wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    amount = Column(Float, nullable=False)
    note = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    from_wallet = relationship("Wallet", foreign_keys=[from_wallet_id])
    to_wallet = relationship("Wallet", foreign_keys=[to_wallet_id])
# ---------------------------

class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True) # <-- This line is crucial
    user_id = Column(BigInteger, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    target_amount = Column(Float, nullable=False)
    monthly_contribution = Column(Float)
    deadline = Column(DateTime(timezone=True))