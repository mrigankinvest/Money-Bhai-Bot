import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

# --- Corrected Imports ---
from db.database import get_session # Use the new session manager
from db import db_writer
from utils.telegram_helpers import add_to_history, reply_and_log, send_wallet_overview, display_pending_transactions_menu, send_interactive_txn_list
from utils.formatting import format_transaction_details
from llm_handler import parse_message
from config import CATEGORY_EMOJIS

# Import all possible states that this handler can START
from .conversations.states import (
    AWAIT_ASSIGNMENT_STRATEGY,
    CONFIRM_DEFAULT_WALLET,
    AWAITING_INVESTMENT_TYPE,
    AWAITING_BALANCE_UPDATE_CATEGORY,
    SELECTING_EDIT_FIELD,
    SELECTING_DELETE_CANDIDATE,
    SELECT_WALLET_TO_EDIT,
    CONFIRM_WALLET_DELETION
)

logger = logging.getLogger(__name__)

# ===================================================================
# Private Helper Functions for each action (Unchanged)
# ===================================================================

async def _handle_add_transaction(update, context, session, data):
    """Handles a single 'add_transaction' action."""
    user_id = update.effective_user.id
    wallet_name = data.get("wallet")

    if not wallet_name:
        # Wallet not specified, start conversation to ask for it.
        context.user_data['new_transaction_data'] = data
        keyboard = [[
            InlineKeyboardButton("✅ Yes, use Cash", callback_data="default_wallet_yes"),
            InlineKeyboardButton("❌ No, let me choose", callback_data="default_wallet_no")
        ]]
        await reply_and_log(update, context, "This will be recorded from your 'Cash' wallet. Is that okay?", reply_markup=InlineKeyboardMarkup(keyboard))
        return CONFIRM_DEFAULT_WALLET

    # Wallet is specified, perform immediate action
    target_wallet = await db_writer.get_wallet_by_name(session, user_id, wallet_name)
    if not target_wallet:
        return f"Skipping transaction: Can't find wallet '{wallet_name}'."

    added_txn = await db_writer.add_transaction_and_flag(session, user_id, data, target_wallet.id)
    context.user_data['last_transaction_id'] = added_txn.id
    asyncio.create_task(db_writer.recalculate_wallet_balance(target_wallet.id))
    
    return {"type": "add_transaction", "txn": added_txn}

async def _handle_query_last(update, context, session, data):
    """
    Handles "show last transaction" by fetching it directly from the database.
    """
    txn = await db_writer.get_last_transaction(session, update.effective_user.id)
    
    if not txn:
        return "Pehle koi transaction add karo, bhai."
    
    context.user_data['last_transaction_id'] = txn.id
    
    await reply_and_log(update, context, format_transaction_details(txn))
    return None

async def _handle_contextual_edit(update, context, session, data):
    last_txn_id = context.user_data.get('last_transaction_id')
    if not last_txn_id:
        return "Pehle koi transaction add karo jise edit karna hai."
    
    updates = data.get("updates", {})
    updated_txn = await db_writer.update_transaction(session, update.effective_user.id, last_txn_id, updates)
    
    if updated_txn:
        context.user_data.pop('last_transaction_id', None)
        return f"✅ Theek hai, pichli transaction update kar di hai:\n{format_transaction_details(updated_txn)}"
    else:
        return "🤯 Kuch gadbad ho gayi, update nahi kar paaya."

async def _handle_create_wallet(update, context, session, data):
    """IMMEDIATE: Handles wallet creation."""
    user_id = update.effective_user.id
    wallet_name = data.get("name") or data.get("wallet_name")
    if not wallet_name: return None

    new_wallet = await db_writer.create_wallet(session, user_id, wallet_name, data.get("category", "Expense"), data.get("initial_balance", 0.0))
    return {"type": "create_wallet", "wallet": new_wallet}

async def _handle_transfer(update, context, session, data):
    """IMMEDIATE: Handles a wallet-to-wallet transfer."""
    user_id = update.effective_user.id
    from_wallet_name = data.get("from_wallet")
    to_wallet_name = data.get("to_wallet")
    amount = data.get("amount")

    if not all([from_wallet_name, to_wallet_name, amount]):
        return "Transfer failed: Please provide from wallet, to wallet, and amount."
    
    from_wallet = await db_writer.get_wallet_by_name(session, user_id, from_wallet_name)
    to_wallet = await db_writer.get_wallet_by_name(session, user_id, to_wallet_name)

    if not from_wallet or not to_wallet:
        return f"Transfer failed: Couldn't find one of the wallets ('{from_wallet_name}' or '{to_wallet_name}')."
    
    await db_writer.record_transfer(session, user_id, from_wallet.id, to_wallet.id, amount, data.get("note"))
    return f"✅ Transfer Successful: ₹{amount:.2f} from {from_wallet.name} to {to_wallet.name}"

async def _handle_view_wallets(update, context, session, data):
    """IMMEDIATE: Shows the wallet overview dashboard."""
    await send_wallet_overview(update, context, session)
    return None

async def _handle_clarify_chat(update, context, session, data):
    """IMMEDIATE: Handles a casual or clarifying chat response."""
    await reply_and_log(update, context, data.get("reply", "Sab badhiya, aap batao?"))
    return None

async def _handle_edit_action(update, context, session, data):
    """STARTS CONVERSATION: Prepares context for the edit flow."""
    context.user_data['edit_query'] = data.get('query', '')
    return SELECTING_EDIT_FIELD

async def _handle_delete_action(update, context, session, data):
    """STARTS CONVERSATION: Prepares context for the delete flow."""
    context.user_data['delete_query'] = data.get('query', '')
    return SELECTING_DELETE_CANDIDATE

async def _handle_edit_wallet_action(update, context, session, data):
    """STARTS CONVERSATION: Prepares context for the edit wallet flow."""
    context.user_data['edit_wallet_name'] = data.get("wallet_name")
    return SELECT_WALLET_TO_EDIT

async def _handle_delete_wallet_action(update, context, session, data):
    """STARTS CONVERSATION: Prepares context for the delete wallet flow."""
    context.user_data['delete_wallet_name'] = data.get("wallet_name")
    return CONFIRM_WALLET_DELETION

async def _handle_log_investment(update, context, session, data):
    """STARTS CONVERSATION: Asks for investment type."""
    context.user_data['investment_data'] = data
    amount = data.get('amount', 0)
    activity = "deposit" if amount > 0 else "withdrawal"
    keyboard = [[
        InlineKeyboardButton(f"Yes, it's a Transfer", callback_data="investment_is_transfer"),
        InlineKeyboardButton(f"No, it's a Direct {activity.capitalize()}", callback_data="investment_is_direct")
    ]]
    await reply_and_log(update, context, f"Is this {activity} a transfer from another of your wallets?", reply_markup=InlineKeyboardMarkup(keyboard))
    return AWAITING_INVESTMENT_TYPE

async def _handle_view_transactions(update, context, session, data):
    """
    Handles a request to view multiple recent transactions.
    """
    count = data.get("count", 5)
    transactions = await db_writer.get_last_n_transactions(session, update.effective_user.id, count)
    
    if not transactions:
        return "Bhai, aapke paas koi transaction nahi hai."

    last_txn_in_list = transactions[-1]
    wallet_id = last_txn_in_list.wallet_id
    wallet_category = last_txn_in_list.wallet.category
    header = f"Here are your last {len(transactions)} transactions:"
    
    await send_interactive_txn_list(
        update=update,
        context=context,
        transactions=transactions,
        header_text=header,
        wallet_id=wallet_id,
        wallet_category=wallet_category,
        period="all_recent",
        page=1
    )
    return None

ACTION_HANDLERS = {
    "add_transaction": _handle_add_transaction,
    "query_last_transaction": _handle_query_last,
    "contextual_edit": _handle_contextual_edit,
    "view_transactions": _handle_view_transactions,
    "create_wallet": _handle_create_wallet,
    "transfer": _handle_transfer,
    "view_wallets": _handle_view_wallets,
    "clarify": _handle_clarify_chat,
    "chat": _handle_clarify_chat,
    "casual_chat": _handle_clarify_chat,
    "edit": _handle_edit_action,
    "delete": _handle_delete_action,
    "edit_wallet": _handle_edit_wallet_action,
    "delete_wallet": _handle_delete_wallet_action,
    "log_investment": _handle_log_investment,
}

# ===================================================================
# The Main Message Handler - The Dispatcher
# ===================================================================

# --- Corrected Function Signature and Structure ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Removed the @with_db_session decorator
    # The function no longer takes 'session' as a direct argument
    
    user_id = update.effective_user.id
    text = update.message.text
    logger.info(f"Received message from {user_id}: '{text}'")
    add_to_history(context, "user", text)

    # Wrap the entire logic in the new session context manager
    async with get_session() as session:
        try:
            history = list(context.user_data.get('message_history', []))
            parsed_actions = await asyncio.to_thread(parse_message, text, history=history)
            
            logger.info(f"LLM parsed actions for {user_id}: {parsed_actions}")
            if not parsed_actions:
                parsed_actions = [{"action": "unknown"}]

            add_actions = [item['data'] for item in parsed_actions if item.get("action") == "add_transaction"]
            if len(add_actions) > 1:
                 context.user_data['multi_tx_pending'] = add_actions
                 keyboard = [
                    [InlineKeyboardButton("Assign Same Wallet to All", callback_data="multi_tx_strategy_same")],
                    [InlineKeyboardButton("Assign Wallets Individually", callback_data="multi_tx_strategy_individual")],
                    [InlineKeyboardButton("Cancel", callback_data="multi_tx_strategy_cancel")]
                 ]
                 await reply_and_log(update, context, "I see multiple transactions. How should I assign wallets?", reply_markup=InlineKeyboardMarkup(keyboard))
                 return AWAIT_ASSIGNMENT_STRATEGY

            newly_added_txns, creation_confirmations, other_confirmations = [], [], []

            for item in parsed_actions:
                action, data = item.get("action", "unknown"), item.get("data", {})
                handler_func = ACTION_HANDLERS.get(action)

                if not handler_func:
                    other_confirmations.append("Bhai, samajh nahi aaya.")
                    continue

                # Pass the session object to the helper functions
                result = await handler_func(update, context, session, data)

                if isinstance(result, int): return result
                if isinstance(result, dict):
                    if result.get("type") == "add_transaction": newly_added_txns.append(result["txn"])
                    elif result.get("type") == "create_wallet": creation_confirmations.append(result["wallet"])
                elif isinstance(result, str):
                    other_confirmations.append(result)

            if newly_added_txns:
                context.user_data['pending_txn_ids'] = [txn.id for txn in newly_added_txns]
                intro_text = "Okay, I've noted the following transaction(s). You can click to manage them."
                return await display_pending_transactions_menu(update, context, session, intro_text)

            summary_parts = []
            if creation_confirmations:
                wallet_lines = [f"  - ✅ {w.name} ({w.category})" for w in creation_confirmations]
                summary_parts.append("✅ Wallets Created:\n" + "\n".join(wallet_lines))
            if other_confirmations:
                summary_parts.extend(other_confirmations)

            if summary_parts:
                await reply_and_log(update, context, "\n\n".join(summary_parts), parse_mode="Markdown")

            return ConversationHandler.END

        except Exception as e:
            logger.error(f"Error in handle_message for {user_id}: {e}", exc_info=True)
            await reply_and_log(update, context, "🤯 Arre yaar, kuch gadbad ho gayi.")
            return ConversationHandler.END
