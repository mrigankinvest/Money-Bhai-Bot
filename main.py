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
from config import BOT_TOKEN
from db.database import create_db_and_tables

# ===================================================================
# 1. Import all handlers from their modular files
# ===================================================================

# --- Simple Commands ---
from handlers.commands import start, summary, help_command, fix_stuck_wallets

# --- Generic Callback Router ---
from handlers.callbacks import handle_callback

# --- Main Message Handler (Entry point for most conversations) ---
from handlers.message_handler import handle_message

# --- Conversation State Handlers ---
from handlers.conversations.states import *
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
    create_wallet_conv_handler, # This one is self-contained, starting from a button
    edit_wallet_start, edit_wallet_select_field, edit_wallet_ask_value, edit_wallet_get_new_value, edit_wallet_cancel,
    delete_wallet_start, delete_wallet_confirm, delete_wallet_cancel as manage_wallet_delete_cancel
)
from handlers.conversations.analysis import analysis_conv_handler # Self-contained

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


def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    logger.info("🚀 Money Bhai Bot is starting...")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ===================================================================
    # 3. Define the Master ConversationHandler
    # ===================================================================
    
    # This handler orchestrates all conversations that start from a text message.
    main_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            # Direct entry for editing a transaction from a button (e.g., post-add menu)
            CallbackQueryHandler(edit_transaction_direct_start, pattern='^edit_action_txn_')
        ],
        states={
            # States from add_txn.py (single add flow)
            CONFIRM_DEFAULT_WALLET: [CallbackQueryHandler(confirm_default_wallet, pattern='^default_wallet_')],
            AWAITING_WALLET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_wallet_name)],
            HANDLE_UNKNOWN_WALLET: [CallbackQueryHandler(handle_new_wallet_choice, pattern='^(create_wallet_confirm|add_txn_cancel)$')],
            
            # States from add_txn.py (multi-add flow)
            AWAIT_ASSIGNMENT_STRATEGY: [CallbackQueryHandler(handle_assignment_strategy, pattern='^multi_tx_strategy_')],
            AWAIT_SINGLE_WALLET_CHOICE: [CallbackQueryHandler(assign_single_wallet_to_all, pattern='^multi_tx_select_wallet_'), CallbackQueryHandler(back_to_strategy, pattern='^multi_tx_strategy_back$')],
            ASSIGNING_INDIVIDUALLY: [CallbackQueryHandler(assign_individual_wallet_step, pattern='^multi_tx_assign_'), CallbackQueryHandler(back_to_strategy, pattern='^multi_tx_strategy_back$')],

            # States from edit_txn.py
            SELECTING_EDIT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_start), CallbackQueryHandler(edit_select_field, pattern='^edit_select_')],
            GETTING_NEW_EDIT_VALUE: [CallbackQueryHandler(edit_get_field_and_ask_value, pattern='^edit_field_'), MessageHandler(filters.TEXT & ~filters.COMMAND, edit_get_new_value)],

            # State from delete_txn.py
            SELECTING_DELETE_CANDIDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_start), CallbackQueryHandler(delete_perform_deletion, pattern='^delete_confirm_')],

            # States from manage_wallets.py
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
            CommandHandler("start", start),
        ],
        per_message=False # Allows multiple conversations to happen without interfering
    )

    # ===================================================================
    # 4. Register All Handlers with the Application
    # ===================================================================

    # Add conversation handlers first, as they are more specific
    app.add_handler(main_conv_handler)
    app.add_handler(create_wallet_conv_handler) # From manage_wallets.py
    app.add_handler(analysis_conv_handler)      # From analysis.py

    # Add simple command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("fix", fix_stuck_wallets))

    # Add the generic callback handler last as a fallback for any button clicks
    # not caught by a conversation.
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    # ===================================================================
    # 5. Run the Bot
    # ===================================================================

    logger.info("✅ Money Bhai Bot is running. Press Ctrl-C to stop.")
    app.run_polling()


if __name__ == '__main__':
    main()