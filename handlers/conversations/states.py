# /handlers/conversations/states.py

# A single, unified range for all conversation states
(
    # Editing a transaction
    SELECTING_EDIT_FIELD, GETTING_NEW_EDIT_VALUE,

    # Deleting a transaction
    SELECTING_DELETE_CANDIDATE,

    # Adding a transaction (default wallet flow)
    CONFIRM_DEFAULT_WALLET, AWAITING_WALLET_NAME, HANDLE_UNKNOWN_WALLET,

    # Adding an investment
    AWAITING_INVESTMENT_TYPE, AWAITING_TRANSFER_WALLET,

    # Updating a wallet balance
    AWAITING_BALANCE_UPDATE_CATEGORY,

    # Creating a new wallet
    AWAITING_NEW_WALLET_NAME, AWAITING_NEW_WALLET_BALANCE,

    # Deleting a wallet
    CONFIRM_WALLET_DELETION,

    # Editing a wallet
    SELECT_WALLET_TO_EDIT, SELECT_WALLET_FIELD, AWAIT_NEW_WALLET_VALUE,

    # Period comparison analysis
    AWAIT_FIRST_PERIOD, AWAIT_SECOND_PERIOD,

    # Post-action confirmation flow
    AWAIT_ACTION_CONFIRMATION, MANAGING_PENDING_ITEM,

    # Multi-transaction wallet assignment
    AWAIT_ASSIGNMENT_STRATEGY, AWAIT_SINGLE_WALLET_CHOICE, ASSIGNING_INDIVIDUALLY
) = range(22)