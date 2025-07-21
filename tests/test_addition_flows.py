# tests/test_addition_flows.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.telegram_bot import (
    handle_message, start_multi_tx_assignment, handle_assignment_strategy, 
    assign_single_wallet_to_all, AWAIT_ASSIGNMENT_STRATEGY, AWAIT_SINGLE_WALLET_CHOICE
)
from telegram.ext import ConversationHandler

# Re-use the session fixture from the other test file
from .test_db_writer import session

@pytest.mark.asyncio
async def test_add_transaction_no_wallet_flow(session, mocker):
    """Tests ADD-TXN-04: Full flow for adding a transaction without a wallet"""
    # 1. Setup
    user_id = 201
    await db_writer.create_wallet(session, user_id, "Cash", "Expense")
    
    # Mock LLM to return one transaction without a wallet
    mocker.patch(
        'app.telegram_bot.parse_message', 
        return_value=[{'action': 'add_transaction', 'data': {'amount': 250, 'note': 'food'}}]
    )
    
    # Mock Telegram objects
    update = AsyncMock()
    update.effective_user.id = user_id
    update.message.text = "250 rs transaction in food"
    context = MagicMock()
    context.user_data = {}

    # 2. Initial message to start the conversation
    result_state = await handle_message(update, context, session)

    # 3. Assert that the bot asks for a wallet assignment strategy
    assert result_state == AWAIT_ASSIGNMENT_STRATEGY
    update.message.reply_text.assert_called_once()
    assert "How should I assign them?" in update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_add_multiple_transactions_flow(session, mocker):
    """Tests ADD-TXN-10: Full flow for adding multiple transactions"""
    # 1. Setup
    user_id = 202
    cash_wallet = await db_writer.create_wallet(session, user_id, "Cash", "Expense")
    
    mocker.patch(
        'app.telegram_bot.parse_message', 
        return_value=[
            {'action': 'add_transaction', 'data': {'amount': 50, 'note': 'chai'}},
            {'action': 'add_transaction', 'data': {'amount': 100, 'note': 'samosa'}}
        ]
    )
    
    update = AsyncMock()
    update.effective_user.id = user_id
    update.message.text = "50 for chai, 100 for samosa"
    context = MagicMock()
    context.user_data = {}

    # 2. Initial message
    result_state = await handle_message(update, context, session)
    assert result_state == AWAIT_ASSIGNMENT_STRATEGY

    # 3. Simulate user clicking "Assign Same Wallet to All"
    query = AsyncMock()
    query.data = "multi_tx_strategy_same"
    query.from_user.id = user_id
    update.callback_query = query
    
    result_state_2 = await handle_assignment_strategy(update, context, session)
    assert result_state_2 == AWAIT_SINGLE_WALLET_CHOICE
    query.edit_message_text.assert_called_with("Okay, which wallet should I use for all transactions?", reply_markup=mocker.ANY)

    # 4. Simulate user clicking the "Cash" wallet
    query_2 = AsyncMock()
    query_2.data = f"multi_tx_select_wallet_{cash_wallet.id}"
    query_2.from_user.id = user_id
    update.callback_query = query_2
    
    result_state_3 = await assign_single_wallet_to_all(update, context, session)
    assert result_state_3 == ConversationHandler.END
    query_2.edit_message_text.assert_called_with(f"✅ All 2 transactions have been added to the 'Cash' wallet.")
    
    # 5. Final verification
    all_txns = await db_writer.get_all_transactions(session, user_id)
    assert len(all_txns) == 2