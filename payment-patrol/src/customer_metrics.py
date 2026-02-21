from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from .models import ARTransaction, CustomerSummary


def build_customer_summaries(transactions: list[ARTransaction]) -> list[CustomerSummary]:
    grouped: dict[str, list[ARTransaction]] = defaultdict(list)
    for tx in transactions:
        grouped[tx.customer_internal_id].append(tx)

    results: list[CustomerSummary] = []
    for customer_id, txs in grouped.items():
        sorted_txs = sorted(txs, key=lambda x: x.invoice_date)
        invoice_count = sum(1 for t in txs if t.type == "Invoice")
        credit_count = sum(1 for t in txs if t.type in {"Credit Memo", "Payment"})
        total_ar = sum((t.signed_amount_remaining for t in txs), Decimal("0"))
        total_past_due = sum((t.signed_amount_remaining for t in txs if t.type == "Invoice" and (t.days_overdue or 0) > 0), Decimal("0"))
        oldest_invoice_date = sorted_txs[0].invoice_date if sorted_txs else date.today()
        oldest_past_due_days = max([(t.days_overdue or 0) for t in txs] or [0])
        mode_terms = Counter([t.effective_terms for t in txs]).most_common(1)[0][0]

        results.append(
            CustomerSummary(
                customer_internal_id=customer_id,
                customer_name=sorted_txs[0].customer_name,
                is_government=any(t.is_government for t in txs),
                invoice_count=invoice_count,
                credit_memo_count=credit_count,
                total_ar=total_ar,
                total_past_due=total_past_due,
                oldest_invoice_date=oldest_invoice_date,
                oldest_past_due_days=oldest_past_due_days,
                effective_terms=mode_terms,
                billing_method=next((t.billing_method for t in txs if t.billing_method), None),
                collection_method=next((t.collection_method for t in txs if t.collection_method), None),
            )
        )

    return sorted(results, key=lambda c: c.total_ar, reverse=True)
