import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, User, Message, Chat, CallbackQuery, BotCommand
# --- FIX: Import the Application class ---
from telegram.ext import ConversationHandler, ContextTypes, Application

# Import the functions and states we are testing
from handlers.conversations import onboarding
from db.models import User as UserModel
from bot_setup import set_bot_commands 

# Use pytest-asyncio to handle async functions
pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_context():
    """Creates a mock Telegram Context object with user_data."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock()
    context.user_data = {}
    return context

@pytest.fixture
def mock_update_factory():
    """
    A factory fixture to create mock Telegram Update objects.
    """
    def _factory(text: str = None, callback_data: str = None):
        user = User(id=12345, first_name="Test", is_bot=False, username="testuser")
        chat = Chat(id=12345, type="private")
        
        if text is not None:
            message = MagicMock(spec=Message)
            message.message_id = 1
            message.date = None
            message.chat = chat
            message.from_user = user
            message.text = text
            message.reply_text = AsyncMock()
            return Update(update_id=1, message=message)
        
        if callback_data is not None:
            callback_query = MagicMock(spec=CallbackQuery)
            callback_query.id = "1"
            callback_query.from_user = user
            callback_query.chat_instance = "1"
            callback_query.data = callback_data
            callback_query.message = MagicMock(spec=Message)
            callback_query.answer = AsyncMock()
            callback_query.edit_message_text = AsyncMock()
            return Update(update_id=2, callback_query=callback_query)
            
        raise ValueError("Must provide either text or callback_data")
        
    return _factory


class TestOnboardingFlow:
    """
    A class to group all tests related to the user onboarding flow.
    """

    @patch('handlers.conversations.onboarding.db_writer.get_or_create_user')
    async def test_01_new_user_start(self, mock_get_or_create_user, mock_update_factory, mock_context):
        """T-01 Part 1: Tests that a new user is greeted and asked for their name."""
        async def mock_db_call(telegram_id):
            return (UserModel(telegram_id=telegram_id, name=None), True)
        mock_get_or_create_user.side_effect = mock_db_call
        
        update = mock_update_factory(text="/start")
        next_state = await onboarding.ask_for_name(update, mock_context)

        mock_get_or_create_user.assert_called_once_with(12345)
        mock_context.bot.send_message.assert_called_once_with(
            chat_id=12345,
            text=onboarding.WELCOME_TEXT,
            parse_mode='Markdown'
        )
        assert next_state == onboarding.GET_NAME

    async def test_02_user_provides_name(self, mock_update_factory, mock_context):
        """T-01 Part 2: Tests that the bot asks for confirmation after getting a name."""
        user_name = "Mrigank"
        update = mock_update_factory(text=user_name)
        next_state = await onboarding.ask_for_name_confirmation(update, mock_context)

        assert mock_context.user_data['name'] == user_name
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert f"Aapka naam *{user_name}* hai" in call_args.args[0]
        assert call_args.kwargs['reply_markup'] is not None
        assert next_state == onboarding.CONFIRM_NAME

    @patch('handlers.conversations.onboarding.db_writer.update_user_name')
    async def test_03_user_confirms_name(self, mock_update_user_name, mock_update_factory, mock_context):
        """T-01 Part 3: Tests that the name is saved after user confirmation."""
        user_name = "Mrigank"
        mock_context.user_data['name'] = user_name
        update = mock_update_factory(callback_data="confirm_name")
        final_state = await onboarding.save_name_confirmed(update, mock_context)

        mock_update_user_name.assert_called_once_with(12345, user_name)
        update.callback_query.answer.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once()
        call_args = update.callback_query.edit_message_text.call_args
        # --- FIX: Check for the welcome message text from your bot's actual output ---
        assert f"Welcome, *{user_name}*!" in call_args.kwargs['text']
        assert 'name' not in mock_context.user_data
        assert final_state == ConversationHandler.END

    async def test_04_user_changes_name(self, mock_update_factory, mock_context):
        """T-01 Part 4: Tests that the bot re-asks for a name if user clicks 'Change'."""
        mock_context.user_data['name'] = "WrongName"
        update = mock_update_factory(callback_data="change_name")
        next_state = await onboarding.change_name(update, mock_context)

        update.callback_query.answer.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once_with(
            text="Koi baat nahi. Please apna sahi naam type karein."
        )
        assert next_state == onboarding.GET_NAME

# =============================================================================
# === T-04 NEW TEST CASE FOR BOT MENU ==============================================
# =============================================================================

class TestBotSetup:
    """
    Tests the initial setup of the bot, such as registering commands.
    """

    @patch('telegram.ext.Application.bot', new_callable=AsyncMock)
    async def test_sets_menu_commands_on_startup(self, mock_bot):
        """
        T-04: Tests that the bot registers the command menu with Telegram on startup.
        """
        # --- Arrange ---
        mock_app = MagicMock(spec=Application)
        mock_app.bot = mock_bot
        
        # Define the new, expanded list of commands
        expected_commands = [
            BotCommand("aboutme", "ℹ️ About Money Bhai Bot"),
            BotCommand("home", "🏠 Main Dashboard"),
            BotCommand("actions", "⚡ Quick Actions (Add, Edit, etc.)"),
            BotCommand("records", "📂 View Past Records"),
            BotCommand("investments", "📈 Manage Investments"),
            BotCommand("statistics", "📊 View Charts & Statistics"),
            BotCommand("plannedpayments", "🗓️ Upcoming Planned Payments"),
            BotCommand("budgets", "💰 Set & View Budgets"),
            BotCommand("debt", "💸 Track Debt"),
            BotCommand("goals", "🎯 Set & View Financial Goals"),
            BotCommand("follow", "🔗 Follow us on Social Media"),
            BotCommand("contact", "💬 Contact Support")
        ]

        # --- Act ---
        await set_bot_commands(mock_app)

        # --- Assert ---
        mock_bot.set_my_commands.assert_awaited_once()
        actual_commands = mock_bot.set_my_commands.call_args.args[0]
        
        assert len(actual_commands) == len(expected_commands)
        # Sort by command name to ensure consistent comparison
        sorted_actual = sorted(actual_commands, key=lambda x: x.command)
        sorted_expected = sorted(expected_commands, key=lambda x: x.command)
        
        for actual, expected in zip(sorted_actual, sorted_expected):
            assert actual.command == expected.command
            assert actual.description == expected.description
    