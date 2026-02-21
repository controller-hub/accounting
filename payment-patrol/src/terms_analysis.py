from __future__ import annotations

from decimal import Decimal

from .models import ARTransaction, TermsBucket, TermsDistribution


STANDARD = [0, 15, 30, 45, 60]


def analyze_terms(transactions: list[ARTransaction], total_ar: Decimal) -> TermsDistribution:
    bucket_data: dict[str, TermsBucket] = {str(k): TermsBucket(count=0, ar_amount=Decimal("0"), pct_of_ar=0.0) for k in STANDARD}
    weighted_total = Decimal("0")
    amount_total = Decimal("0")

    for tx in transactions:
        term = tx.effective_terms if tx.effective_terms in STANDARD else 30
        key = str(term)
        b = bucket_data[key]
        b.count += 1
        b.ar_amount += tx.signed_amount_remaining
        weighted_total += Decimal(term) * max(tx.signed_amount_remaining, Decimal("0"))
        amount_total += max(tx.signed_amount_remaining, Decimal("0"))

    for key, b in bucket_data.items():
        b.pct_of_ar = float((b.ar_amount / total_ar * Decimal("100")) if total_ar else Decimal("0"))

    weighted_avg = float((weighted_total / amount_total) if amount_total else Decimal("30"))
    impact = (Decimal(str(weighted_avg)) - Decimal("15")) * (total_ar / Decimal("365")) * Decimal("0.05")

    return TermsDistribution(by_bucket=bucket_data, weighted_avg_terms=weighted_avg, working_capital_impact_vs_net15=impact)
