from datetime import date

from src.models import (
    CheckResult,
    CheckSeverity,
    Disposition,
    EntityType,
    FormType,
    SellerProtectionStandard,
    ValidationPathway,
    ValidationResult,
)
from src.report import generate_csv_export, generate_portfolio_report
from src.validate import find_duplicates


def _sample_result(cert_id: str, customer: str, state: str, disposition: Disposition, cert_date: date):
    return ValidationResult(
        cert_id=cert_id,
        customer_name=customer,
        state=state,
        form_type=FormType.TX_01_339,
        entity_type=EntityType.LOCAL_GOVERNMENT,
        pathway=ValidationPathway.STANDARD_SELF_COMPLETED,
        seller_protection_standard=SellerProtectionStandard.GOOD_FAITH,
        disposition=disposition,
        confidence_score=85,
        checks=[
            CheckResult(
                check_name="completeness.signature",
                passed=disposition != Disposition.NEEDS_CORRECTION,
                severity=CheckSeverity.HARD_FAIL,
                message="Missing signature" if disposition == Disposition.NEEDS_CORRECTION else "Signature present",
            )
        ],
        expiration_date=cert_date,
    )


def test_find_duplicates_identifies_matching_fingerprint():
    results = [
        {
            "cert_id": "100",
            "customer_name": "Acme, LLC",
            "state": "TX",
            "exemption_category": "Resale",
            "cert_date": "2024-01-01",
        },
        {
            "cert_id": "101",
            "customer_name": "Acme LLC",
            "state": "TX",
            "exemption_category": "Resale",
            "cert_date": "2024-01-01",
        },
    ]
    dupes = find_duplicates(results)
    assert ("100", "101") in dupes


def test_generate_portfolio_report_sections_present():
    results = [
        _sample_result("1", "Alpha", "TX", Disposition.VALIDATED, date.today()),
        _sample_result("2", "Beta", "TX", Disposition.NEEDS_CORRECTION, date.today()),
    ]

    report = generate_portfolio_report(results)
    assert "## 1. EXECUTIVE SUMMARY" in report
    assert "## 9. RECOMMENDATIONS" in report
    assert "DUPLICATE CANDIDATES" in report


def test_generate_csv_export_has_headers_and_rows():
    results = [_sample_result("1", "Alpha", "TX", Disposition.VALIDATED, date.today())]
    csv_data = generate_csv_export(results)
    assert "cert_id,customer_name,state,form_type" in csv_data
    assert "1,Alpha,TX" in csv_data
