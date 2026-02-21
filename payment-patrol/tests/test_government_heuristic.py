from __future__ import annotations

from src.government_heuristic import classify_government_name


def test_city_of_mobile_high() -> None:
    result = classify_government_name("City of Mobile")
    assert result.is_government is True
    assert result.confidence == "high"


def test_school_district_high() -> None:
    result = classify_government_name("Baldwin County School District")
    assert result.is_government is True
    assert result.confidence == "high"


def test_acme_none() -> None:
    result = classify_government_name("Acme Corp")
    assert result.is_government is False
    assert result.confidence == "none"


def test_transit_authority_high() -> None:
    result = classify_government_name("Transit Authority")
    assert result.is_government is True
    assert result.confidence == "high"


def test_case_insensitive() -> None:
    result = classify_government_name("city OF mobile")
    assert result.is_government is True


def test_general_services_administration_high() -> None:
    result = classify_government_name("General Services Administration")
    assert result.is_government is True
    assert result.confidence == "high"
