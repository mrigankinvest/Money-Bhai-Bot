# /handlers/callbacks.py

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from db.database import with_db_session
from db import db_writer
from utils.telegram_helpers import (
    edit_and_log, 
    send_dataframe_as_image,
    display_pending_transactions_menu,
    send_interactive_txn_list
)
from utils.plotting import (
    create_balance_overview_chart, 
    create_trend_analysis_chart, 
    create_expense_pie_chart
)
from utils.formatting import transactions_to_dataframe, format_transaction_details
from .conversations.states import MANAGING_PENDING_ITEM

logger = logging.getLogger(__name__)

# This is the main router for almost all button clicks that are NOT part of an active conversation.
@with_db_session
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    data = query.data

    # ===================================================================
    # Main Dashboard & Menu Navigation
    # ===================================================================

    if data.startswith("show_wallets_"):
        wallet_category = data.split('_')[2]
        all_wallets = await db_writer.get_wallets(session, user_id)
        wallets_to_show = [w for w in all_wallets if w.category == wallet_category]

        keyboard = []
        if not wallets_to_show:
            await edit_and_log(query, context, text=f"You don't have any '{wallet_category}' wallets yet.")
            return

        for wallet in wallets_to_show:
            button_text = f"💳 {wallet.name}: ₹{wallet.balance:.2f}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"wallet_txn_report_menu_{wallet.id}")])
        
        keyboard.extend([
            [InlineKeyboardButton("📊 Deeper Analysis", callback_data=f"deeper_analysis_{wallet_category}")],
            [InlineKeyboardButton("➕ Create New Wallet", callback_data=f"create_wallet_start_{wallet_category}")], # Starts conversation
            [InlineKeyboardButton("« Back to Dashboard", callback_data="back_to_dashboard")]
        ])
        await edit_and_log(query, context, f"Here are your {wallet_category} wallets:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "back_to_dashboard":
        from utils.telegram_helpers import send_wallet_overview # Local import to avoid circular dependency
        await send_wallet_overview(update, context, session)

    # ===================================================================
    # Analysis Menus & Immediate Chart Generation
    # ===================================================================

    elif data.startswith("deeper_analysis_"):
        wallet_category = data.split('_')[-1]
        keyboard = [
            [InlineKeyboardButton("Balance Overview", callback_data=f"balance_overview_{wallet_category}")],
            [InlineKeyboardButton("Trend Analysis", callback_data=f"trend_analysis_menu_{wallet_category}")],
            [InlineKeyboardButton("Period Comparison", callback_data=f"start_comparison_monthly_{wallet_category}")], # Starts conversation
            [InlineKeyboardButton("« Back to Wallets", callback_data=f"show_wallets_{wallet_category}")]
        ]
        await edit_and_log(query, context, "Please choose an analysis type:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("balance_overview_"):
        wallet_category = data.split('_')[-1]
        await edit_and_log(query, context, f"📊 Generating balance overview for {wallet_category} wallets...")
        wallets = sorted(
            [w for w in await db_writer.get_wallets(session, user_id) if w.category == wallet_category],
            key=lambda x: x.balance, reverse=True
        )
        if not wallets:
            await query.message.reply_text(f"No wallets to analyze in the '{wallet_category}' category.")
            return
        title = f"'{wallet_category}' Wallet Balance Overview"
        image_buffer = await asyncio.to_thread(create_balance_overview_chart, wallets, title)
        await context.bot.send_photo(chat_id=chat_id, photo=image_buffer)

    elif data.startswith("trend_analysis_menu_"):
        wallet_category = data.split('_')[-1]
        keyboard = [
            [InlineKeyboardButton("Monthly", callback_data=f"run_trend_monthly_{wallet_category}"),
             InlineKeyboardButton("Quarterly", callback_data=f"run_trend_quarterly_{wallet_category}"),
             InlineKeyboardButton("Yearly", callback_data=f"run_trend_yearly_{wallet_category}")],
            [InlineKeyboardButton("« Back", callback_data=f"deeper_analysis_{wallet_category}")]
        ]
        await edit_and_log(query, context, "Please select the time period for the trend analysis:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("run_trend_"):
        parts = data.split('_')
        period, wallet_category = parts[2], parts[3]
        await edit_and_log(query, context, f"📈 Generating {period} trend analysis, please wait...")
        trend_df = await db_writer.get_trend_data(session, user_id, period, wallet_category)
        if trend_df.empty:
            await query.message.reply_text(f"No data found for '{wallet_category}' to generate a trend analysis.")
            return
        title = f"{wallet_category} - {period.capitalize()} Trend Analysis"
        image_buffer = await asyncio.to_thread(create_trend_analysis_chart, trend_df, title)
        await context.bot.send_photo(chat_id=chat_id, photo=image_buffer, caption=f"Here is your {period} trend analysis.")

    # ===================================================================
    # Report Generation (DF Image & Pie Chart)
    # ===================================================================

    # This handler now correctly passes the `reply_markup`
    if data.startswith("wallet_txn_report_menu_"):
        wallet_id = data.split('_')[-1]
        keyboard = [
            [InlineKeyboardButton("Last 7 Days", callback_data=f"txn_report_{wallet_id}_weekly"),
             InlineKeyboardButton("This Month", callback_data=f"txn_report_{wallet_id}_monthly")],
            [InlineKeyboardButton("This Year", callback_data=f"txn_report_{wallet_id}_yearly"),
             InlineKeyboardButton("All Time", callback_data=f"txn_report_{wallet_id}_all")],
            [InlineKeyboardButton("📊 Expense Pie Chart", callback_data=f"wallet_pie_chart_{wallet_id}")],
             [InlineKeyboardButton("« Back", callback_data=f"show_wallets_Expense")]
        ]
        await edit_and_log(query, context, text="Please select a time period or report type:", reply_markup=InlineKeyboardMarkup(keyboard))

    # This handler starts the interactive list view
    elif data.startswith("txn_report_"):
        parts = data.split('_')
        wallet_id = int(parts[2])
        period = parts[3]
        
        await edit_and_log(query, context, "🔍 Fetching transactions...")
        transactions = await db_writer.get_transactions_for_wallet_period(session, user_id, wallet_id, period)
        wallet = await db_writer.get_wallet_by_id(session, wallet_id)
        if not wallet:
            await edit_and_log(query, context, "Error: Could not find the specified wallet.")
            return

        header = f"Transactions for '{wallet.name}' ({period.capitalize()})"
        await send_interactive_txn_list(
            update=update,
            context=context,
            transactions=transactions,
            header_text=header,
            wallet_id=wallet_id,
            wallet_category=wallet.category,
            period=period,
            page=1
        )

    # --- THIS SECTION CONTAINS THE FIX ---
    # The indices used to parse the callback_data are now correct.

    elif data.startswith("txn_page_"):
        parts = data.split('_')
        # "txn_page_{page}_{wallet_id}_{period}"
        #   0    1      2        3         4
        page = int(parts[2])
        wallet_id = int(parts[3])
        period = parts[4]
        
        transactions = await db_writer.get_transactions_for_wallet_period(session, user_id, wallet_id, period)
        wallet = await db_writer.get_wallet_by_id(session, wallet_id)
        if not wallet: return
        
        header = f"Transactions for '{wallet.name}' ({period.capitalize()})"
        await send_interactive_txn_list(
            update=update, context=context, transactions=transactions,
            header_text=header, wallet_id=wallet_id, wallet_category=wallet.category, period=period, page=page
        )

    elif data.startswith("view_txn_"):
        parts = data.split('_')
        # "view_txn_{txn_id}_{page}_{wallet_id}_{period}"
        #   0    1      2       3        4         5
        txn_id = int(parts[2])
        page = int(parts[3])
        wallet_id = int(parts[4])
        period = parts[5]

        txn = await db_writer.get_transaction_by_id(session, user_id, txn_id)
        if not txn:
            await edit_and_log(query, context, "Sorry, this transaction could not be found.")
            return

        details_text = format_transaction_details(txn)
        back_callback_data = f"back_to_txn_list_{page}_{wallet_id}_{period}"
        keyboard = [
            [
                InlineKeyboardButton("✏️ Edit", callback_data=f"edit_action_txn_{txn.id}"),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_action_txn_{txn.id}")
            ],
            [InlineKeyboardButton("« Back to List", callback_data=back_callback_data)]
        ]
        await edit_and_log(query, context, details_text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data.startswith("back_to_txn_list_"):
        parts = data.split('_')
        # "back_to_txn_list_{page}_{wallet_id}_{period}"
        #   0    1    2    3     4        5         6
        page = int(parts[4])
        wallet_id = int(parts[5])
        period = parts[6]
        
        transactions = await db_writer.get_transactions_for_wallet_period(session, user_id, wallet_id, period)
        wallet = await db_writer.get_wallet_by_id(session, wallet_id)
        if not wallet: return

        header = f"Transactions for '{wallet.name}' ({period.capitalize()})"
        # FIX 3: Removed session=session from the call
        await send_interactive_txn_list(
            update=update, context=context, transactions=transactions,
            header_text=header, wallet_id=wallet_id, wallet_category=wallet.category, period=period, page=page
        )

    elif data.startswith("wallet_pie_chart_"):
        wallet_id = int(data.split('_')[-1])
        await edit_and_log(query, context, "📊 Generating expense breakdown...")
        transactions = await db_writer.get_transactions_for_wallet_period(session, user_id, wallet_id, "all")
        if not transactions:
            await query.message.reply_text("This wallet has no transactions to analyze.")
            return
        wallet_name = transactions[0].wallet.name
        df = transactions_to_dataframe(transactions)
        expense_df = df[df['Type'] == 'Expense']
        if expense_df.empty:
            await query.message.reply_text(f"No expense transactions found in '{wallet_name}' to chart.")
            return
        title = f"Expense Breakdown for '{wallet_name}'"
        image_buffer = await asyncio.to_thread(create_expense_pie_chart, expense_df, title)
        await context.bot.send_photo(chat_id=chat_id, photo=image_buffer)

    # ===================================================================
    # Post-Add Transaction Confirmation Flow
    # ===================================================================

    elif data == 'confirm_all_pending_txns':
        context.user_data.pop('pending_txn_ids', None)
        await edit_and_log(query, context, "✅ Got it! Action(s) confirmed.")
        return ConversationHandler.END

    elif data == 'cancel_all_pending_txns':
        txn_ids_to_delete = context.user_data.pop('pending_txn_ids', [])
        deleted_count = 0
        for txn_id in txn_ids_to_delete:
            txn_to_delete = await db_writer.get_transaction_by_id(session, user_id, txn_id)
            if txn_to_delete:
                await db_writer.delete_transaction_and_update_wallet(session, txn_to_delete)
                deleted_count += 1
        await edit_and_log(query, context, f"👍 Okay, all {deleted_count} pending transaction(s) have been cancelled.")
        return ConversationHandler.END

    elif data.startswith("select_pending_txn_"):
        txn_id = int(data.split('_')[-1])
        context.user_data['selected_pending_txn_id'] = txn_id
        keyboard = [
            [InlineKeyboardButton("✏️ Edit", callback_data=f"edit_action_txn_{txn_id}"), # Starts conversation
             InlineKeyboardButton("🗑️ Delete", callback_data="delete_pending_txn")],
            [InlineKeyboardButton("« Back to List", callback_data="show_pending_list")]
        ]
        await edit_and_log(query, context, "What would you like to do with this item?", reply_markup=InlineKeyboardMarkup(keyboard))
        return MANAGING_PENDING_ITEM

    # ===================================================================
    # Universal Destructive Action Confirmations
    # ===================================================================
    
    elif data == 'confirm_delete_all_txns':
        # This logic needs to be fully implemented in db_writer
        # deleted_count = await db_writer.delete_all_transactions(session, user_id)
        # await edit_and_log(query, context, text=f"✅ All {deleted_count} transactions deleted.")
        await edit_and_log(query, context, text="Functionality to be implemented.")
        
    elif data == 'confirm_delete_all_wallets':
        # This logic needs to be fully implemented in db_writer
        # await db_writer.delete_all_user_data(session, user_id)
        # await edit_and_log(query, context, text="✅ Your entire profile has been deleted.")
        await edit_and_log(query, context, text="Functionality to be implemented.")

    elif data == 'cancel_delete':
        await edit_and_log(query, context, text="👍 Deletion cancelled. Your data is safe.")