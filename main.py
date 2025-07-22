# /main.py

import logging
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler
)
# Using your config variable
from config import BOT_TOKEN 
from handlers import commands 
# Using your database function
from db.database import create_db_and_tables 
from bot_setup import set_bot_commands

# ===================================================================
# 1. Import all handlers from their modular files
# ===================================================================

# --- Simple Commands ---
from handlers.commands import (
    summary, help_command, fix_stuck_wallets, 
    # Import all the new menu commands
    home, aboutme, actions, records, investments, statistics,
    plannedpayments, budgets, debt, goals, follow, contact
)

# --- Generic Callback Router ---
from handlers.callbacks import handle_callback

# --- Main Message Handler (Entry point for most conversations) ---
from handlers.message_handler import handle_message

# --- Conversation State Handlers ---
from handlers.conversations.states import *
# Import the new onboarding handler and its states
from handlers.conversations import onboarding 
from handlers.conversations.add_txn import (
    confirm_default_wallet, receive_wallet_name, handle_new_wallet_choice, add_txn_cancel,
    handle_assignment_strategy, assign_single_wallet_to_all, assign_individual_wallet_step, back_to_strategy
)
from handlers.conversations.edit_txn import (
    edit_start, edit_transaction_direct_start, edit_select_field, edit_get_field_and_ask_value,
    edit_get_new_value, edit_cancel
)
from handlers.conversations.delete_txn import (
    delete_start, delete_perform_deletion, delete_cancel
)
from handlers.conversations.manage_wallets import (
    create_wallet_conv_handler, 
    edit_wallet_start, edit_wallet_select_field, edit_wallet_ask_value, edit_wallet_get_new_value, edit_wallet_cancel,
    delete_wallet_start, delete_wallet_confirm, delete_wallet_cancel as manage_wallet_delete_cancel
)
from handlers.conversations.analysis import analysis_conv_handler 

# ===================================================================
# 2. Configure Logging
# ===================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
# Reduce logging noise from libraries
for noisy_logger in ("httpx", "telegram.ext", "apscheduler"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

async def post_init(app: Application):
    """Post-initialization function to create database tables."""
    logger.info("Creating database tables...")
    await create_db_and_tables() 
    logger.info("Database tables created or already exist.")
    await set_bot_commands(app)


def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    logger.info("🚀 Money Bhai Bot is starting...")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build() 

    # ===================================================================
    # 3. Define Conversation Handlers
    # ===================================================================

    onboarding_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", onboarding.ask_for_name)],
        states={
            onboarding.GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding.ask_for_name_confirmation)],
            onboarding.CONFIRM_NAME: [
                CallbackQueryHandler(onboarding.save_name_confirmed, pattern="^confirm_name$"),
                CallbackQueryHandler(onboarding.change_name, pattern="^change_name$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", onboarding.cancel)],
        per_user=True,
        per_chat=True,
    )
    
    main_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            CallbackQueryHandler(edit_transaction_direct_start, pattern='^edit_action_txn_')
        ],
        states={
            CONFIRM_DEFAULT_WALLET: [CallbackQueryHandler(confirm_default_wallet, pattern='^default_wallet_')],
            AWAITING_WALLET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_wallet_name)],
            HANDLE_UNKNOWN_WALLET: [CallbackQueryHandler(handle_new_wallet_choice, pattern='^(create_wallet_confirm|add_txn_cancel)$')],
            AWAIT_ASSIGNMENT_STRATEGY: [CallbackQueryHandler(handle_assignment_strategy, pattern='^multi_tx_strategy_')],
            AWAIT_SINGLE_WALLET_CHOICE: [CallbackQueryHandler(assign_single_wallet_to_all, pattern='^multi_tx_select_wallet_'), CallbackQueryHandler(back_to_strategy, pattern='^multi_tx_strategy_back$')],
            ASSIGNING_INDIVIDUALLY: [CallbackQueryHandler(assign_individual_wallet_step, pattern='^multi_tx_assign_'), CallbackQueryHandler(back_to_strategy, pattern='^multi_tx_strategy_back$')],
            SELECTING_EDIT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_start), CallbackQueryHandler(edit_select_field, pattern='^edit_select_')],
            GETTING_NEW_EDIT_VALUE: [CallbackQueryHandler(edit_get_field_and_ask_value, pattern='^edit_field_'), MessageHandler(filters.TEXT & ~filters.COMMAND, edit_get_new_value)],
            SELECTING_DELETE_CANDIDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_start), CallbackQueryHandler(delete_perform_deletion, pattern='^delete_confirm_')],
            SELECT_WALLET_TO_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_wallet_start), CallbackQueryHandler(edit_wallet_select_field, pattern='^edit_wallet_select_')],
            SELECT_WALLET_FIELD: [CallbackQueryHandler(edit_wallet_ask_value, pattern='^edit_wallet_field_')],
            AWAIT_NEW_WALLET_VALUE: [CallbackQueryHandler(edit_wallet_get_new_value, pattern='^edit_wallet_value_'), MessageHandler(filters.TEXT & ~filters.COMMAND, edit_wallet_get_new_value)],
            CONFIRM_WALLET_DELETION: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_wallet_start), CallbackQueryHandler(delete_wallet_confirm, pattern='^confirm_delete_wallet_')],
        },
        fallbacks=[
            CallbackQueryHandler(edit_cancel, pattern='^edit_cancel$'),
            CallbackQueryHandler(delete_cancel, pattern='^delete_cancel$'),
            CallbackQueryHandler(add_txn_cancel, pattern='^add_txn_cancel$'),
            CallbackQueryHandler(manage_wallet_delete_cancel, pattern='^cancel_wallet_deletion$'),
            CommandHandler("start", onboarding.ask_for_name),
        ],
        per_message=False 
    )

    # ===================================================================
    # 4. Register All Handlers with the Application
    # ===================================================================

    # The new onboarding handler now manages the /start command.
    app.add_handler(onboarding_conv_handler)

    # 1. Handler for the /home command
    # This will trigger the initial dashboard view
    app.add_handler(CommandHandler("home", commands.home))

    # 2. Handler for all button clicks (callbacks)
    # This will handle clicks on "Time Horizon", "Expenses", "Income", etc.
    # We use a pattern that matches the start of your callback data
    app.add_handler(CallbackQueryHandler(commands.handle_button_press))
    
    # Your existing conversation handlers
    app.add_handler(main_conv_handler)
    app.add_handler(create_wallet_conv_handler)
    app.add_handler(analysis_conv_handler)

    # Your existing simple command handlers
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("fix", fix_stuck_wallets))

    # Add handlers for all the new menu commands
    app.add_handler(CommandHandler("home", home))
    app.add_handler(CommandHandler("aboutme", aboutme))
    app.add_handler(CommandHandler("actions", actions))
    app.add_handler(CommandHandler("records", records))
    app.add_handler(CommandHandler("investments", investments))
    app.add_handler(CommandHandler("statistics", statistics))
    app.add_handler(CommandHandler("plannedpayments", plannedpayments))
    app.add_handler(CommandHandler("budgets", budgets))
    app.add_handler(CommandHandler("debt", debt))
    app.add_handler(CommandHandler("goals", goals))
    app.add_handler(CommandHandler("follow", follow))
    app.add_handler(CommandHandler("contact", contact))

    # Generic callback handler
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    # ===================================================================
    # 5. Run the Bot
    # ===================================================================

    logger.info("✅ Money Bhai Bot is running. Press Ctrl-C to stop.")
    app.run_polling()


if __name__ == '__main__':
    main()
