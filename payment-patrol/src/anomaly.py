from __future__ import annotations

import json
from decimal import Decimal

from .models import Anomaly, CustomerSummary, PortfolioSummary


def detect_anomalies(
    portfolio: PortfolioSummary,
    customers: list[CustomerSummary],
    prior_snapshot_json: str | None,
) -> list[Anomaly]:
    if not prior_snapshot_json:
        return []

    prior = json.loads(prior_snapshot_json)
    anomalies: list[Anomaly] = []

    prior_dso = float(prior.get("dso_simple", 0))
    if portfolio.dso_simple - prior_dso > 5:
        anomalies.append(Anomaly(type="dso_spike", severity="yellow", message="DSO increased by more than 5 days week-over-week."))

    prior_past_due_pct = float(prior.get("pct_past_due", 0))
    if portfolio.pct_past_due - prior_past_due_pct > 3:
        anomalies.append(Anomaly(type="past_due_surge", severity="red", message="Past-due percentage increased by more than 3 points week-over-week."))

    total_ar = portfolio.total_ar or Decimal("1")
    for c in customers:
        if c.total_ar / total_ar > Decimal("0.05"):
            anomalies.append(Anomaly(type="concentration_risk", severity="yellow", message=f"{c.customer_name} exceeds 5% of total AR.", customer_name=c.customer_name, amount=c.total_ar))

    return anomalies
