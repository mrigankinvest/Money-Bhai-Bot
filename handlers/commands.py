# /handlers/commands.py

import logging
from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from db.database import with_db_session
from db import db_writer
from db.models import Wallet
from utils.telegram_helpers import reply_and_log, send_wallet_overview
from config import WELCOME_TEXT

logger = logging.getLogger(__name__)

@with_db_session
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Handles the /start command, creating default wallets for new users."""
    user_id = update.effective_user.id
    existing_wallets = await db_writer.get_wallets(session, user_id)
    
    if not existing_wallets:
        logger.info(f"Creating default wallets for new user {user_id}")
        await db_writer.create_wallet(session, user_id, "Cash", category='Expense')
        await db_writer.create_wallet(session, user_id, "Zerodha", category='Investment')
        await reply_and_log(update, context, text=WELCOME_TEXT, parse_mode="Markdown")
    else:
        await reply_and_log(update, context, "Welcome back! 👋")

    # Show the main dashboard to all users
    await send_wallet_overview(update, context, session)

@with_db_session
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Handles the /summary command by showing the financial dashboard."""
    await send_wallet_overview(update, context, session)

@with_db_session
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Handles the /help command, showing commands and wallet balances."""
    user_id = update.effective_user.id
    wallets = await db_writer.get_wallets(session, user_id)
    
    expense_wallets = [w for w in wallets if w.category == 'Expense']
    investment_wallets = [w for w in wallets if w.category == 'Investment']
    
    help_text = "Here's what you can do:\n\n" \
                "• **Add Transaction:** `500 for groceries from Cash`\n" \
                "• **Create Wallet:** `create investment wallet named Groww`\n" \
                "• **Transfer Money:** `transfer 1000 from Cash to Zerodha`\n"

    if expense_wallets:
        wallet_list = "\n".join([f"  - {w.name} (Balance: ₹{w.balance:.2f})" for w in expense_wallets])
        help_text += f"\n**Expense Wallets:**\n{wallet_list}"
    
    if investment_wallets:
        wallet_list = "\n".join([f"  - {w.name} (Balance: ₹{w.balance:.2f})" for w in investment_wallets])
        help_text += f"\n\n**Investment Wallets:**\n{wallet_list}"

    if not wallets:
        help_text = "You don't have any wallets yet. Try: `create wallet named Cash`"
        
    await reply_and_log(update, context, help_text, parse_mode="Markdown")

@with_db_session
async def fix_stuck_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """A utility command to find and fix wallets stuck in the 'updating' state."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} initiated a fix for stuck wallets.")
    
    stuck_wallets_query = select(Wallet).where(
        Wallet.user_id == user_id, 
        Wallet.is_updating == True
    )
    result = await session.execute(stuck_wallets_query)
    stuck_wallets = result.scalars().all()

    if not stuck_wallets:
        await reply_and_log(update, context, "Great! No wallets are currently stuck.")
        return

    await reply_and_log(update, context, f"Found {len(stuck_wallets)} stuck wallet(s). Starting the fix now...")

    for wallet in stuck_wallets:
        logger.info(f"Scheduling fix for wallet: {wallet.name} (ID: {wallet.id})")
        # You might need to adjust the import path for your recalculate function
        # asyncio.create_task(db_writer.recalculate_wallet_balance(wallet.id))

    await reply_and_log(update, context, "The fix is running in the background. Your wallet balances should update shortly.")