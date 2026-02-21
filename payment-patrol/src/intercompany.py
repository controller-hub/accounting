from __future__ import annotations

from .models import ARTransaction

INTERCOMPANY_KEYWORDS = ("fleetio", "rarestep", "stingray", "auto integrate")


def filter_intercompany(
    transactions: list[ARTransaction],
) -> tuple[list[ARTransaction], list[ARTransaction]]:
    external_transactions: list[ARTransaction] = []
    intercompany_transactions: list[ARTransaction] = []

    for transaction in transactions:
        customer_name = transaction.customer_name.lower()
        if any(keyword in customer_name for keyword in INTERCOMPANY_KEYWORDS):
            intercompany_transactions.append(transaction)
            continue

        external_transactions.append(transaction)

    return external_transactions, intercompany_transactions
