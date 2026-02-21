from __future__ import annotations

from bisect import bisect_left
from decimal import Decimal

from .models import CustomerSummary


def _dollar_factor(total_ar: Decimal, sorted_values: list[Decimal]) -> float:
    if not sorted_values:
        return 1.0
    idx = bisect_left(sorted_values, total_ar)
    pct = (idx + 1) / len(sorted_values)
    if pct <= 0.25:
        return 1.0
    if pct <= 0.5:
        return 2.0
    if pct <= 0.75:
        return 3.0
    if pct <= 0.95:
        return 4.0
    return 5.0


def _dpd_factor(days: int, terms: int, is_government: bool) -> float:
    if terms == 0:
        bins = [(5, 1), (10, 2), (15, 3), (21, 4)]
        score = 5.0
        for lim, val in bins:
            if days < lim:
                score = float(val)
                break
    else:
        ratio = days / max(terms, 1)
        if ratio < 0.5:
            score = 1.0
        elif ratio < 1.0:
            score = 2.0
        elif ratio < 1.5:
            score = 3.0
        elif ratio < 2.0:
            score = 4.0
        else:
            score = 5.0
    if is_government:
        score = max(1.0, score - 0.5)
    return score


def _collection_factor(method: str | None) -> float:
    if not method:
        return 2.0
    m = method.lower()
    if "auto" in m:
        return 5.0
    if "remittance" in m:
        return 3.0
    return 2.0


def _invoice_factor(count: int) -> float:
    return float(min(max(count, 1), 5))


def _history_factor(days: int) -> float:
    if days <= 0:
        return 1.0
    if days <= 30:
        return 2.0
    if days <= 60:
        return 3.0
    if days <= 90:
        return 4.0
    return 5.0


def tier_for_score(score: float) -> str:
    if score >= 4.0:
        return "Tier 1"
    if score >= 3.0:
        return "Tier 2"
    if score >= 2.0:
        return "Tier 3"
    return "Tier 4"


def _suggested_action(c: CustomerSummary) -> str:
    if (c.billing_method or "").lower().startswith("auto") and c.oldest_past_due_days > 5:
        return f"Auto-pay failed {c.oldest_past_due_days} days ago. Verify payment method on file. If card issue, request updated payment info. Low-effort, high-impact recovery."
    if c.is_government and c.oldest_past_due_days > 0:
        return f"Government account, Net {c.effective_terms} terms. {c.oldest_past_due_days} days past due is within normal range for this segment. Send formal reminder with PO reference. Escalate to CX only if 90+ DPD."
    if c.priority_tier == "Tier 1":
        return f"Commercial account, ${c.total_past_due} past due, {c.oldest_past_due_days} days over terms. Immediate phone outreach recommended."
    if c.priority_tier == "Tier 2":
        return "Commercial account on watch list. Send structured email follow-up and ask about billing disputes or process issues."
    return "Monitor account through standard dunning cadence."


def score_customers(customers: list[CustomerSummary]) -> list[CustomerSummary]:
    values = sorted([c.total_ar for c in customers])
    for c in customers:
        f1 = _dollar_factor(c.total_ar, values)
        f2 = _dpd_factor(c.oldest_past_due_days, c.effective_terms, c.is_government)
        f3 = _collection_factor(c.billing_method or c.collection_method)
        f4 = _invoice_factor(c.invoice_count)
        f5 = _history_factor(c.oldest_past_due_days)

        score = (f1 * 0.25) + (f2 * 0.25) + (f3 * 0.20) + (f4 * 0.15) + (f5 * 0.15)
        if (c.billing_method or "").lower().startswith("auto") and c.oldest_past_due_days > 5:
            score += 1.0

        score = max(0.0, min(5.0, score))
        c.priority_score = round(score, 2)
        c.priority_tier = tier_for_score(c.priority_score)
        c.health_color = "red" if c.priority_score >= 4 else ("yellow" if c.priority_score >= 3 else "green")
        c.suggested_action = _suggested_action(c)
    return sorted(customers, key=lambda x: x.priority_score, reverse=True)
