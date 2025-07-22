# /config.py
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# --- Core Bot Config ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# --- Bot Personality & Text ---
WELCOME_TEXT = (
    "👋 Arre bhai! Main hoon *Money Bhai* – Your Finance Dost!\n\n"
    "Main ab wallets support karta hoon. Saare transactions wallets se record honge.\n"
    "By default, aapke paas 'Cash' aur 'Investment' wallets hain.\n\n"
    "Try examples like:\n"
    "– `500 for pizza from my bank account`\n"
    "– `create a new wallet named Credit Card`\n"
    "– `transfer 1000 from Cash to Zerodha`\n"
    "– `show my wallets` or `/start`\n"
    "– `/help` for more options"
)

# --- Emojis ---
CATEGORY_EMOJIS = {
    "food": "🍔", "groceries": "🛒", "entertainment": "🎮", "bills": "💡",
    "shopping": "🛍️", "travel": "✈️", "education": "📚", "medical": "💊",
    "income": "💰", "Investment": "📈", "other": "🔀",'Expense': '💸','Goal': '💸'
}