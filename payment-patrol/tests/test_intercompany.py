from __future__ import annotations

from pathlib import Path

from src.ingest import parse_csv
from src.intercompany import filter_intercompany


def _sample_transaction_with_name(customer_name: str):
    transactions, _ = parse_csv(Path("tests/fixtures/sample_fleetio.csv").read_bytes(), entity="fleetio")
    return transactions[0].model_copy(update={"customer_name": customer_name})


def test_filter_classifies_fleetio_as_intercompany() -> None:
    transaction = _sample_transaction_with_name("Fleetio")

    external_transactions, intercompany_transactions = filter_intercompany([transaction])

    assert external_transactions == []
    assert intercompany_transactions == [transaction]


def test_filter_classifies_enterprise_as_external() -> None:
    transaction = _sample_transaction_with_name("Enterprise Holdings")

    external_transactions, intercompany_transactions = filter_intercompany([transaction])

    assert external_transactions == [transaction]
    assert intercompany_transactions == []


def test_filter_preserves_original_transaction_count() -> None:
    fleetio = _sample_transaction_with_name("Fleetio")
    external = _sample_transaction_with_name("Enterprise Holdings")
    transactions = [fleetio, external]

    external_transactions, intercompany_transactions = filter_intercompany(transactions)

    assert len(external_transactions) + len(intercompany_transactions) == len(transactions)
