from __future__ import annotations

import json
import time
from datetime import date
from decimal import Decimal

from fastapi import FastAPI, File, Form, UploadFile

from .anomaly import detect_anomalies
from .calculations import compute_portfolio_summary
from .customer_metrics import build_customer_summaries
from .data_quality import build_data_quality_report
from .formatters import build_action_blocks, build_cfo_blocks, build_controller_blocks, build_cx_blocks
from .ingest import parse_csv
from .models import AnalysisMeta, AnalysisResult
from .report_builder import build_reports
from .scoring import score_customers
from .terms_analysis import analyze_terms

app = FastAPI(title="Payment Patrol", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.post("/analyze", response_model=AnalysisResult)
async def analyze(
    file: UploadFile = File(...),
    entity: str = Form(...),
    run_date: str | None = Form(default=None),
    prior_snapshot_json: str | None = Form(default=None),
    total_invoiced_amount: float | None = Form(default=None),
) -> AnalysisResult:
    start = time.perf_counter()
    parsed_run_date = date.fromisoformat(run_date) if run_date else date.today()

    content = await file.read()
    transactions, signed_total = parse_csv(content, entity=entity)
    customers = build_customer_summaries(transactions)
    customers = score_customers(customers)

    portfolio = compute_portfolio_summary(
        transactions,
        customers,
        Decimal(str(total_invoiced_amount)) if total_invoiced_amount is not None else None,
    )
    terms = analyze_terms(transactions, portfolio.total_ar)
    data_quality = build_data_quality_report(transactions)
    anomalies = detect_anomalies(portfolio, customers, prior_snapshot_json)

    reports = build_reports(portfolio, customers, terms, anomalies, data_quality)
    reports.slack_blocks = {
        "cfo": build_cfo_blocks(reports.cfo_summary, parsed_run_date),
        "controller": build_controller_blocks(reports.controller_detail, parsed_run_date),
        "ar_action": build_action_blocks(reports.ar_action_plan, parsed_run_date),
        "cx": build_cx_blocks(reports.cx_escalation, parsed_run_date),
    }

    meta = AnalysisMeta(
        entity=entity,
        run_date=parsed_run_date,
        record_count=len(transactions),
        signed_ar_total=signed_total,
        processing_time_ms=int((time.perf_counter() - start) * 1000),
    )

    return AnalysisResult(
        meta=meta,
        portfolio=portfolio,
        customers=customers,
        priority_list=customers,
        terms_analysis=terms,
        anomalies=anomalies,
        data_quality=data_quality,
        reports=reports,
    )
