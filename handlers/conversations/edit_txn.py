# /handlers/conversations/edit_txn.py

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
from utils.formatting import format_transaction_details
from .states import SELECTING_EDIT_FIELD, GETTING_NEW_EDIT_VALUE

async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Starts the edit process by searching for transactions based on user query.
    This is called when entering the SELECTING_EDIT_FIELD state from the message handler.
    """
    query_text = context.user_data.get('edit_query', '')
    if not query_text:
        await reply_and_log(update, context, "What transaction do you want to edit? Please be more specific.")
        return ConversationHandler.END

    user_id = update.effective_user.id
    async with get_session() as session:
        matches = await db_writer.search_transactions(session, user_id, query_text)
    
    if not matches:
        await reply_and_log(update, context, f"🤔 Bhai, '{query_text}' jaisi koi transaction mili nahi.")
        context.user_data.pop('edit_query', None)
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(
            f"{txn.created_at.strftime('%d-%b')} - {txn.note} (₹{txn.amount})", 
            callback_data=f"edit_select_{txn.id}"
        )] 
        for txn in matches[:5]
    ]
    keyboard.append([InlineKeyboardButton("Cancel", callback_data="edit_cancel")])
    
    await reply_and_log(update, context, "Theek hai bhai, konsi transaction edit karni hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    
    return SELECTING_EDIT_FIELD

async def edit_transaction_direct_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    An entry point to start editing directly from a button click, bypassing the search.
    """
    query = update.callback_query
    await query.answer()

    txn_id = int(query.data.split('_')[-1])
    context.user_data['edit_transaction_id'] = txn_id

    keyboard = [
        [InlineKeyboardButton("Amount", callback_data="edit_field_amount"), InlineKeyboardButton("Note", callback_data="edit_field_note")],
        [InlineKeyboardButton("Category", callback_data="edit_field_category"), InlineKeyboardButton("Cancel", callback_data="edit_cancel")]
    ]
    await edit_and_log(query, context, "Okay, what would you like to change for this transaction?", reply_markup=InlineKeyboardMarkup(keyboard))
    
    return GETTING_NEW_EDIT_VALUE

async def edit_select_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    After user selects a transaction from the search list, this asks which field to edit.
    """
    query = update.callback_query
    await query.answer()

    txn_id = int(query.data.split('_')[-1])
    context.user_data['edit_transaction_id'] = txn_id

    keyboard = [
        [InlineKeyboardButton("Amount", callback_data="edit_field_amount"), InlineKeyboardButton("Note", callback_data="edit_field_note")],
        [InlineKeyboardButton("Category", callback_data="edit_field_category"), InlineKeyboardButton("Cancel", callback_data="edit_cancel")]
    ]
    await edit_and_log(query, context, "Okay, is transaction ka kya badalna hai?", reply_markup=InlineKeyboardMarkup(keyboard))

    return GETTING_NEW_EDIT_VALUE

async def edit_get_field_and_ask_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    After user selects a field, this stores the field and asks for the new value.
    """
    query = update.callback_query
    await query.answer()

    field = query.data.split('_')[-1]
    context.user_data['edit_field'] = field
    
    await edit_and_log(query, context, text=f"Theek hai, naya '{field}' kya hoga?")
    
    return GETTING_NEW_EDIT_VALUE

async def edit_get_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Receives the new text value from the user, performs the update, and ends.
    """
    new_value = update.message.text
    field_to_edit = context.user_data.get('edit_field')
    txn_id = context.user_data.get('edit_transaction_id')
    user_id = update.effective_user.id

    updates = {field_to_edit: new_value}
    
    async with get_session() as session:
        updated_txn = await db_writer.update_transaction(session, user_id, txn_id, updates)
    
    if updated_txn:
        await reply_and_log(update, context, f"✅ Ho gaya! Transaction updated.\n{format_transaction_details(updated_txn)}")
    else:
        await reply_and_log(update, context, "🤯 Kuch gadbad ho gayi, update nahi kar paaya.")
        
    # Clean up context data
    for key in ['edit_query', 'edit_transaction_id', 'edit_field']:
        context.user_data.pop(key, None)
        
    return ConversationHandler.END

async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the edit process and clears context."""
    query = update.callback_query
    if query:
        await query.answer()
        await edit_and_log(query, context, text="Theek hai, edit cancel kar diya.")
    else:
        await reply_and_log(update, context, "Theek hai, edit cancel kar diya.")

    for key in ['edit_query', 'edit_transaction_id', 'edit_field']:
        context.user_data.pop(key, None)
        
    return ConversationHandler.END

# Note: The ConversationHandler definition is usually in main.py, not here.
# This file should only export the handler functions.
