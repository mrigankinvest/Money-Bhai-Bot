# /handlers/conversations/manage_wallets.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CommandHandler
)

# --- Corrected Imports ---
from db.database import get_session # Use the new session manager
from db import db_writer
from utils.telegram_helpers import reply_and_log, edit_and_log
from .states import (
    AWAITING_NEW_WALLET_NAME, AWAITING_NEW_WALLET_BALANCE,
    SELECT_WALLET_TO_EDIT, SELECT_WALLET_FIELD, AWAIT_NEW_WALLET_VALUE,
    CONFIRM_WALLET_DELETION
)


# =============================================================================
# === FLOW 1: CREATE A NEW WALLET =============================================
# =============================================================================

async def create_wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the wallet creation conversation from a button click."""
    query = update.callback_query
    await query.answer()
    
    wallet_category = query.data.split('_')[-1]
    context.user_data['new_wallet_category'] = wallet_category
    
    await edit_and_log(query, context, text=f"Okay, let's create a new '{wallet_category}' wallet. What would you like to name it?")
    return AWAITING_NEW_WALLET_NAME

async def create_wallet_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the name for the new wallet and asks for the balance."""
    context.user_data['new_wallet_name'] = update.message.text
    await reply_and_log(update, context, "Got it. Now, what is the initial balance? (Enter 0 if none)")
    return AWAITING_NEW_WALLET_BALANCE

async def create_wallet_get_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the balance and creates the wallet."""
    try:
        balance = float(update.message.text)
    except ValueError:
        await reply_and_log(update, context, "That's not a valid number. Please enter the initial balance again.")
        return AWAITING_NEW_WALLET_BALANCE
        
    user_id = update.effective_user.id
    name = context.user_data['new_wallet_name']
    category = context.user_data['new_wallet_category']
    
    async with get_session() as session:
        new_wallet = await db_writer.create_wallet(session, user_id, name, category, balance)

    keyboard = [[InlineKeyboardButton("✏️ Edit This Wallet", callback_data=f"edit_wallet_direct_{new_wallet.id}")]]
    await reply_and_log(
        update, context,
        f"✅ Success! Your new '{category}' wallet named '{name}' has been created with a balance of ₹{balance:.2f}.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    for key in ['new_wallet_name', 'new_wallet_category']:
        context.user_data.pop(key, None)
    return ConversationHandler.END

async def create_wallet_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the wallet creation conversation."""
    await reply_and_log(update, context, text="Okay, wallet creation cancelled.")
    for key in ['new_wallet_name', 'new_wallet_category']:
        context.user_data.pop(key, None)
    return ConversationHandler.END

# The ConversationHandler definition itself
create_wallet_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(create_wallet_start, pattern='^create_wallet_start_')],
    states={
        AWAITING_NEW_WALLET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_wallet_get_name)],
        AWAITING_NEW_WALLET_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_wallet_get_balance)],
    },
    fallbacks=[CommandHandler('cancel', create_wallet_cancel)],
)


# =============================================================================
# === FLOW 2: EDIT AN EXISTING WALLET =========================================
# =============================================================================

async def edit_wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for editing a wallet from a text command."""
    async with get_session() as session:
        wallets = await db_writer.get_wallets(session, update.effective_user.id)
    
    if not wallets:
        await reply_and_log(update, context, "You don't have any wallets to edit.")
        return ConversationHandler.END
        
    keyboard = [[InlineKeyboardButton(f"💳 {w.name}", callback_data=f"edit_wallet_select_{w.id}")] for w in wallets]
    await reply_and_log(update, context, "Which wallet would you like to edit?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_WALLET_TO_EDIT

async def edit_wallet_direct_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for editing a wallet from a direct button click."""
    query = update.callback_query
    await query.answer()
    wallet_id = int(query.data.split('_')[-1])
    context.user_data['edit_wallet_id'] = wallet_id
    keyboard = [
        [InlineKeyboardButton("Name", callback_data="edit_wallet_field_name")],
        [InlineKeyboardButton("Category", callback_data="edit_wallet_field_category")]
    ]
    await edit_and_log(query, context, "What would you like to change?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_WALLET_FIELD

async def edit_wallet_select_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """After user selects a wallet, this asks which field to edit."""
    query = update.callback_query
    await query.answer()
    wallet_id = int(query.data.split('_')[-1])
    context.user_data['edit_wallet_id'] = wallet_id
    keyboard = [
        [InlineKeyboardButton("Name", callback_data="edit_wallet_field_name")],
        [InlineKeyboardButton("Category", callback_data="edit_wallet_field_category")]
    ]
    await edit_and_log(query, context, "What would you like to change?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_WALLET_FIELD

async def edit_wallet_ask_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """After user selects a field, this asks for the new value."""
    query = update.callback_query
    await query.answer()
    field_to_edit = query.data.split('_')[-1]
    context.user_data['edit_wallet_field'] = field_to_edit
    if field_to_edit == 'category':
        keyboard = [
            [InlineKeyboardButton("Expense", callback_data="edit_wallet_value_Expense")],
            [InlineKeyboardButton("Investment", callback_data="edit_wallet_value_Investment")]
        ]
        await edit_and_log(query, context, "Please choose the new category:", reply_markup=InlineKeyboardMarkup(keyboard))
    else: # It's 'name'
        await edit_and_log(query, context, f"Okay, what should the new name be?")
    return AWAIT_NEW_WALLET_VALUE

async def edit_wallet_get_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the new value and performs the update."""
    query = update.callback_query
    field = context.user_data.get('edit_wallet_field')
    wallet_id = context.user_data.get('edit_wallet_id')
    
    if query:
        await query.answer()
        new_value = query.data.split('_')[-1]
        message_to_edit = query.message
    else:
        new_value = update.message.text
        message_to_edit = update.message

    updates = {field: new_value}
    async with get_session() as session:
        updated_wallet = await db_writer.update_wallet(session, wallet_id, updates)

    reply_text = f"✅ Wallet updated successfully!\n\n**Name:** {updated_wallet.name}\n**Category:** {updated_wallet.category}" if updated_wallet else "Sorry, an error occurred."
    
    if query:
        await message_to_edit.edit_text(reply_text, parse_mode="Markdown")
    else:
        await message_to_edit.reply_text(reply_text, parse_mode="Markdown")

    for key in ['edit_wallet_id', 'edit_wallet_field', 'edit_wallet_name']:
        context.user_data.pop(key, None)
    return ConversationHandler.END

async def edit_wallet_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await reply_and_log(update, context, "Wallet edit cancelled.")
    return ConversationHandler.END

# The ConversationHandler definition itself
edit_wallet_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(edit_wallet_direct_start, pattern='^edit_wallet_direct_')],
    states={
        SELECT_WALLET_TO_EDIT: [CallbackQueryHandler(edit_wallet_select_field, pattern='^edit_wallet_select_')],
        SELECT_WALLET_FIELD: [CallbackQueryHandler(edit_wallet_ask_value, pattern='^edit_wallet_field_')],
        AWAIT_NEW_WALLET_VALUE: [
            CallbackQueryHandler(edit_wallet_get_new_value, pattern='^edit_wallet_value_'),
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_wallet_get_new_value)
        ],
    },
    fallbacks=[CommandHandler('cancel', edit_wallet_cancel)],
)


# =============================================================================
# === FLOW 3: DELETE A WALLET =================================================
# =============================================================================

async def delete_wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the wallet deletion confirmation process."""
    wallet_name = context.user_data.get('delete_wallet_name')
    if not wallet_name:
        await reply_and_log(update, context, "Which wallet do you want to delete? e.g., 'delete my bank wallet'.")
        return ConversationHandler.END

    async with get_session() as session:
        wallet = await db_writer.get_wallet_by_name(session, update.effective_user.id, wallet_name)
        
    if not wallet:
        await reply_and_log(update, context, f"Sorry, I couldn't find a wallet named '{wallet_name}'.")
        return ConversationHandler.END

    context.user_data['wallet_to_delete_id'] = wallet.id
    
    warning_text = (f"⚠️ *DANGER!* Are you sure you want to delete the wallet '{wallet.name}'?\n\nThis will permanently delete the wallet AND all its data. *This action cannot be undone.*")
    keyboard = [
        [InlineKeyboardButton("✅ YES, DELETE EVERYTHING", callback_data=f"confirm_delete_wallet_{wallet.id}")],
        [InlineKeyboardButton("❌ NO, CANCEL", callback_data="cancel_wallet_deletion")]
    ]
    await reply_and_log(update, context, warning_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CONFIRM_WALLET_DELETION

async def delete_wallet_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's confirmation to delete the wallet."""
    query = update.callback_query
    await query.answer()

    wallet_id = context.user_data.get('wallet_to_delete_id')
    if f"confirm_delete_wallet_{wallet_id}" != query.data:
        await edit_and_log(query, context, "Something went wrong. Deletion cancelled for safety.")
        return ConversationHandler.END

    async with get_session() as session:
        wallet = await db_writer.get_wallet_by_id(session, wallet_id)
        wallet_name = wallet.name if wallet else "unknown"
        success = await db_writer.delete_wallet_and_associated_data(session, wallet_id)

    if success:
        await edit_and_log(query, context, f"✅ The wallet '{wallet_name}' and all its data have been permanently deleted.")
    else:
        await edit_and_log(query, context, "❌ An error occurred while trying to delete the wallet.")

    for key in ['delete_wallet_name', 'wallet_to_delete_id']:
        context.user_data.pop(key, None)
    return ConversationHandler.END

async def delete_wallet_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the wallet deletion process."""
    query = update.callback_query
    await query.answer()
    await edit_and_log(query, context, text="👍 Deletion cancelled. Your wallet is safe.")
    for key in ['delete_wallet_name', 'wallet_to_delete_id']:
        context.user_data.pop(key, None)
    return ConversationHandler.END

# The ConversationHandler definition itself
delete_wallet_conv_handler = ConversationHandler(
    entry_points=[],
    states={
        CONFIRM_WALLET_DELETION: [
            CallbackQueryHandler(delete_wallet_confirm, pattern='^confirm_delete_wallet_'),
            CallbackQueryHandler(delete_wallet_cancel, pattern='^cancel_wallet_deletion$')
        ]
    },
    fallbacks=[CommandHandler('cancel', delete_wallet_cancel)],
)
