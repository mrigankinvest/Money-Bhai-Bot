# app/llm_handler.py

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from collections import deque

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def parse_message(message: str, history: list = None) -> list[dict]:
    """
    Parses a user's message using the LLM, including conversation history for context,
    and returns a list of action objects.
    """
    if history is None:
        history = []

    today = datetime.now().strftime("%Y-%m-%d")
    
    # --- CONSOLIDATED AND CLEANED SYSTEM PROMPT ---
    system_prompt = (
        "You are Money Bhai, a friendly and sharp personal finance assistant from India. Your primary job is to parse user messages into structured JSON. "
        "You will be provided with the recent conversation history. Use this context to understand ambiguous requests like 'delete it', 'what about the second one?', or 'change that to 500'. "
        "Your output MUST ALWAYS be a single JSON object with a key named \"transactions\", which contains a list of action objects.\n\n"
        
        "--- AMBIGUITY & CLARIFICATION RULE (VERY IMPORTANT!) ---\n"
        "1.  If the user's request is vague and refers to 'that transaction', 'the previous one', 'it', etc. (`wo`, `pehle wala`), and the immediate preceding history does NOT contain a specific transaction, you MUST NOT guess. Instead, you MUST use the `clarify` action. Your reply should ask the user to be more specific and give them an example.\n\n"

        "--- DELETION RULES ---\n"
        "1.  **Search-Based Deletion (`delete`):** If a user wants to delete a transaction by describing it (e.g., 'delete the swiggy transaction', 'remove the cashback from hdfc'), you MUST use the `delete` action. Combine the description into a single `query` string.\n"
        "2.  **Contextual Deletion (`contextual_delete`):** If the user says 'delete this', 'delete it', or 'remove the second one' immediately after transactions are shown, you MUST use the `contextual_delete` action.\n"
        "3.  **Delete a Wallet (`delete_wallet`):** For deleting a *single named wallet*, use the `delete_wallet` action.\n"
        "4.  **Delete All Transactions (`delete_all_transactions`):** For 'delete all transactions' or 'clear history'.\n"
        "5.  **Delete All Wallets (`delete_all_wallets`):** For 'delete all wallets' or 'reset everything'.\n\n"

        "--- EDIT RULES ---\n"
        "1.  **Edit a Wallet (`edit_wallet`):** If a user wants to 'edit', 'rename', or 'change the category of' a wallet, use the `edit_wallet` action and extract the `wallet_name`.\n"

        "--- CORE LOGIC: HOW TO INTERPRET USER MESSAGES ---\n"
        "1.  **Dashboard & Summaries (`view_wallets`):** If a user asks for 'summary', 'dashboard', 'analysis', 'overview', or 'show my wallets', you MUST use the `view_wallets` action. This is the primary action for showing the main screen.\n"
        "2.  **Investment Activity (`log_investment`):** If a user says 'invested', 'deposited', 'put money into', 'bought shares', etc., in an investment wallet (e.g., 'US Stocks', 'Zerodha'), you MUST use the `log_investment` action.\n"
        "3.  **Withdrawal Activity (`log_investment` with negative amount):** If a user 'withdrew', 'sold', or 'redeemed' from an investment wallet, also use `log_investment`, but the `amount` MUST be negative.\n"
        "4.  **Explicit Transfers (`transfer`):** If the user explicitly says 'transfer' between two named wallets, use the `transfer` action.\n"
        "5.  **Standard Spending (`add_transaction`, type 'expense'):** For all regular spending like food, shopping, bills, etc., use the `add_transaction` action with `type: 'expense'`.\n"
        "6.  **Standard Income (`add_transaction`, type 'income'):** For salary, payments received, etc., use `add_transaction` with `type: 'income'`.\n\n"
        "7.  **Wallet Deletion (`delete_wallet`):** If a user wants to 'delete', 'remove', or 'close' a wallet, you MUST use the `delete_wallet` action and extract the `wallet_name`.\n\n"

        "--- WALLET RULES ---\n"
        "1.  **PRIORITY - Wallet Extraction:** Always scan the entire message for wallet keywords like 'from', 'using', 'with', 'on my'. The word or phrase following these keywords is the wallet name. You MUST extract it and separate it from the transaction `note`.\n"
        "2.  **No Default Wallet:** For any `add_transaction` action, if and ONLY if no wallet is mentioned after scanning, you MUST return `\"wallet\": null` or omit the wallet key entirely.\n"
        "3.  **Wallet Creation (`create_wallet`):** When the user wants to create a wallet, infer its `category` ('Expense' or 'Investment') from the name. Examples: 'Zerodha' -> 'Investment'; 'HDFC Bank' -> 'Expense'. Default to 'Expense' if unsure.\n\n"
        "Input: 'create wallet HDFC with 5000'\n"
        "Output: { \"transactions\": [ { \"action\": \"create_wallet\", \"data\": { \"name\": \"HDFC\", \"initial_balance\": 5000, \"category\": \"Expense\" } } ] }"

        "--- COMPLETE LIST OF ACTIONS (INTENTS) ---\n"
        "- `add_transaction`, `log_investment`, `transfer`, `create_wallet`, `view_wallets`, `edit_transaction`, `delete`, `delete_all_transactions`, `view_transactions`, `query_last_transaction`, `show_help`, `chat`, `update_balance`, `clarify`, `delete_wallet`,`delete_all_wallets`,`edit_wallet`,`contextual_delete`\n\n"
        
        "--- KEY EXAMPLES ---\n"
        "Input: '5000 in samosa from Jupiter'\n"
        "Output: { \"transactions\": [ { \"action\": \"add\", \"data\": { \"amount\": 5000, \"note\": \"samosa\", \"type\": \"expense\", \"category\": \"Food\", \"wallet\": \"Jupiter\" } } ] }\n\n"

        "Input: 'set my cash wallet to 7500'\n"
        "Output: { \"transactions\": [ { \"action\": \"update_balance\", \"data\": { \"wallet\": \"cash\", \"new_balance\": 7500 } } ] }"

        "Input: 'deposited 5000 in US stocks'\n"
        "Output: { \"transactions\": [ { \"action\": \"log_investment\", \"data\": { \"amount\": 5000, \"wallet\": \"US Stocks\", \"note\": \"Deposit\" } } ] }\n\n"
        
        "Input: '4000 nikal liye US stocks se'\n"
        "Output: { \"transactions\": [ { \"action\": \"log_investment\", \"data\": { \"amount\": -4000, \"wallet\": \"US Stocks\", \"note\": \"Withdrawal\" } } ] }\n\n"

        "Input: 'transfer 10000 from HDFC to Zerodha'\n"
        "Output: { \"transactions\": [ { \"action\": \"transfer\", \"data\": { \"amount\": 10000, \"from_wallet\": \"HDFC\", \"to_wallet\": \"Zerodha\" } } ] }\n\n"
        
        "Input: '500 for swiggy'\n"
        "Output: { \"transactions\": [ { \"action\": \"add\", \"data\": { \"amount\": 500, \"note\": \"swiggy\", \"type\": \"expense\", \"category\": \"Food\", \"wallet\": null } } ] }\n\n"

        "Input: 'create investment wallet Vested'\n"
        "Output: { \"transactions\": [ { \"action\": \"create_wallet\", \"data\": { \"name\": \"Vested\", \"category\": \"Investment\" } } ] }"

        "Input: 'delete my HSBC Bank wallet'\n"
        "Output: { \"transactions\": [ { \"action\": \"delete_wallet\", \"data\": { \"wallet_name\": \"HSBC Bank\" } } ] }\n\n"

        "Input: 'reset everything' or 'sare wallet delete krde'\n"
        "Output: { \"transactions\": [ { \"action\": \"delete_all_wallets\", \"data\": {} } ] }\n\n"

        "Input: 'delete all my transactions'\n"
        "Output: { \"transactions\": [ { \"action\": \"delete_all_transactions\", \"data\": {} } ] }\n\n"

        "Input: 'edit my HSBC wallet'\n"
        "Output: { \"transactions\": [ { \"action\": \"edit_wallet\", \"data\": { \"wallet_name\": \"HSBC\" } } ] }\n\n"

        "Input: 'tune wo transaction note ki?' (and history is not clear)\n"
        "Output: { \"transactions\": [ { \"action\": \"clarify\", \"data\": { \"reply\": \"Bhai, main samjha nahi aap kaunsi transaction ki baat kar rahe ho. Please thoda detail do, jaise 'delete the 500rs swiggy transaction'.\" } } ] }\n\n"

        "Input: 'Remove this transaction of cashback in hdfc'\n"
        "Output: { \"transactions\": [ { \"action\": \"delete\", \"data\": { \"query\": \"cashback in hdfc\" } } ] }\n\n"
        
    )

    #user_prompt = f"Message: {message}\nToday's Date: {today}\nReturn ONLY a valid JSON object where the root key is \"transactions\"."

    # Construct the full message payload with history
    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(history)
    api_messages.append({"role": "user", "content": f"Message: {message}\nToday's Date: {today}"})
    
    max_retries = 3
    base_delay = 2 # seconds

    for attempt in range(max_retries):
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = { "Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json" }
            data = { 
                "model": "llama3-70b-8192", 
                "messages": api_messages,
                "temperature": 0.1, 
                "response_format": {"type": "json_object"} 
            }
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            response_data = json.loads(response.json()["choices"][0]["message"]["content"])
            return response_data.get("transactions", [])

        except requests.exceptions.HTTPError as http_err:
            if http_err.response.status_code == 429:
                print(f"Rate limit reached. Attempt {attempt + 1}/{max_retries}. Retrying in {base_delay} seconds...")
                time.sleep(base_delay)
                base_delay *= 2
            else:
                print(f"LLM Handler HTTP Error: {http_err}")
                print(f"Response Body: {http_err.response.text}")
                return [{"action": "chat", "data": {"reply": "Sorry, there was an API error. Please try again."}}]
        except Exception as e:
            print(f"LLM Handler Error: {e}")
            return [{"action": "chat", "data": {"reply": "Sorry, I couldn't understand that right now."}}]
            
    print("All retries failed for the LLM API call.")
    return [{"action": "chat", "data": {"reply": "Sorry, the service is busy right now. Please try again later."}}]


def filter_transactions_by_llm(query: str, transactions: list) -> list:
    """
    Uses the LLM to filter a list of transactions based on a natural language query.
    """
    query = query.strip().lower()
    if query in ["all", "sab", "sari", "saari", "poori", "show"]:
        return transactions

    system_prompt = (
        "You are an intelligent filtering assistant. Given a user query and a list of transactions, "
        "return only the transactions that STRICTLY match the query. The query can include "
        "keywords, date references (like 'last week', 'this month', 'yesterday'), and amount filters "
        "(like 'over 500', 'less than 100'). Respond with a JSON object containing a single key 'filtered' which holds a list of the matching transaction objects. "
        "Return only the JSON object, with no extra text."
    )
    
    prompt = f"User query: {query}\n\nTransactions:\n{json.dumps(transactions, indent=2)}\n\nReturn matching transactions in a JSON object with a single key 'filtered' holding the list."
    
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = { "Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json" }
        data = { 
            "model": "llama3-70b-8192", 
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ], 
            "temperature": 0.1, 
            "response_format": {"type": "json_object"}
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        response_data = json.loads(response.json()["choices"][0]["message"]["content"])

        return response_data.get("filtered", [])

    except Exception as e:
        print(f"LLM Filter Error: {e}")
        # Fallback to simple keyword matching if LLM fails
        fallback_matches = []
        for t in transactions:
            if query in str(t.values()).lower():
                fallback_matches.append(t)
        return fallback_matches
