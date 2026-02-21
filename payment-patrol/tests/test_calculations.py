from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from src.calculations import compute_portfolio_summary
from src.customer_metrics import build_customer_summaries
from src.ingest import parse_csv
from src.terms_analysis import analyze_terms


def test_aging_buckets_sum_to_total_ar() -> None:
    txs, _ = parse_csv(Path("tests/fixtures/sample_fleetio.csv").read_bytes(), "fleetio")
    customers = build_customer_summaries(txs)
    portfolio = compute_portfolio_summary(txs, customers, Decimal("500000"))
    assert sum(portfolio.aging_buckets.values()) == portfolio.total_ar


def test_dso_reasonable_range() -> None:
    txs, _ = parse_csv(Path("tests/fixtures/sample_fleetio.csv").read_bytes(), "fleetio")
    customers = build_customer_summaries(txs)
    portfolio = compute_portfolio_summary(txs, customers, Decimal("800000"))
    assert 0 <= portfolio.dso_simple <= 365


def test_wado_only_past_due() -> None:
    txs, _ = parse_csv(Path("tests/fixtures/sample_fleetio.csv").read_bytes(), "fleetio")
    customers = build_customer_summaries(txs)
    portfolio = compute_portfolio_summary(txs, customers, Decimal("500000"))
    assert portfolio.wado >= 0


def test_working_cap_impact_positive_when_terms_above_15() -> None:
    txs, _ = parse_csv(Path("tests/fixtures/sample_fleetio.csv").read_bytes(), "fleetio")
    customers = build_customer_summaries(txs)
    portfolio = compute_portfolio_summary(txs, customers, Decimal("500000"))
    terms = analyze_terms(txs, portfolio.total_ar)
    assert terms.weighted_avg_terms > 15
    assert terms.working_capital_impact_vs_net15 > 0
