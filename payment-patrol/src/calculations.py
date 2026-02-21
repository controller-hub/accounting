from __future__ import annotations

from decimal import Decimal

from .models import ARTransaction, CustomerSummary, PortfolioSummary


BUCKET_ORDER = ["current", "1_30", "31_60", "61_90", "91_120", "over_120"]
FORECAST_RATES = {
    "current": Decimal("0.95"),
    "1_30": Decimal("0.80"),
    "31_60": Decimal("0.60"),
    "61_90": Decimal("0.40"),
    "91_120": Decimal("0.20"),
    "over_120": Decimal("0.05"),
}


def bucket_for_days(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "1_30"
    if days_overdue <= 60:
        return "31_60"
    if days_overdue <= 90:
        return "61_90"
    if days_overdue <= 120:
        return "91_120"
    return "over_120"


def compute_portfolio_summary(transactions: list[ARTransaction], customers: list[CustomerSummary], total_invoiced_amount: Decimal | None) -> PortfolioSummary:
    aging = {k: Decimal("0") for k in BUCKET_ORDER}
    for tx in transactions:
        aging[bucket_for_days(tx.days_overdue or 0)] += tx.signed_amount_remaining

    total_ar = sum(aging.values(), Decimal("0"))
    total_current = aging["current"]
    total_past_due = total_ar - total_current
    pct_past_due = float((total_past_due / total_ar * Decimal("100")) if total_ar else Decimal("0"))
    aging_pct = {k: float((v / total_ar * Decimal("100")) if total_ar else Decimal("0")) for k, v in aging.items()}

    invoiced = total_invoiced_amount or Decimal("1")
    dso_simple = float((total_ar / invoiced) * Decimal("90")) if total_invoiced_amount and total_invoiced_amount > 0 else 0.0
    dso_countback = min(365.0, max(0.0, float(sum(abs(v) for v in aging.values()) / max(invoiced, Decimal("1")) * Decimal("90"))))

    past_due = [t for t in transactions if (t.days_overdue or 0) > 0 and t.signed_amount_remaining > 0]
    past_due_total = sum((t.signed_amount_remaining for t in past_due), Decimal("0"))
    wado = float(sum((Decimal(t.days_overdue or 0) * t.signed_amount_remaining for t in past_due), Decimal("0")) / past_due_total) if past_due_total else 0.0

    cei = float(((invoiced - max(total_past_due, Decimal("0"))) / invoiced) * Decimal("100")) if total_invoiced_amount and invoiced > 0 else 0.0

    government_ar = sum((c.total_ar for c in customers if c.is_government), Decimal("0"))
    commercial_ar = sum((c.total_ar for c in customers if not c.is_government), Decimal("0"))
    intercompany = sum((t.signed_amount_remaining for t in transactions if "fleetio" in t.customer_name.lower() and "auto integrate" in t.subsidiary.lower()), Decimal("0"))

    forecast = sum((aging[k] * FORECAST_RATES[k] for k in BUCKET_ORDER), Decimal("0"))

    health = {
        "dso_health": "green" if dso_simple <= 45 else ("yellow" if dso_simple <= 60 else "red"),
        "cei_health": "green" if cei >= 90 else ("yellow" if cei >= 80 else "red"),
    }
    health["overall_health"] = "red" if "red" in health.values() else ("yellow" if "yellow" in health.values() else "green")

    return PortfolioSummary(
        total_ar=total_ar,
        total_current=total_current,
        total_past_due=total_past_due,
        pct_past_due=pct_past_due,
        aging_buckets=aging,
        aging_buckets_pct=aging_pct,
        dso_simple=dso_simple,
        dso_countback=dso_countback,
        wado=wado,
        cei=cei,
        health_scorecard=health,
        customer_count=len(customers),
        government_ar=government_ar,
        commercial_ar=commercial_ar,
        intercompany_ar=intercompany,
        collections_forecast_30d=forecast,
    )
