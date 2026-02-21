from __future__ import annotations

from pathlib import Path

from src.ingest import parse_csv


def test_parse_fleetio_row_count() -> None:
    txs, _ = parse_csv(Path("tests/fixtures/sample_fleetio.csv").read_bytes(), entity="fleetio")
    assert len(txs) == 20


def test_sign_correction_credit_negative() -> None:
    txs, _ = parse_csv(Path("tests/fixtures/sample_fleetio.csv").read_bytes(), entity="fleetio")
    credit = next(t for t in txs if t.type == "Credit Memo")
    assert credit.signed_amount_remaining < 0


def test_date_parsing_supports_two_formats() -> None:
    txs, _ = parse_csv(Path("tests/fixtures/sample_fleetio.csv").read_bytes(), entity="fleetio")
    assert any(t.document_number == "INV-1001" and t.invoice_date.isoformat() == "2026-01-05" for t in txs)
    assert any(t.document_number == "INV-1002" and t.invoice_date.isoformat() == "2026-01-08" for t in txs)


def test_blank_fields_do_not_crash() -> None:
    txs, _ = parse_csv(Path("tests/fixtures/sample_fleetio.csv").read_bytes(), entity="fleetio")
    target = next(t for t in txs if t.document_number == "INV-1007")
    assert target.customer_email is None
    assert target.po_number is None


def test_entity_type_rules() -> None:
    fleetio_txs, _ = parse_csv(Path("tests/fixtures/sample_ai_llc.csv").read_bytes(), entity="fleetio")
    ai_txs, _ = parse_csv(Path("tests/fixtures/sample_ai_llc.csv").read_bytes(), entity="auto_integrate")
    assert all(t.type in {"Invoice", "Credit Memo"} for t in fleetio_txs)
    assert any(t.type == "Payment" for t in ai_txs)
