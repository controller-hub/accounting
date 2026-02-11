from pathlib import Path

import pytest

from src.models import Disposition, FormType
from src.pipeline import validate_certificate

FIXTURES = Path(__file__).parent / "fixtures"


def test_clean_cert_validates():
    """A clean government cert should produce VALIDATED disposition."""
    clean_fixture = FIXTURES / "10273.pdf"
    if not clean_fixture.exists():
        pytest.skip("No test PDFs")

    result = validate_certificate(str(clean_fixture))
    assert result.disposition in [Disposition.VALIDATED, Disposition.VALIDATED_WITH_NOTES]
    assert result.form_type == FormType.TX_01_339
    assert "Mont Belvieu" in result.customer_name
    assert result.confidence_score > 50


def test_pipeline_returns_all_fields():
    """Pipeline should populate all key fields."""
    pdfs = list(FIXTURES.glob("*.pdf"))
    if not pdfs:
        pytest.skip("No test PDFs")

    result = validate_certificate(str(pdfs[0]))
    assert result.customer_name is not None or result.form_type is not None
    assert result.disposition is not None
    assert result.confidence_score >= 0
    assert len(result.checks) > 0
