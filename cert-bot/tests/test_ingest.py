from pathlib import Path

import pytest

from src.ingest import detect_signature, extract_certificate, extract_text_from_pdf

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_text_returns_content():
    """Any test cert PDF should return non-empty text."""
    pdfs = list(FIXTURES.glob("*.pdf"))
    if not pdfs:
        pytest.skip("No test PDFs found in fixtures/")

    for pdf in pdfs[:3]:  # Test first 3
        result = extract_text_from_pdf(str(pdf))
        assert len(result["text"]) > 50, f"Too little text from {pdf.name}"
        assert result["method"] in ("pdfplumber", "ocr")


def test_extract_certificate_returns_model():
    """extract_certificate should return a valid ExtractedFields."""
    pdfs = list(FIXTURES.glob("*.pdf"))
    if not pdfs:
        pytest.skip("No test PDFs")

    result = extract_certificate(str(pdfs[0]))
    assert result.raw_text is not None
    assert result.extraction_confidence > 0
    assert result.signature_present is not None


def test_detect_signature_on_fixture_if_present():
    """Signature detector should return bool on available fixture PDFs."""
    pdfs = list(FIXTURES.glob("*.pdf"))
    if not pdfs:
        pytest.skip("No test PDFs")

    signature = detect_signature(str(pdfs[0]))
    assert isinstance(signature, bool)


def test_load_config():
    """Config files should load correctly."""
    from src.utils import load_config

    state_rules = load_config("state_rules.json")
    assert "taxability" in state_rules
    assert "TX" in state_rules["taxability"]

    mtc = load_config("mtc_restrictions.json")
    assert "resale_only_states" in mtc

    forms = load_config("form_templates.json")
    assert "forms" in forms
    assert "TX_01_339" in forms["forms"]

    reason = load_config("reasonableness_rules.json")
    assert "exemption_validity_for_saas" in reason
