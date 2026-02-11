import pytest

from src.classify import check_entity_form_compatibility, classify_entity, route_to_pathway
from src.models import EntityType, ExtractedFields, FormType, ValidationPathway
from src.parse import identify_form_type, parse_certificate


def test_identify_texas_form():
    text = "Texas Sales and Use Tax Exemption Certification 01-339 Purchaser Name: Waller Harris ESD 200"
    form_type, conf = identify_form_type(text)
    assert form_type == FormType.TX_01_339
    assert conf > 0.9


def test_identify_mtc_form():
    text = "Uniform Sales & Use Tax Multijurisdictional Exemption Certificate"
    form_type, conf = identify_form_type(text)
    assert form_type == FormType.MTC_UNIFORM


def test_identify_sst_form():
    text = "Streamlined Sales Tax Certificate of Exemption F0003"
    form_type, conf = identify_form_type(text)
    assert form_type == FormType.SST_F0003


def test_identify_md_gov_card():
    text = "Comptroller of Maryland GOV-1 Government Exemption Card"
    form_type, conf = identify_form_type(text)
    assert form_type == FormType.MD_GOV_1


def test_classify_local_government():
    fields = ExtractedFields(
        purchaser_name="Waller Harris ESD 200",
        raw_text="Waller Harris Emergency Services District 200",
    )
    entity = classify_entity(fields)
    assert entity == EntityType.LOCAL_GOVERNMENT


def test_classify_tribal():
    fields = ExtractedFields(
        purchaser_name="Gila River Health Care Corporation",
        raw_text="Gila River Indian Community Tribal Enterprise",
    )
    entity = classify_entity(fields)
    assert entity == EntityType.TRIBAL


def test_classify_nonprofit():
    fields = ExtractedFields(
        purchaser_name="New Life Centers",
        raw_text="New Life Centers 501(c)(3) nonprofit organization",
    )
    entity = classify_entity(fields)
    assert entity == EntityType.NONPROFIT_501C3


def test_pathway_routing_standard():
    fields = ExtractedFields(purchaser_name="Test")
    pathway = route_to_pathway(FormType.TX_01_339, EntityType.LOCAL_GOVERNMENT, fields)
    assert pathway == ValidationPathway.STANDARD_SELF_COMPLETED


def test_pathway_routing_gov_card():
    fields = ExtractedFields(purchaser_name="Test")
    pathway = route_to_pathway(FormType.MD_GOV_1, EntityType.LOCAL_GOVERNMENT, fields)
    assert pathway == ValidationPathway.GOV_CARD_NO_EXPIRY


def test_pathway_routing_federal():
    fields = ExtractedFields(purchaser_name="Test")
    pathway = route_to_pathway(FormType.FEDERAL_GSA_CARD, EntityType.FEDERAL_GOVERNMENT, fields)
    assert pathway == ValidationPathway.FEDERAL_EXEMPTION


def test_ny_incompatibility_st_119_1_for_government():
    compatible, message = check_entity_form_compatibility("NY", EntityType.LOCAL_GOVERNMENT, FormType.NY_ST_119_1)
    assert compatible is False
    assert message is not None and "cannot use ST-119.1" in message


def test_parse_certificate_populates_fields():
    text = (
        "Texas Sales and Use Tax Exemption Certification Form 01-339\n"
        "Name of purchaser: Waller Harris ESD 200\n"
        "Address of purchaser: 123 Main St Houston TX 77001\n"
        "Name of seller: Acme Software\n"
        "Nature of business: Government services\n"
        "Date: 01/15/2025\n"
    )
    parsed = parse_certificate(text)
    assert parsed.form_type_detected == FormType.TX_01_339
    assert parsed.purchaser_name == "Waller Harris ESD 200"
    assert parsed.purchaser_state == "TX"
    assert parsed.exemption_states == ["TX"]

