from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from src.customer_metrics import build_customer_summaries
from src.ingest import parse_csv
from src.scoring import score_customers, tier_for_score


def test_score_range() -> None:
    txs, _ = parse_csv(Path("tests/fixtures/sample_fleetio.csv").read_bytes(), "fleetio")
    customers = score_customers(build_customer_summaries(txs))
    assert all(0.0 <= c.priority_score <= 5.0 for c in customers)


def test_auto_pay_failure_boost() -> None:
    txs, _ = parse_csv(Path("tests/fixtures/sample_fleetio.csv").read_bytes(), "fleetio")
    customers = score_customers(build_customer_summaries(txs))
    auto = next(c for c in customers if c.customer_name == "Rapid Logistics")
    assert auto.priority_score >= 3.0


def test_government_adjustment_present() -> None:
    txs, _ = parse_csv(Path("tests/fixtures/sample_fleetio.csv").read_bytes(), "fleetio")
    customers = score_customers(build_customer_summaries(txs))
    gov = next(c for c in customers if c.customer_name == "City of Mobile")
    comm = next(c for c in customers if c.customer_name == "Acme Construction")
    assert gov.is_government is True
    assert gov.priority_score <= 5.0
    assert comm.priority_score >= gov.priority_score - 1.0


def test_tier_assignment() -> None:
    assert tier_for_score(4.1) == "Tier 1"
    assert tier_for_score(3.5) == "Tier 2"
    assert tier_for_score(2.2) == "Tier 3"
    assert tier_for_score(1.4) == "Tier 4"


def test_higher_risk_higher_score() -> None:
    txs, _ = parse_csv(Path("tests/fixtures/sample_fleetio.csv").read_bytes(), "fleetio")
    customers = score_customers(build_customer_summaries(txs))
    risky = next(c for c in customers if c.customer_name == "Acme Construction")
    low = next(c for c in customers if c.customer_name == "Nimble Auto")
    assert risky.priority_score > low.priority_score
