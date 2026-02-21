from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from .government_heuristic import classify_government_name
from .models import ARTransaction


FLEETIO_HEADERS = [
    "Type", "Document Number", "Name", "Date", "Amount Remaining", "Account", "Status", "Due Date", "Days Overdue",
    "Amount", "Currency", "Internal ID", "Email", "Category", "Fleetio Account", "Terms (Transaction)",
    "Terms (Customer)", "Billing Method", "Collection Method", "PO Number", "Approval Status", "Source", "Posting Period",
    "Subsidiary", "Calculated Terms", "Days Since Invoice", "Days Overdue Calc", "Segment Hint", "Invoice Date ISO", "Due Date ISO",
]


def _none_if_blank(value: str) -> Optional[str]:
    stripped = (value or "").strip()
    return stripped or None


def _parse_date(value: str) -> Optional[date]:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value}")


def _parse_decimal(value: str) -> Decimal:
    return Decimal((value or "0").replace(",", "").strip() or "0")


def _parse_int(value: str) -> Optional[int]:
    value = (value or "").strip()
    return int(value) if value else None


def _extract_terms(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


def _resolve_effective_terms(calculated: Optional[int], tx_terms: Optional[str], customer_terms: Optional[str]) -> int:
    if calculated is not None:
        return calculated
    tx = _extract_terms(tx_terms)
    if tx is not None:
        return tx
    cust = _extract_terms(customer_terms)
    if cust is not None:
        return cust
    return 30


def _normalize_header(value: str | None) -> str:
    return (value or "").replace("\ufeff", "").strip()


def parse_csv(content: bytes, entity: str) -> tuple[list[ARTransaction], Decimal]:
    rows = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    parsed_headers = [_normalize_header(h) for h in (rows.fieldnames or [])]
    expected_headers = [_normalize_header(h) for h in FLEETIO_HEADERS]
    if parsed_headers != expected_headers:
        raise ValueError("CSV headers do not match expected NetSuite export schema")

    transactions: list[ARTransaction] = []
    signed_total = Decimal("0")
    allowed = {"Invoice", "Credit Memo"} if entity == "fleetio" else {"Invoice", "Credit Memo", "Payment"}

    for row in rows:
        tx_type = row["Type"].strip()
        if tx_type not in allowed:
            continue

        amount_remaining = _parse_decimal(row["Amount Remaining"])
        is_credit = tx_type in {"Credit Memo", "Payment"}
        signed = -amount_remaining if is_credit else amount_remaining

        invoice_date = _parse_date(row["Date"])
        if invoice_date is None:
            raise ValueError("Date is required")

        due_date = _parse_date(row["Due Date"]) or _parse_date(row["Due Date ISO"])
        days_overdue = _parse_int(row["Days Overdue"])
        calculated_terms = _parse_int(row["Calculated Terms"])
        effective_terms = _resolve_effective_terms(calculated_terms, _none_if_blank(row["Terms (Transaction)"]), _none_if_blank(row["Terms (Customer)"]))

        heuristic = classify_government_name(row["Name"])
        segment_hint = _none_if_blank(row["Segment Hint"])
        is_government = (segment_hint or "").upper() == "GOV" or heuristic.is_government
        dpd = days_overdue if days_overdue is not None else (_parse_int(row["Days Overdue Calc"]) or 0)

        tx = ARTransaction(
            type=tx_type,
            document_number=row["Document Number"].strip(),
            customer_name=row["Name"].strip(),
            invoice_date=invoice_date,
            amount_remaining=amount_remaining,
            account=row["Account"].strip(),
            status=row["Status"].strip(),
            due_date=due_date,
            days_overdue=days_overdue,
            original_amount=_parse_decimal(row["Amount"]),
            currency=row["Currency"].strip(),
            customer_internal_id=row["Internal ID"].strip(),
            customer_email=_none_if_blank(row["Email"]),
            customer_category=_none_if_blank(row["Category"]),
            fleetio_account=_none_if_blank(row["Fleetio Account"]),
            transaction_terms=_none_if_blank(row["Terms (Transaction)"]),
            customer_default_terms=_none_if_blank(row["Terms (Customer)"]),
            billing_method=_none_if_blank(row["Billing Method"]),
            collection_method=_none_if_blank(row["Collection Method"]),
            po_number=_none_if_blank(row["PO Number"]),
            approval_status=_none_if_blank(row["Approval Status"]),
            source=_none_if_blank(row["Source"]),
            posting_period=_none_if_blank(row["Posting Period"]),
            subsidiary=row["Subsidiary"].strip(),
            calculated_terms=calculated_terms,
            days_since_invoice=_parse_int(row["Days Since Invoice"]),
            days_overdue_calc=_parse_int(row["Days Overdue Calc"]),
            segment_hint=segment_hint,
            invoice_date_iso=_none_if_blank(row["Invoice Date ISO"]),
            due_date_iso=_none_if_blank(row["Due Date ISO"]),
            signed_amount_remaining=signed,
            is_credit=is_credit,
            is_government=is_government,
            effective_terms=effective_terms,
            days_past_terms=max(dpd, 0),
        )
        transactions.append(tx)
        signed_total += signed

    return transactions, signed_total
