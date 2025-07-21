# /utils/telegram_helpers.py

import os
import logging
import asyncio
import pandas as pd
import dataframe_image as dfi
from collections import deque
from telegram import Update, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import math

from config import DATA_DIR, CATEGORY_EMOJIS
from db import db_writer

logger = logging.getLogger(__name__)

def add_to_history(context: ContextTypes.DEFAULT_TYPE, role: str, content: str):
    if 'message_history' not in context.user_data:
        context.user_data['message_history'] = deque(maxlen=30)
    context.user_data['message_history'].append({"role": role, "content": content})

async def reply_and_log(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs):
    logger.info(f"Replying to {update.effective_user.id}: '{text}'")
    add_to_history(context, "assistant", text)
    await update.message.reply_text(text, **kwargs)

async def edit_and_log(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs):
    logger.info(f"Editing message for {query.from_user.id}: '{text}'")
    add_to_history(context, "assistant", text)
    await query.edit_message_text(text, **kwargs)

async def send_and_log(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, **kwargs):
    logger.info(f"Sending to {chat_id}: '{text}'")
    add_to_history(context, "assistant", text)
    await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)

async def send_dataframe_as_image(df: pd.DataFrame, chat_id: int, context: ContextTypes.DEFAULT_TYPE, caption="Here are your transactions. 📄"):
    if df.empty:
        await send_and_log(context, chat_id, text="😕 No matching transactions found.")
        return

    styled_df = df.style.background_gradient(cmap='BuGn').set_properties(**{'text-align': 'left'})
    styled_df.set_table_styles([dict(selector="th", props=[("text-align", "left")])])
    image_path = DATA_DIR / f"export_{chat_id}.png"
    
    await asyncio.to_thread(dfi.export, styled_df, str(image_path))
    
    logger.info(f"Sending dataframe image to {chat_id}")
    with open(image_path, "rb") as photo:
        await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
    os.remove(image_path)
    
async def send_wallet_overview(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Sends a high-level financial summary dashboard as a message."""
    user_id = update.effective_user.id
    # get_financial_summary needs to be implemented in your db_writer.py
    summary = await db_writer.get_financial_summary(session, user_id)

    expense_text = f"💳 Expenses: ₹{summary.get('total_expense', 0):.2f}"
    income_text = f"💰 Income: ₹{summary.get('total_income', 0):.2f}"
    investment_text = f"📈 Investments: ₹{summary.get('net_investment', 0):.2f}"
    goal_text = f"🎯 Goal: {summary.get('goal_status', 'Not Set')}"

    keyboard = [
        [
            InlineKeyboardButton(expense_text, callback_data="show_wallets_Expense"),
            InlineKeyboardButton(income_text, callback_data="show_wallets_Expense")
        ],
        [
            InlineKeyboardButton(investment_text, callback_data="show_wallets_Investment"),
            InlineKeyboardButton(goal_text, callback_data="show_goal_detail")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "Here is your financial dashboard:"
    if update.callback_query:
        await edit_and_log(update.callback_query, context, message_text, reply_markup=reply_markup)
    else:
        await reply_and_log(update, context, message_text, reply_markup=reply_markup)


async def display_pending_transactions_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, session, intro_text: str):
    from handlers.conversations.states import AWAIT_ACTION_CONFIRMATION
    
    user_id = update.effective_user.id
    pending_txn_ids = context.user_data.get('pending_txn_ids', [])

    if not pending_txn_ids:
        await edit_and_log(update.callback_query, context, "No more pending transactions. All confirmed!")
        return ConversationHandler.END

    keyboard = []
    for txn_id in pending_txn_ids:
        txn = await db_writer.get_transaction_by_id(session, user_id, txn_id)
        if txn:
            emoji = CATEGORY_EMOJIS.get(txn.category.lower(), "✅")
            button_text = f"- {emoji} {txn.category}: {txn.note} (₹{txn.amount}) from {txn.wallet.name}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_pending_txn_{txn_id}")])

    keyboard.append([
        InlineKeyboardButton("✅ Confirm All", callback_data="confirm_all_pending_txns"),
        InlineKeyboardButton("❌ Cancel All", callback_data="cancel_all_pending_txns")
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await edit_and_log(update.callback_query, context, intro_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await reply_and_log(update, context, intro_text, reply_markup=reply_markup, parse_mode="Markdown")

    return AWAIT_ACTION_CONFIRMATION

async def send_interactive_txn_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    transactions: list,
    header_text: str,
    wallet_id: int,
    wallet_category: str,
    period: str,
    page: int = 1
):
    """
    Sends a paginated, interactive list of transactions as buttons.
    It can now either EDIT an existing message or SEND a new one.
    """
    TXNS_PER_PAGE = 7
    if not transactions:
        # If called from a button, edit the message. Otherwise, send a new one.
        if update.callback_query:
            await edit_and_log(update.callback_query, context, "No transactions found for this period.")
        else:
            await reply_and_log(update, context, "No transactions found for this period.")
        return

    # --- Pagination and Keyboard building logic remains the same ---
    total_txns = len(transactions)
    total_pages = math.ceil(total_txns / TXNS_PER_PAGE)
    start_index = (page - 1) * TXNS_PER_PAGE
    end_index = start_index + TXNS_PER_PAGE
    txns_to_display = transactions[start_index:end_index]

    keyboard = []
    for txn in txns_to_display:
        emoji = "🟢" if txn.type in ('income', 'deposit') else "🔴"
        button_text = f"{emoji} {txn.created_at.strftime('%d %b')}: {txn.note or 'N/A'} (₹{txn.amount:,.0f})"
        callback_data = f"view_txn_{txn.id}_{page}_{wallet_id}_{period}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    pagination_row = []
    if page > 1:
        pagination_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"txn_page_{page-1}_{wallet_id}_{period}"))
    if total_pages > 1:
        pagination_row.append(InlineKeyboardButton(f"Page {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        pagination_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"txn_page_{page+1}_{wallet_id}_{period}"))
    if pagination_row:
        keyboard.append(pagination_row)

    keyboard.append([InlineKeyboardButton(f"« Back to {wallet_category} Wallets", callback_data=f"show_wallets_{wallet_category}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # --- FIX: Check if we should edit or reply ---
    if update.callback_query:
        await edit_and_log(update.callback_query, context, header_text, reply_markup=reply_markup)
    else:
        await reply_and_log(update, context, header_text, reply_markup=reply_markup)