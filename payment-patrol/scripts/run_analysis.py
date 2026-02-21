from __future__ import annotations

import argparse
import time
from datetime import date
from decimal import Decimal

from src.anomaly import detect_anomalies
from src.calculations import compute_portfolio_summary
from src.customer_metrics import build_customer_summaries
from src.data_quality import build_data_quality_report
from src.formatters import build_action_blocks, build_cfo_blocks, build_controller_blocks, build_cx_blocks
from src.ingest import parse_csv
from src.intercompany import filter_intercompany
from src.models import AnalysisMeta, AnalysisResult, IntercompanyCustomerSummary, IntercompanySummary
from src.report_builder import build_reports
from src.scoring import score_customers
from src.terms_analysis import analyze_terms


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Payment Patrol analysis pipeline on a CSV file.")
    parser.add_argument("--file", required=True, help="Path to CSV input file")
    parser.add_argument(
        "--entity",
        required=True,
        choices=["fleetio", "auto_integrate"],
        help="Entity key used to parse signed amounts",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start = time.perf_counter()
    parsed_run_date = date.today()

    with open(args.file, "rb") as csv_file:
        content = csv_file.read()

    transactions, signed_total = parse_csv(content, entity=args.entity)
    external_transactions, intercompany_transactions = filter_intercompany(transactions)

    customers = build_customer_summaries(external_transactions)
    customers = score_customers(customers)

    portfolio = compute_portfolio_summary(external_transactions, customers, None)
    terms = analyze_terms(external_transactions, portfolio.total_ar)
    data_quality = build_data_quality_report(external_transactions)
    anomalies = detect_anomalies(portfolio, customers, None)

    intercompany_by_customer: dict[str, Decimal] = {}
    for transaction in intercompany_transactions:
        intercompany_by_customer.setdefault(transaction.customer_name, Decimal("0"))
        intercompany_by_customer[transaction.customer_name] += transaction.signed_amount_remaining

    intercompany = IntercompanySummary(
        intercompany_count=len(intercompany_transactions),
        intercompany_total=sum((t.signed_amount_remaining for t in intercompany_transactions), Decimal("0")),
        intercompany_customers=[
            IntercompanyCustomerSummary(customer_name=name, signed_total=total)
            for name, total in sorted(intercompany_by_customer.items())
        ],
    )
    portfolio.intercompany_ar = intercompany.intercompany_total

    reports = build_reports(portfolio, customers, terms, anomalies, data_quality)
    reports.slack_blocks = {
        "cfo": build_cfo_blocks(reports.cfo_summary, parsed_run_date),
        "controller": build_controller_blocks(reports.controller_detail, parsed_run_date),
        "ar_action": build_action_blocks(reports.ar_action_plan, parsed_run_date),
        "cx": build_cx_blocks(reports.cx_escalation, parsed_run_date),
    }

    meta = AnalysisMeta(
        entity=args.entity,
        run_date=parsed_run_date,
        record_count=len(transactions),
        signed_ar_total=signed_total,
        processing_time_ms=int((time.perf_counter() - start) * 1000),
    )

    result = AnalysisResult(
        meta=meta,
        portfolio=portfolio,
        customers=customers,
        priority_list=customers,
        terms_analysis=terms,
        anomalies=anomalies,
        data_quality=data_quality,
        reports=reports,
        intercompany=intercompany,
    )

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
