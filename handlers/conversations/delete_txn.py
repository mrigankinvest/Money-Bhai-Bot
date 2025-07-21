# /handlers/conversations/delete_txn.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from db.database import with_db_session
from db import db_writer
from utils.telegram_helpers import reply_and_log, edit_and_log

@with_db_session
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> int:
    """
    Starts the deletion process by searching for transactions based on user query
    and displaying them as buttons.
    This function is intended to be called when the conversation enters the 
    SELECTING_DELETE_CANDIDATE state.
    """
    query_text = context.user_data.get('delete_query', '')
    if not query_text:
        await reply_and_log(update, context, "What transaction do you want to delete? Please be more specific.")
        return ConversationHandler.END

    user_id = update.effective_user.id
    
    # Use your database search function to find potential matches
    # This assumes db_writer.search_transactions exists and is effective
    matches = await db_writer.search_transactions(session, user_id, query_text)
    
    if not matches:
        await reply_and_log(update, context, f"🤔 Bhai, '{query_text}' jaisi koi transaction mili nahi.")
        context.user_data.pop('delete_query', None)
        return ConversationHandler.END

    # Create a keyboard with the top 5 matches
    keyboard = [
        [InlineKeyboardButton(
            f"{txn.created_at.strftime('%d-%b')} - {txn.note} (₹{txn.amount})", 
            callback_data=f"delete_confirm_{txn.id}"
        )] 
        for txn in matches[:5]
    ]
    keyboard.append([InlineKeyboardButton("Cancel", callback_data="delete_cancel")])
    
    await reply_and_log(update, context, "Theek hai bhai, inmein se konsi transaction delete karni hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # The conversation remains in this state, waiting for a button click
    return SELECTING_DELETE_CANDIDATE


@with_db_session
async def delete_perform_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> int:
    """
    Performs the actual deletion after the user selects a transaction from the list.
    """
    query = update.callback_query
    await query.answer()
    
    txn_id_str = query.data.split('_')[-1]
    if not txn_id_str.isdigit():
        await edit_and_log(query, context, "Invalid selection. Please try again.")
        return SELECTING_DELETE_CANDIDATE

    txn_id = int(txn_id_str)
    user_id = query.from_user.id

    txn_to_delete = await db_writer.get_transaction_by_id(session, user_id, txn_id)
    if not txn_to_delete:
        await edit_and_log(query, context, "🤯 Transaction mil nahi rahi, shayad pehle se delete ho gayi.")
        context.user_data.pop('delete_query', None)
        return ConversationHandler.END

    # Use the safe delete function that also updates the wallet balance
    success = await db_writer.delete_transaction_and_update_wallet(session, txn_to_delete)
    
    if success:
        # Get the updated wallet to show the new balance
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