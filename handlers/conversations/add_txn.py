# /handlers/conversations/add_txn.py

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Use absolute imports
from db.database import with_db_session
from db import db_writer
from utils.telegram_helpers import reply_and_log, edit_and_log
# Use relative imports for sibling packages
from .states import (
    CONFIRM_DEFAULT_WALLET, AWAITING_WALLET_NAME, HANDLE_UNKNOWN_WALLET,
    AWAIT_ASSIGNMENT_STRATEGY, AWAIT_SINGLE_WALLET_CHOICE, ASSIGNING_INDIVIDUALLY
)

# =============================================================================
# === FLOW 1: SINGLE TRANSACTION, UNKNOWN WALLET ============================
# =============================================================================

@with_db_session
async def confirm_default_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Handles user's choice on using the default 'Cash' wallet."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    choice = query.data
    transaction_data = context.user_data.get('new_transaction_data')

    if not transaction_data:
        await edit_and_log(query, context, "Sorry, something went wrong. Please try adding the transaction again.")
        return ConversationHandler.END

    if choice == 'default_wallet_yes':
        cash_wallet = await db_writer.get_wallet_by_name(session, user_id, "Cash")
        if not cash_wallet:
            cash_wallet = await db_writer.create_wallet(session, user_id, "Cash", category="Expense")
        
        added_txn = await db_writer.add_transaction(session, user_id, transaction_data, cash_wallet.id)
        await edit_and_log(query, context, f"✅ Done! Transaction for '{added_txn.note}' (₹{added_txn.amount}) added to **{cash_wallet.name}** wallet.", parse_mode="Markdown")
        
        context.user_data.pop('new_transaction_data', None)
        return ConversationHandler.END
    
    else:
        await edit_and_log(query, context, "Okay, please type the name of the wallet you want to use.")
        return AWAITING_WALLET_NAME

@with_db_session
async def receive_wallet_name(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Receives a wallet name from the user and either uses it or prompts to create it."""
    wallet_name = update.message.text
    user_id = update.effective_user.id
    transaction_data = context.user_data.get('new_transaction_data')
    target_wallet = await db_writer.get_wallet_by_name(session, user_id, wallet_name)

    if target_wallet:
        added_txn = await db_writer.add_transaction(session, user_id, transaction_data, target_wallet.id)
        await reply_and_log(update, context, f"✅ Done! Transaction for '{added_txn.note}' (₹{added_txn.amount}) added to **{target_wallet.name}** wallet.", parse_mode="Markdown")
        context.user_data.pop('new_transaction_data', None)
        return ConversationHandler.END
    else:
        context.user_data['unavailable_wallet_name'] = wallet_name
        keyboard = [
            [InlineKeyboardButton(f"Yes, create '{wallet_name}'", callback_data="create_wallet_confirm")],
            [InlineKeyboardButton("Cancel Transaction", callback_data="add_txn_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await reply_and_log(update, context, f"The wallet '{wallet_name}' does not exist. Would you like to create it and add the transaction?", reply_markup=reply_markup)
        return HANDLE_UNKNOWN_WALLET

@with_db_session
async def handle_new_wallet_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Handles the choice to create a new wallet during a transaction or cancel."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    choice = query.data

    if choice == 'create_wallet_confirm':
        wallet_name = context.user_data.get('unavailable_wallet_name')
        transaction_data = context.user_data.get('new_transaction_data')
        new_wallet = await db_writer.create_wallet(session, user_id, wallet_name, category='Expense')
        added_txn = await db_writer.add_transaction(session, user_id, transaction_data, new_wallet.id)
        await edit_and_log(query, context, f"✅ Done! New wallet '{new_wallet.name}' created and transaction for '{added_txn.note}' (₹{added_txn.amount}) has been added.")
    else:
        await edit_and_log(query, context, "Okay, the transaction has been cancelled.")
    
    context.user_data.pop('new_transaction_data', None)
    context.user_data.pop('unavailable_wallet_name', None)
    return ConversationHandler.END

async def add_txn_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the transaction addition process."""
    query = update.callback_query
    await query.answer()
    await edit_and_log(query, context, "Okay, the transaction has been cancelled.")
    context.user_data.pop('new_transaction_data', None)
    context.user_data.pop('unavailable_wallet_name', None)
    return ConversationHandler.END

add_transaction_conv_handler = ConversationHandler(
    entry_points=[],
    states={
        CONFIRM_DEFAULT_WALLET: [CallbackQueryHandler(confirm_default_wallet, pattern='^default_wallet_')],
        AWAITING_WALLET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_wallet_name)],
        HANDLE_UNKNOWN_WALLET: [CallbackQueryHandler(handle_new_wallet_choice, pattern='^(create_wallet_confirm|add_txn_cancel)$')]
    },
    fallbacks=[CallbackQueryHandler(add_txn_cancel, pattern='^add_txn_cancel$')]
)


# =============================================================================
# === FLOW 2: MULTIPLE TRANSACTIONS, WALLET ASSIGNMENT =======================
# =============================================================================

@with_db_session
async def handle_assignment_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Handles the user's choice of 'Same Wallet' or 'Individual'."""
    query = update.callback_query
    await query.answer()
    choice = query.data.split('_')[-1]
    user_id = query.from_user.id

    if choice == "same":
        wallets = await db_writer.get_wallets(session, user_id)
        if not wallets:
            await edit_and_log(query, context, "You have no wallets. Please create one first. Cancelling.")
            return ConversationHandler.END
            
        keyboard = [[InlineKeyboardButton(f"💳 {w.name}", callback_data=f"multi_tx_select_wallet_{w.id}")] for w in wallets]
        keyboard.append([InlineKeyboardButton("« Back", callback_data="multi_tx_strategy_back")])
        await edit_and_log(query, context, "Okay, which wallet should I use for all transactions?", reply_markup=InlineKeyboardMarkup(keyboard))
        return AWAIT_SINGLE_WALLET_CHOICE

    elif choice == "individual":
        context.user_data['multi_tx_index'] = 0
        return await assign_individual_wallet_step(update, context, session)

    else:
        context.user_data.pop('multi_tx_pending', None)
        await edit_and_log(query, context, "Okay, all pending transactions have been cancelled.")
        return ConversationHandler.END

@with_db_session
async def assign_single_wallet_to_all(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Assigns one chosen wallet to all pending transactions and saves them."""
    query = update.callback_query
    await query.answer()
    wallet_id = int(query.data.split('_')[-1])
    user_id = query.from_user.id
    
    pending_txns = context.user_data.pop('multi_tx_pending', [])
    for txn_data in pending_txns:
        # Add the transaction, but DON'T recalculate yet.
        await db_writer.add_transaction_and_flag(session, user_id, txn_data, wallet_id)
    
    # --- FIX ---
    # Recalculate the balance only ONCE after all transactions are added.
    asyncio.create_task(db_writer.recalculate_wallet_balance(wallet_id))
    
    wallet = await db_writer.get_wallet_by_id(session, wallet_id)
    await edit_and_log(query, context, f"✅ All {len(pending_txns)} transactions have been added to the '{wallet.name}' wallet.")
    return ConversationHandler.END

@with_db_session
async def assign_individual_wallet_step(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Assigns wallets one-by-one, with a back button."""
    query = update.callback_query
    if query: await query.answer()

    pending_txns = context.user_data.get('multi_tx_pending', [])
    index = context.user_data.get('multi_tx_index', 0)
    user_id = update.effective_user.id

    if query and query.data.startswith("multi_tx_assign_"):
        wallet_id = int(query.data.split('_')[-1])
        pending_txns[index - 1]['wallet_id'] = wallet_id

    if index >= len(pending_txns):
        wallets_to_recalculate = set() # Keep track of wallets to update
        for txn_data in pending_txns:
            wallet_id = txn_data['wallet_id']
            await db_writer.add_transaction_and_flag(session, user_id, txn_data, wallet_id)
            wallets_to_recalculate.add(wallet_id)
        
        # --- FIX ---
        # Recalculate each affected wallet's balance only ONCE.
        for wallet_id in wallets_to_recalculate:
            asyncio.create_task(db_writer.recalculate_wallet_balance(wallet_id))

        context.user_data.pop('multi_tx_pending', None)
        context.user_data.pop('multi_tx_index', None)
        await edit_and_log(query, context, "✅ All transactions have been saved successfully!")
        return ConversationHandler.END

    current_txn = pending_txns[index]
    all_wallets = await db_writer.get_wallets(session, user_id)
    
    wallets_to_show = [w for w in all_wallets if w.category == 'Expense']

    keyboard = [[InlineKeyboardButton(f"💳 {w.name}", callback_data=f"multi_tx_assign_{w.id}")] for w in wallets_to_show]
    keyboard.append([InlineKeyboardButton("« Back to Strategy", callback_data="multi_tx_strategy_back")])
    
    prompt = f"({index + 1}/{len(pending_txns)}) For '{current_txn['note']}' (₹{current_txn['amount']}), which wallet?"
    
    context.user_data['multi_tx_index'] = index + 1
    
    message_to_edit = query.message if query else update.message
    await message_to_edit.edit_text(prompt, reply_markup=InlineKeyboardMarkup(keyboard))

    return ASSIGNING_INDIVIDUALLY

async def back_to_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns the user from individual/single assignment back to the strategy selection screen."""
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Assign Same Wallet to All", callback_data="multi_tx_strategy_same")],
        [InlineKeyboardButton("Assign Wallets Individually", callback_data="multi_tx_strategy_individual")],
        [InlineKeyboardButton("Cancel", callback_data="multi_tx_strategy_cancel")]
    ]
    await edit_and_log(query, context, "How would you like to assign wallets?", reply_markup=InlineKeyboardMarkup(keyboard))
    return AWAIT_ASSIGNMENT_STRATEGY

multi_tx_wallet_conv_handler = ConversationHandler(
    entry_points=[],
    states={
        AWAIT_ASSIGNMENT_STRATEGY: [CallbackQueryHandler(handle_assignment_strategy, pattern='^multi_tx_strategy_')],
        AWAIT_SINGLE_WALLET_CHOICE: [
            CallbackQueryHandler(assign_single_wallet_to_all, pattern='^multi_tx_select_wallet_'),
            CallbackQueryHandler(back_to_strategy, pattern='^multi_tx_strategy_back$')
        ],
        ASSIGNING_INDIVIDUALLY: [
            CallbackQueryHandler(assign_individual_wallet_step, pattern='^multi_tx_assign_'),
            CallbackQueryHandler(back_to_strategy, pattern='^multi_tx_strategy_back$')
        ],
    },
    fallbacks=[CallbackQueryHandler(handle_assignment_strategy, pattern='^multi_tx_strategy_cancel$')]
)