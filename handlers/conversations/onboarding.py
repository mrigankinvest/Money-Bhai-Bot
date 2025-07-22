# handlers/conversations/onboarding.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from db import db_writer
from handlers.commands import help_command

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for the conversation
GET_NAME, CONFIRM_NAME = range(2)

WELCOME_TEXT = (
    "👋 Arre bhai! Main hoon *Money Bhai* – Your Finance Dost!\n\n"
    "Main aapke saare kharchon aur investments ka hisaab-kitaab rakhne mein help karunga. "
    "Aap natural language mein transactions add kar sakte hain, jaise '5000 in stocks from Zerodha' "
    "aur main samajh jaunga.\n\n"
    "Shuru karne se pehle, kya mai apka naam jaan skta hun?"
)

async def ask_for_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Starts the onboarding conversation. Greets the user, explains the bot's purpose,
    and asks for their name.
    """
    user_id = update.message.from_user.id
    logger.info(f"User {user_id} started the onboarding process.")

    # Check if the user already exists and has a name.
    user, created = await db_writer.get_or_create_user(user_id)

    # If user is not new and already has a name, just show the help message.
    if not created and user.name:
        logger.info(f"User {user_id} ({user.name}) is already onboarded. Sending help text.")
        await help_command(update, context)
        return ConversationHandler.END

    # If the user is new or doesn't have a name, ask for it.
    await context.bot.send_message(
        chat_id=user_id,
        text=WELCOME_TEXT,
        parse_mode='Markdown'
    )
    return GET_NAME

async def ask_for_name_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Stores the provided name in context and asks for confirmation.
    """
    user_name = update.message.text.strip()
    logger.info(f"User {update.message.from_user.id} provided potential name: {user_name}")

    # Validate name
    if not user_name or len(user_name) > 50:
        await update.message.reply_text("Bhai, sahi naam daalo. Please try again.")
        return GET_NAME

    # Store name temporarily in user_data
    context.user_data['name'] = user_name

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data="confirm_name"),
            InlineKeyboardButton("✏️ Change", callback_data="change_name"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Aapka naam *{user_name}* hai. Kya ab se main aapko isi naam se bula sakta hun?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return CONFIRM_NAME

async def save_name_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Saves the user's name to the database after confirmation and ends the conversation.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_name = context.user_data.get('name')

    logger.info(f"User {user_id} confirmed name: {user_name}")

    # Save the name to the database
    await db_writer.update_user_name(user_id, user_name)

    confirmation_text = (
        f"Welcome, *{user_name}*! Ab se main aapko isi naam se bulaunga.\n\n"

                "Main apki personal finance journey ka partner hun. Saare transactions wallets se record honge, with full encryption to protect your data\n"
            "By default, aapke paas 'Cash' aur 'Investment' wallets hain.\n\n"
            "Try examples like:\n"
            "– `500 for pizza from my bank account`\n"
            "– `create a new wallet named Credit Card`\n"
            "– `transfer 1000 from Cash to Zerodha`\n"
            "– `show my wallets` or `/start`\n"
            "– `/help` for more options"
    )
    await query.edit_message_text(text=confirmation_text, parse_mode='Markdown')

    # Clean up user_data
    del context.user_data['name']

    return ConversationHandler.END

async def change_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles the user's request to change the name they entered.
    """
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="Koi baat nahi. Please apna sahi naam type karein.")
    return GET_NAME

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user_id = update.message.from_user.id
    logger.info(f"User {user_id} canceled the conversation.")
    await update.message.reply_text("Koi baat nahi. Jab mann kare, /start type kar dena.")
    return ConversationHandler.END
