import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import (
    Update, User, Message, Chat, CallbackQuery, BotCommand,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import ConversationHandler, ContextTypes, Application

# Import the functions we are testing
from handlers.conversations import onboarding
from handlers.commands import aboutme, handle_time_horizon_selection
from utils.telegram_helpers import send_wallet_overview, reply_and_log, edit_and_log
from db.models import User as UserModel
from bot_setup import set_bot_commands

# Use pytest-asyncio to handle async functions
pytestmark = pytest.mark.asyncio

# --- Fixtures (mock_context, mock_update_factory) remain unchanged ---
@pytest.fixture
def mock_context():
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock()
    context.user_data = {}
    return context

@pytest.fixture
def mock_update_factory():
    def _factory(text: str = None, callback_data: str = None):
        user = User(id=12345, first_name="Test", is_bot=False, username="testuser")
        chat = Chat(id=12345, type="private")
        if text is not None:
            message = MagicMock(spec=Message, text=text, from_user=user, chat=chat, message_id=1, date=None)
            message.reply_text = AsyncMock()
            return Update(update_id=1, message=message)
        if callback_data is not None:
            callback_query = MagicMock(spec=CallbackQuery, data=callback_data, from_user=user, id="1", chat_instance="1")
            callback_query.message = MagicMock(spec=Message)
            callback_query.answer = AsyncMock()
            callback_query.edit_message_text = AsyncMock()
            return Update(update_id=2, callback_query=callback_query)
        raise ValueError("Must provide either text or callback_data")
    return _factory


class TestOnboardingFlow:
    """Tests the complete user onboarding conversation flow."""

    @patch('handlers.conversations.onboarding.db_writer.get_or_create_user')
    async def test_01_new_user_start(self, mock_get_or_create_user, mock_update_factory, mock_context):
        """
        T-01.1: Verifies the initial interaction for a brand new user.
        
        This test ensures that when a user sends '/start' for the first time,
        the bot correctly sends the welcome message and transitions the conversation
        to the GET_NAME state, prompting the user for their name.
        """
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
        """
        T-01.2: Checks that the bot correctly handles the user's name input.
        
        This test simulates the user providing their name. It verifies that the
        name is temporarily stored in the context's user_data and that the bot
        replies by asking for confirmation with 'Confirm' and 'Change' buttons.
        """
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
        """
        T-01.3: Ensures the user's name is saved after they confirm it.
        
        This test simulates the user clicking the 'Confirm' button. It verifies
        that the bot calls the database function to save the name, sends a final
        welcome message, clears the temporary name from user_data, and ends the conversation.
        """
        user_name = "Mrigank"
        mock_context.user_data['name'] = user_name
        update = mock_update_factory(callback_data="confirm_name")
        final_state = await onboarding.save_name_confirmed(update, mock_context)
        mock_update_user_name.assert_called_once_with(12345, user_name)
        update.callback_query.answer.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once()
        call_args = update.callback_query.edit_message_text.call_args
        assert f"Welcome, *{user_name}*!" in call_args.kwargs['text']
        assert 'name' not in mock_context.user_data
        assert final_state == ConversationHandler.END

    async def test_04_user_changes_name(self, mock_update_factory, mock_context):
        """
        T-01.4: Tests the flow for when a user decides to change their name.
        
        This test simulates the user clicking the 'Change' button. It ensures
        the bot acknowledges the request and correctly transitions back to the
        GET_NAME state, re-prompting the user for their name.
        """
        mock_context.user_data['name'] = "WrongName"
        update = mock_update_factory(callback_data="change_name")
        next_state = await onboarding.change_name(update, mock_context)
        update.callback_query.answer.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once_with(
            text="Koi baat nahi. Please apna sahi naam type karein."
        )
        assert next_state == onboarding.GET_NAME

class TestBotSetup:
    """Tests the initial setup of the bot."""

    @patch('telegram.ext.Application.bot', new_callable=AsyncMock)
    async def test_sets_menu_commands_on_startup(self, mock_bot):
        """
        T-04: Verifies that the bot's command menu is set correctly on startup.
        
        This test checks the bot's initialization process. It ensures that the
        `set_bot_commands` function is called and that it registers the complete
        and accurate list of commands with Telegram, making them visible to users.
        """
        mock_app = MagicMock(spec=Application)
        mock_app.bot = mock_bot
        
        expected_commands = [
            BotCommand("aboutme", "ℹ️ About Money Bhai Bot"), BotCommand("home", "🏠 Main Dashboard"),
            BotCommand("actions", "⚡ Quick Actions (Add, Edit, etc.)"), BotCommand("records", "📂 View Past Records"),
            BotCommand("investments", "📈 Manage Investments"), BotCommand("statistics", "📊 View Charts & Statistics"),
            BotCommand("plannedpayments", "🗓️ Upcoming Planned Payments"), BotCommand("budgets", "💰 Set & View Budgets"),
            BotCommand("debt", "💸 Track Debt"), BotCommand("goals", "🎯 Set & View Financial Goals"),
            BotCommand("follow", "🔗 Follow us on Social Media"), BotCommand("contact", "💬 Contact Support")
        ]

        await set_bot_commands(mock_app)

        mock_bot.set_my_commands.assert_awaited_once()
        actual_commands = mock_bot.set_my_commands.call_args.args[0]
        assert sorted(actual_commands, key=lambda x: x.command) == sorted(expected_commands, key=lambda x: x.command)

class TestAboutCommand:
    """Tests the /aboutme command."""

    async def test_t05_about_command_sends_correct_message(self, mock_update_factory, mock_context):
        """
        T-05: Validates the content and format of the /aboutme command's response.
        
        This test ensures that when a user sends the `/aboutme` command, the bot
        replies with the exact, pre-defined informational text about the bot's
        features and purpose, correctly formatted using Markdown.
        """
        update = mock_update_factory(text="/aboutme")
        expected_message = (
            "🤖 *Mera Naam Hai Money Bhai!* 💰\n\n"
            "Main aapka personal finance dost hoon, jo aapke paise ka hisaab-kitaab ekdum simple aur mazedaar bana dega!\n\n"
            "✨ *Main Kya Kar Sakta Hoon?*\n\n"
            "🗣️ **Natural Language:** Bas mujhe normal message bhejo, jaise dosto se baat karte ho! (e.g., `100 ka petrol dala ⛽`)\n\n"
            "💳 **Wallet Management:** Alag-alag wallets banao - Kharchon ke liye 🛍️, Investments ke liye 📈, ya aur kisi cheez ke liye!\n\n"
            "📊 **Data Analysis:** Apne kharchon ko beautiful charts aur graphs mein dekho. Pata lagao paisa jaa kahan raha hai!\n\n"
            "🔒 **Secure & Private:** Aapka saara data 100% safe aur private hai. Tension not!\n\n"
            "My goal is to help you get a clear picture of your finances without the hassle of complex apps 🚀"
        )
        await aboutme(update, mock_context)
        update.message.reply_text.assert_called_once_with(expected_message, parse_mode='Markdown')


class TestHomeCommandWithTimeHorizon:
    """
    Tests the updated /home command flow with the interactive time horizon dropdown.
    """

    @patch('utils.telegram_helpers.db_writer.get_financial_summary_for_period')
    @patch('utils.telegram_helpers.reply_and_log', new_callable=AsyncMock)
    async def test_t07_home_command_shows_default_dashboard(
        self, mock_reply_and_log, mock_get_summary, mock_update_factory, mock_context
    ):
        """
        T-07: Verifies the initial /home command shows a dashboard with a
        time horizon dropdown, defaulting to the "Current Month" view.
        """
        mock_get_summary.return_value = {
            'total_expense': 1200.0, 'total_income': 8000.0,
            'net_investment': 15000.0, 'goal_status': 'On Track'
        }
        update = mock_update_factory(text="/home")

        expected_keyboard = [
            [InlineKeyboardButton("📅 Time Horizon: Current Month", callback_data="select_time_horizon")],
            [InlineKeyboardButton("💳 Expenses: ₹1,200.00", callback_data="view_expenses_current_month")],
            [InlineKeyboardButton("💰 Income: ₹8,000.00", callback_data="view_income_current_month")],
            [InlineKeyboardButton("📈 Investments: ₹15,000.00", callback_data="view_investments_current_month")],
            [InlineKeyboardButton("🎯 Goal: On Track", callback_data="show_goal_detail")]
        ]
        # --- FIX: Define the expected_markup variable that was missing ---
        expected_markup = InlineKeyboardMarkup(expected_keyboard)
        expected_message_text = "Here is your financial dashboard:"

        await send_wallet_overview(update, mock_context, period="current_month")

        mock_get_summary.assert_called_once_with(user_id=12345, period="current_month")
        mock_reply_and_log.assert_called_once()
        call_args, call_kwargs = mock_reply_and_log.call_args
        
        assert call_args[2] == expected_message_text
        actual_markup = call_kwargs.get('reply_markup')
        assert actual_markup.inline_keyboard == expected_markup.inline_keyboard

    # --- FIX: Patch the correct path for the helper function ---
    @patch('handlers.commands.edit_and_log', new_callable=AsyncMock)
    async def test_t08_time_horizon_button_shows_options(
        self, mock_edit_and_log, mock_update_factory, mock_context
    ):
        """
        T-08: Verifies that clicking the time horizon button reveals all
        the available time period options.
        """
        update = mock_update_factory(callback_data="select_time_horizon")

        expected_keyboard = [
            [InlineKeyboardButton("Current Month ✅", callback_data="set_period_current_month")],
            [InlineKeyboardButton("Last Month", callback_data="set_period_last_month")],
            [InlineKeyboardButton("Last 3 Months", callback_data="set_period_last_3_months")],
            [InlineKeyboardButton("Last 6 Months", callback_data="set_period_last_6_months")],
            [InlineKeyboardButton("Current Financial Year", callback_data="set_period_current_fy")],
            [InlineKeyboardButton("Select Date Range", callback_data="select_date_range")],
            [InlineKeyboardButton("All Time", callback_data="set_period_all")],
            [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="home")]
        ]
        expected_markup = InlineKeyboardMarkup(expected_keyboard)
        expected_message_text = "Please select a time horizon:"

        await handle_time_horizon_selection(update, mock_context)

        # Assert that our helper function was called, not the raw telegram method
        mock_edit_and_log.assert_called_once()
        
        _ , call_kwargs = mock_edit_and_log.call_args
        assert call_kwargs.get('text') == expected_message_text
        actual_markup = call_kwargs.get('reply_markup')
        assert actual_markup.inline_keyboard == expected_markup.inline_keyboard