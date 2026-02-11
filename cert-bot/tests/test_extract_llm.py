from datetime import date
from types import SimpleNamespace
import sys

from src.extract_llm import extract_fields_via_llm
from src.models import EntityType, FormType
from src.parse import map_llm_entity_type, map_llm_form_type


def test_extract_fields_via_llm_maps_response(monkeypatch):
    payload = (
        '{"customer_name":"City of Austin","customer_address":"123 Main St, Austin, TX 78701",'
        '"state":"TX","form_type":"TX 01-339","entity_type":"local_government",'
        '"exemption_reason":"government entity","signed_date":"2025-01-15",'
        '"expiration_date":null,"tax_id":"12-3456789","seller_name":"Rarestep",'
        '"has_signature":true,"checked_boxes":["Government"],"confidence":0.91,'
        '"notes":"Readable"}'
    )

    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["model"] == "gpt-4o"
            assert kwargs["response_format"] == {"type": "json_object"}
            assert kwargs["temperature"] == 0
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
            )

    class FakeOpenAI:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("src.extract_llm._load_openai_api_key", lambda: "test-key")
    monkeypatch.setattr("src.extract_llm._pdf_to_base64_images", lambda *_args, **_kwargs: ["abc123"])
    fake_openai_module = SimpleNamespace(OpenAI=FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_openai_module)

    fields = extract_fields_via_llm("dummy.pdf")

    assert fields.purchaser_name == "City of Austin"
    assert fields.purchaser_address == "123 Main St, Austin, TX 78701"
    assert fields.purchaser_state == "TX"
    assert fields.form_type_detected == FormType.TX_01_339
    assert fields.exemption_reason == "government entity"
    assert fields.cert_date == date(2025, 1, 15)
    assert fields.expiration_date is None
    assert fields.purchaser_tax_id == "12-3456789"
    assert fields.seller_name == "Rarestep"
    assert fields.signature_present is True
    assert fields.extraction_confidence == 0.91


def test_map_llm_form_type_variants():
    cases = {
        "TX 01-339": FormType.TX_01_339,
        "PA REV-1220": FormType.PA_REV_1220,
        "NY ST-121": FormType.NY_ST_121,
        "FL DR-14": FormType.FL_DR_14,
        "OH STEC-B": FormType.OH_STEC_B,
        "MTC Uniform": FormType.MTC_UNIFORM,
        "NY Government Letter": FormType.NY_GOV_LETTER,
        "Federal Agency Letter": FormType.FEDERAL_LETTERHEAD,
        "SST F0003": FormType.SST_F0003,
        "Unrecognized Form": FormType.UNKNOWN,
    }

    for value, expected in cases.items():
        assert map_llm_form_type(value) == expected


def test_map_llm_entity_type_variants():
    cases = {
        "federal_government": EntityType.FEDERAL_GOVERNMENT,
        "state_government": EntityType.STATE_GOVERNMENT,
        "local_government": EntityType.LOCAL_GOVERNMENT,
        "tribal": EntityType.TRIBAL,
        "nonprofit_501c3": EntityType.NONPROFIT_501C3,
        "nonprofit_other": EntityType.EXEMPT_ORG_OTHER,
        "educational": EntityType.EDUCATIONAL,
        "religious": EntityType.RELIGIOUS,
        "for_profit": EntityType.FOR_PROFIT,
        "unknown": EntityType.UNKNOWN,
        "anything_else": EntityType.UNKNOWN,
    }

    for value, expected in cases.items():
        assert map_llm_entity_type(value) == expected
