import logging
from pathlib import Path
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .models import Base

logger = logging.getLogger(__name__)

# --- Keeping your existing path and URL setup ---
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DB_FILE = PROJECT_ROOT / "money_bhai.db"
SQLALCHEMY_DATABASE_URL = f"sqlite+aiosqlite:///{DB_FILE}"

# --- Using the more robust engine and session factory from our new version ---
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    # The connect_args for sqlite are not needed with aiosqlite driver
    echo=False 
)

# Create a configured "Session" class
async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# --- This is the key change ---
# Replacing your `get_db_session` generator and `with_db_session` decorator
# with a single, more modern context manager.
@asynccontextmanager
async def get_session() -> AsyncSession:
    """
    Provide a transactional scope around a series of operations.
    This will be used by db_writer.py and other data-handling files.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.error(f"Session rollback due to error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

# --- Keeping your existing table creation function ---
async def create_db_and_tables():
    """
    Creates all database tables defined in models.py if they don't exist.
    """
    # Import models locally to ensure they are registered with Base
    from . import models  
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables successfully created or already exist.")

