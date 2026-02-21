from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class GovernmentHeuristicResult(BaseModel):
    is_government: bool
    confidence: str
    matched_pattern: Optional[str] = None


class ARTransaction(BaseModel):
    type: str
    document_number: str
    customer_name: str
    invoice_date: date
    amount_remaining: Decimal
    account: str
    status: str
    due_date: Optional[date] = None
    days_overdue: Optional[int] = None
    original_amount: Decimal
    currency: str
    customer_internal_id: str
    customer_email: Optional[str] = None
    customer_category: Optional[str] = None
    fleetio_account: Optional[str] = None
    transaction_terms: Optional[str] = None
    customer_default_terms: Optional[str] = None
    billing_method: Optional[str] = None
    collection_method: Optional[str] = None
    po_number: Optional[str] = None
    approval_status: Optional[str] = None
    source: Optional[str] = None
    posting_period: Optional[str] = None
    subsidiary: str
    calculated_terms: Optional[int] = None
    days_since_invoice: Optional[int] = None
    days_overdue_calc: Optional[int] = None
    segment_hint: Optional[str] = None
    invoice_date_iso: Optional[str] = None
    due_date_iso: Optional[str] = None

    signed_amount_remaining: Decimal
    is_credit: bool
    is_government: bool
    effective_terms: int
    days_past_terms: int


class CustomerSummary(BaseModel):
    customer_internal_id: str
    customer_name: str
    is_government: bool
    invoice_count: int
    credit_memo_count: int
    total_ar: Decimal
    total_past_due: Decimal
    oldest_invoice_date: date
    oldest_past_due_days: int
    effective_terms: int
    billing_method: Optional[str] = None
    collection_method: Optional[str] = None
    priority_score: float = 0.0
    priority_tier: str = "Tier 4"
    health_color: str = "green"
    suggested_action: str = ""
    data_quality_flags: list[str] = Field(default_factory=list)


class PortfolioSummary(BaseModel):
    total_ar: Decimal
    total_current: Decimal
    total_past_due: Decimal
    pct_past_due: float
    aging_buckets: dict[str, Decimal]
    aging_buckets_pct: dict[str, float]
    dso_simple: float
    dso_countback: float
    wado: float
    cei: float
    health_scorecard: dict[str, str]
    customer_count: int
    government_ar: Decimal
    commercial_ar: Decimal
    intercompany_ar: Decimal
    collections_forecast_30d: Decimal


class TermsBucket(BaseModel):
    count: int
    ar_amount: Decimal
    pct_of_ar: float


class TermsDistribution(BaseModel):
    by_bucket: dict[str, TermsBucket]
    weighted_avg_terms: float
    working_capital_impact_vs_net15: Decimal


class Anomaly(BaseModel):
    type: str
    severity: str
    message: str
    customer_name: Optional[str] = None
    amount: Optional[Decimal] = None


class DataQualityReport(BaseModel):
    unapplied_credits: list[dict[str, Any]] = Field(default_factory=list)
    missing_billing_method: list[str] = Field(default_factory=list)
    gov_no_po: list[dict[str, str]] = Field(default_factory=list)
    terms_anomalies: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_names: list[dict[str, Any]] = Field(default_factory=list)


class AnalysisMeta(BaseModel):
    entity: str
    run_date: date
    record_count: int
    signed_ar_total: Decimal
    processing_time_ms: int


class AnalysisReports(BaseModel):
    cfo_summary: dict[str, Any]
    controller_detail: dict[str, Any]
    ar_action_plan: dict[str, Any]
    cx_escalation: list[dict[str, Any]]
    slack_blocks: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    meta: AnalysisMeta
    portfolio: PortfolioSummary
    customers: list[CustomerSummary]
    priority_list: list[CustomerSummary]
    terms_analysis: TermsDistribution
    anomalies: list[Anomaly]
    data_quality: DataQualityReport
    reports: AnalysisReports
