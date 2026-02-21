from __future__ import annotations

from collections import defaultdict

from .models import ARTransaction, DataQualityReport


def build_data_quality_report(transactions: list[ARTransaction]) -> DataQualityReport:
    report = DataQualityReport()
    customer_has_open_invoice = defaultdict(bool)
    name_to_ids = defaultdict(set)

    for tx in transactions:
        if tx.type == "Invoice" and tx.signed_amount_remaining > 0:
            customer_has_open_invoice[tx.customer_internal_id] = True
        name_to_ids[tx.customer_name].add(tx.customer_internal_id)

    for tx in transactions:
        if tx.type == "Credit Memo" and tx.amount_remaining != 0 and not customer_has_open_invoice[tx.customer_internal_id]:
            report.unapplied_credits.append({"customer_name": tx.customer_name, "credit_amount": str(tx.amount_remaining)})
        if tx.is_government and not tx.po_number:
            report.gov_no_po.append({"customer_name": tx.customer_name, "document_number": tx.document_number})
        if not tx.billing_method and not tx.collection_method:
            if tx.customer_name not in report.missing_billing_method:
                report.missing_billing_method.append(tx.customer_name)
        if tx.calculated_terms is not None and tx.calculated_terms not in [0, 15, 30, 45, 60]:
            report.terms_anomalies.append({"customer_name": tx.customer_name, "calculated_terms": tx.calculated_terms})

    for name, ids in name_to_ids.items():
        if len(ids) > 1:
            report.duplicate_names.append({"customer_name": name, "internal_ids": sorted(ids)})

    return report
