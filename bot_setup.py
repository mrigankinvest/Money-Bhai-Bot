# /bot_setup.py

import logging
from telegram import BotCommand
from telegram.ext import Application

logger = logging.getLogger(__name__)

async def set_bot_commands(application: Application) -> None:
    """
    Sets the bot's command menu that users see in the Telegram interface.
    This is called once on startup.
    """
    commands = [
        BotCommand("aboutme", "ℹ️ About Money Bhai Bot"),
        BotCommand("home", "🏠 Main Dashboard"),
        BotCommand("actions", "⚡ Quick Actions (Add, Edit, etc.)"),
        BotCommand("records", "📂 View Past Records"),
        BotCommand("investments", "📈 Manage Investments"),
        BotCommand("statistics", "📊 View Charts & Statistics"),
        BotCommand("plannedpayments", "🗓️ Upcoming Planned Payments"),
        BotCommand("budgets", "💰 Set & View Budgets"),
        BotCommand("debt", "💸 Track Debt"),
        BotCommand("goals", "🎯 Set & View Financial Goals"),
        BotCommand("follow", "🔗 Follow us on Social Media"),
        BotCommand("contact", "💬 Contact Support")
    ]
    
    try:
        await application.bot.set_my_commands(commands)
        logger.info("Bot command menu has been set successfully.")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}", exc_info=True)

