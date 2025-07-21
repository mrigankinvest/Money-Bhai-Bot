import logging
from pathlib import Path
from functools import wraps
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from .models import Base

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DB_FILE = PROJECT_ROOT / "money_bhai.db"
SQLALCHEMY_DATABASE_URL = f"sqlite+aiosqlite:///{DB_FILE}"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=True
)

AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

async def get_db_session():
    async with AsyncSessionLocal() as session:
        yield session

async def create_db_and_tables():
    from . import models  # Import models to ensure they are registered with Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables successfully created.")

def with_db_session(func):
    """Decorator to inject a database session into a handler function."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # The first two arguments for a handler are typically 'update' and 'context'
        update, context = args[0], args[1]
        
        session_generator = get_db_session()
        session = await anext(session_generator)
        try:
            # Pass the session as the third positional argument
            return await func(update, context, session)
        finally:
            await session.close()
    return wrapper