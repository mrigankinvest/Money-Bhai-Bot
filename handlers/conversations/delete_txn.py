# /handlers/conversations/delete_txn.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

# --- Corrected Imports ---
from db.database import get_session # Use the new session manager
from db import db_writer
from utils.telegram_helpers import reply_and_log, edit_and_log

async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Starts the deletion process by searching for transactions based on user query
    and displaying them as buttons.
    """
    query_text = context.user_data.get('delete_query', '')
    if not query_text:
        await reply_and_log(update, context, "What transaction do you want to delete? Please be more specific.")
        return ConversationHandler.END

    user_id = update.effective_user.id
    
    async with get_session() as session:
        matches = await db_writer.search_transactions(session, user_id, query_text)
    
    if not matches:
        await reply_and_log(update, context, f"🤔 Bhai, '{query_text}' jaisi koi transaction mili nahi.")
        context.user_data.pop('delete_query', None)
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(
            f"{txn.created_at.strftime('%d-%b')} - {txn.note} (₹{txn.amount})", 
            callback_data=f"delete_confirm_{txn.id}"
        )] 
        for txn in matches[:5]
    ]
    keyboard.append([InlineKeyboardButton("Cancel", callback_data="delete_cancel")])
    
    await reply_and_log(update, context, "Theek hai bhai, inmein se konsi transaction delete karni hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # This state is defined in your states.py file
    from .states import SELECTING_DELETE_CANDIDATE
    return SELECTING_DELETE_CANDIDATE


async def delete_perform_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Performs the actual deletion after the user selects a transaction from the list.
    """
    query = update.callback_query
    await query.answer()
    
    txn_id_str = query.data.split('_')[-1]
    if not txn_id_str.isdigit():
        await edit_and_log(query, context, "Invalid selection. Please try again.")
        from .states import SELECTING_DELETE_CANDIDATE
        return SELECTING_DELETE_CANDIDATE

    txn_id = int(txn_id_str)
    user_id = query.from_user.id

    async with get_session() as session:
        txn_to_delete = await db_writer.get_transaction_by_id(session, user_id, txn_id)
        if not txn_to_delete:
            await edit_and_log(query, context, "🤯 Transaction mil nahi rahi, shayad pehle se delete ho gayi.")
            context.user_data.pop('delete_query', None)
            return ConversationHandler.END

        success = await db_writer.delete_transaction_and_update_wallet(session, txn_to_delete)
        
        if success:
            updated_wallet = await db_writer.get_wallet_by_id(session, txn_to_delete.wallet_id)
            confirmation_message = (
                f"🗑️ Transaction for '{txn_to_delete.note}' has been deleted.\n\n"
                f"Wallet '{updated_wallet.name}' balance is now **₹{updated_wallet.balance:.2f}**."
            )
            await edit_and_log(query, context, confirmation_message, parse_mode="Markdown")
        else:
            await edit_and_log(query, context, "🤯 Kuch gadbad ho gayi, delete nahi kar paaya.")

    context.user_data.pop('delete_query', None)
    return ConversationHandler.END


async def delete_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the deletion process and clears context."""
    query = update.callback_query
    await query.answer()
    
    await edit_and_log(query, context, text="👍 Deletion cancelled.")
    
    context.user_data.pop('delete_query', None)
    return ConversationHandler.END
