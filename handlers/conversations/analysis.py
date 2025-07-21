# /handlers/conversations/analysis.py

import asyncio
from telegram import Update
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CommandHandler
)

from db.database import with_db_session
from db import db_writer
from utils.telegram_helpers import reply_and_log, edit_and_log
from utils.plotting import create_period_comparison_chart
from .states import AWAIT_FIRST_PERIOD, AWAIT_SECOND_PERIOD


async def start_period_comparison(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for the period comparison conversation."""
    query = update.callback_query
    await query.answer()

    # Data is expected in the format: 'start_comparison_{period_type}_{wallet_category}'
    # e.g., 'start_comparison_monthly_Expense'
    parts = query.data.split('_')
    period_type = parts[2]
    wallet_category = parts[3]
    
    context.user_data['comparison_info'] = {
        "period_type": period_type,
        "wallet_category": wallet_category
    }
    
    if period_type == 'monthly':
        prompt = "Please enter the first month to compare (e.g., `2025-07`):"
    elif period_type == 'quarterly':
        prompt = "Please enter the first quarter (e.g., `2025-Q2`):"
    else:  # yearly
        prompt = "Please enter the first year (e.g., `2025`):"
        
    await edit_and_log(query, context, text=prompt, parse_mode="Markdown")
    return AWAIT_FIRST_PERIOD


@with_db_session
async def get_first_period(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Gets the first period from the user and asks for the second."""
    context.user_data['comparison_info']['period1'] = update.message.text
    period_type = context.user_data['comparison_info']['period_type']
    
    if period_type == 'monthly':
        prompt = "Got it. Now enter the second month to compare (e.g., `2025-08`):"
    elif period_type == 'quarterly':
        prompt = "And the second quarter (e.g., `2025-Q3`):"
    else:  # yearly
        prompt = "And the second year (e.g., `2024`):"

    await reply_and_log(update, context, text=prompt, parse_mode="Markdown")
    return AWAIT_SECOND_PERIOD


@with_db_session
async def get_second_period_and_compare(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Gets the second period, fetches data, generates the chart, and ends."""
    info = context.user_data.get('comparison_info', {})
    info['period2'] = update.message.text
    user_id = update.effective_user.id
    
    await reply_and_log(update, context, "📊 Generating comparison chart, please wait...")

    # Fetch the data from the database
    comparison_data = await db_writer.get_period_comparison_data(
        session, user_id, info['wallet_category'], info['period_type'], info['period1'], info['period2']
    )
    
    title = f"Comparison: {info['period1']} vs. {info['period2']}"

    # Generate the chart using the plotting utility
    image_buffer = await asyncio.to_thread(
        create_period_comparison_chart,
        comparison_data['period1'],
        comparison_data['period2'],
        info['period1'],
        info['period2'],
        title
    )
    
    await context.bot.send_photo(chat_id=user_id, photo=image_buffer, caption=title)
    
    context.user_data.pop('comparison_info', None)
    return ConversationHandler.END


async def comparison_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the comparison conversation and clears user data."""
    context.user_data.pop('comparison_info', None)
    await reply_and_log(update, context, "Comparison cancelled.")
    return ConversationHandler.END


# Define the ConversationHandler for the analysis flow
analysis_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_period_comparison, pattern='^start_comparison_')
    ],
    states={
        AWAIT_FIRST_PERIOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_first_period)],
        AWAIT_SECOND_PERIOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_second_period_and_compare)],
    },
    fallbacks=[
        CommandHandler('cancel', comparison_cancel)
    ],
)