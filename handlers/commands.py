# /handlers/commands.py

import logging
import asyncio
from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

# --- Corrected Imports ---
from db.database import get_session
from db import db_writer
from db.models import Wallet
from utils.telegram_helpers import reply_and_log, send_wallet_overview
from config import WELCOME_TEXT

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /start command for returning users, now personalized with their name.
    """
    user_id = update.effective_user.id
    
    # 1. Fetch the user's details from the database
    user = await db_writer.get_user_by_telegram_id(user_id)
    
    # 2. Use the name in the welcome message
    user_name = user.name if user and user.name else "Dost"
    await reply_and_log(update, context, f"Welcome back, {user_name}! 👋")
    
    # 3. Show the main dashboard
    await send_wallet_overview(update, context)

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /summary command by showing the financial dashboard."""
    await send_wallet_overview(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /help command, showing commands and wallet balances."""
    user_id = update.effective_user.id
    wallets = await db_writer.get_wallets(user_id)
    
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
        # Fetch the user's name to personalize the welcome message
        user = await db_writer.get_user_by_telegram_id(user_id)
        user_name = user.name if user and user.name else "Dost"
        help_text = (f"Welcome, *{user_name}*!\n\n"
                     "Main apki personal finance journey ka partner hun. Saare transactions wallets se record honge., with full encryption to protect your data\n"
                     "By default, aapke paas 'Cash' aur 'Investment' wallets hain.\n\n"
                     "Try examples like:\n"
                     "– `Create Zerodha Investment Wallet`\n"
                     "– `Create HDFC Credit card Wallet`\n"
                     "– `500 for pizza from my bank account`\n"
                     "– `create a new wallet named Credit Card`\n"
                     "– `transfer 1000 from Cash to Zerodha`\n"
                     "– `show my wallets` or `/start`\n"
                     "– `/help` for more options")
                     
        
    await reply_and_log(update, context, help_text, parse_mode="Markdown")

async def fix_stuck_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """A utility command to find and fix wallets stuck in the 'updating' state."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} initiated a fix for stuck wallets.")
    
    wallets = await db_writer.get_wallets(user_id)
    stuck_wallets = [w for w in wallets if w.is_updating]

    if not stuck_wallets:
        await reply_and_log(update, context, "Great! No wallets are currently stuck.")
        return

    await reply_and_log(update, context, f"Found {len(stuck_wallets)} stuck wallet(s). Starting the fix now...")

    tasks = [db_writer.recalculate_wallet_balance(wallet.id) for wallet in stuck_wallets]
    await asyncio.gather(*tasks)

    await reply_and_log(update, context, "The fix is running in the background. Your wallet balances should update shortly.")

# =============================================================================
# === NEW MENU COMMANDS =======================================================
# =============================================================================

async def home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /home command by showing the main dashboard."""
    async with get_session() as session:
        await send_wallet_overview(update, context)

async def aboutme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /aboutme command by providing information about the bot."""
    about_text = (
        "🤖 *Mera Naam Hai Money Bhai!* 💰\n\n"
        "Main aapka personal finance dost hoon, jo aapke paise ka hisaab-kitaab ekdum simple aur mazedaar bana dega!\n\n"
        "✨ *Main Kya Kar Sakta Hoon?*\n\n"
        "🗣️ **Natural Language:** Bas mujhe normal message bhejo, jaise dosto se baat karte ho! (e.g., `100 ka petrol dala ⛽`)\n\n"
        "💳 **Wallet Management:** Alag-alag wallets banao - Kharchon ke liye 🛍️, Investments ke liye 📈, ya aur kisi cheez ke liye!\n\n"
        "📊 **Data Analysis:** Apne kharchon ko beautiful charts aur graphs mein dekho. Pata lagao paisa jaa kahan raha hai!\n\n"
        "🔒 **Secure & Private:** Aapka saara data 100% safe aur private hai. Tension not!\n\n"
        "My goal is to help you get a clear picture of your finances without the hassle of complex apps 🚀"
    )
    await reply_and_log(update, context, about_text, parse_mode="Markdown")

async def actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /actions command."""
    await reply_and_log(update, context, "This feature is coming soon!")

async def records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /records command."""
    await reply_and_log(update, context, "This feature is coming soon!")

async def investments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /investments command."""
    await reply_and_log(update, context, "This feature is coming soon!")

async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /statistics command."""
    await reply_and_log(update, context, "This feature is coming soon!")

async def plannedpayments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /plannedpayments command."""
    await reply_and_log(update, context, "This feature is coming soon!")

async def budgets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /budgets command."""
    await reply_and_log(update, context, "This feature is coming soon!")

async def debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /debt command."""
    await reply_and_log(update, context, "This feature is coming soon!")

async def goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /goals command."""
    await reply_and_log(update, context, "This feature is coming soon!")

async def follow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /follow command."""
    await reply_and_log(update, context, "This feature is coming soon!")

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /contact command."""
    await reply_and_log(update, context, "This feature is coming soon!")