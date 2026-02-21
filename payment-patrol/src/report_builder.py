from __future__ import annotations

from decimal import Decimal

from .models import AnalysisReports, Anomaly, CustomerSummary, DataQualityReport, PortfolioSummary, TermsDistribution


def build_reports(
    portfolio: PortfolioSummary,
    customers: list[CustomerSummary],
    terms: TermsDistribution,
    anomalies: list[Anomaly],
    data_quality: DataQualityReport,
) -> AnalysisReports:
    cx_escalation_eligible = lambda c: (
        abs(c.total_ar) >= Decimal("5000")
        and (
            (not c.is_government and c.oldest_past_due_days >= 45)
            or ((c.billing_method or "").lower().startswith("auto") and c.oldest_past_due_days >= 21)
            or (c.is_government and c.oldest_past_due_days >= 90)
        )
    )

    top10 = [{"customer_name": c.customer_name, "amount": str(c.total_past_due), "days": c.oldest_past_due_days} for c in sorted(customers, key=lambda x: x.total_past_due, reverse=True)[:10]]
    red_anomalies = [a.model_dump(mode="json") for a in anomalies if a.severity == "red"]

    cfo = {
        "health_scorecard": portfolio.health_scorecard,
        "total_ar": str(portfolio.total_ar),
        "pct_past_due": portfolio.pct_past_due,
        "dso": portfolio.dso_simple,
        "cei": portfolio.cei,
        "top_10_past_due": top10,
        "red_anomalies": red_anomalies,
        "weighted_avg_terms": terms.weighted_avg_terms,
        "working_capital_impact": str(terms.working_capital_impact_vs_net15),
        "collections_forecast_30d": str(portfolio.collections_forecast_30d),
    }

    controller = {
        **cfo,
        "aging_buckets": {k: str(v) for k, v in portfolio.aging_buckets.items()},
        "terms_distribution": terms.model_dump(mode="json"),
        "all_anomalies": [a.model_dump(mode="json") for a in anomalies],
        "data_quality": data_quality.model_dump(mode="json"),
        "concentration_top_10": top10,
        "segment_breakdown": {"government_ar": str(portfolio.government_ar), "commercial_ar": str(portfolio.commercial_ar)},
        "intercompany_ar": str(portfolio.intercompany_ar),
    }

    action_sections = {
        "auto_pay_failures": [c.model_dump(mode="json") for c in customers if (c.billing_method or "").lower().startswith("auto") and c.oldest_past_due_days > 5],
        "tier_1_remittance": [c.model_dump(mode="json") for c in customers if c.priority_tier == "Tier 1" and (c.billing_method or "").lower() == "remittance"],
        "tier_2": [c.model_dump(mode="json") for c in customers if c.priority_tier == "Tier 2"],
        "cx_escalation_candidates": [c.model_dump(mode="json") for c in customers if cx_escalation_eligible(c)],
        "data_quality_actions": data_quality.model_dump(mode="json"),
    }

    cx = [
        {
            "customer_name": c.customer_name,
            "ar_amount": str(c.total_ar),
            "days_past_due": c.oldest_past_due_days,
            "last_known_activity": "N/A",
            "context_note": c.suggested_action,
        }
        for c in customers
        if cx_escalation_eligible(c)
    ]

    return AnalysisReports(cfo_summary=cfo, controller_detail=controller, ar_action_plan=action_sections, cx_escalation=cx, slack_blocks={})
