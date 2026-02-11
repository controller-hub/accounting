from __future__ import annotations

import base64
import json
import logging
import os
from datetime import date
from io import BytesIO
from pathlib import Path

from .ingest import extract_text_from_pdf
from .models import ExtractedFields
from .parse import extract_exemption_states, extract_fields_regex, identify_form_type, map_llm_form_type
from .utils import normalize_state, parse_date

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a tax compliance document analyst. Extract the following fields from this US state tax exemption certificate image. Return a JSON object with exactly these fields:

{
  \"customer_name\": \"The purchaser/buyer organization name (not the seller)\",
  \"customer_address\": \"Full address of the purchaser including street, city, state, zip\",
  \"state\": \"Two-letter US state code this certificate covers (the jurisdiction, not the purchaser's state)\",
  \"form_type\": \"The official form number/name (e.g., 'TX 01-339', 'PA REV-1220', 'NY ST-121', 'MTC Uniform', 'FL DR-14', 'OH STEC-B')\",
  \"entity_type\": \"One of: federal_government, state_government, local_government, tribal, nonprofit_501c3, nonprofit_other, educational, religious, for_profit, unknown\",
  \"exemption_reason\": \"The stated reason for exemption (e.g., 'government entity', 'resale', 'agricultural', 'manufacturing', 'nonprofit - charitable')\",
  \"signed_date\": \"Date signed in YYYY-MM-DD format, or null if not found\",
  \"expiration_date\": \"Expiration date in YYYY-MM-DD format, or null if none/perpetual\",
  \"tax_id\": \"Tax exempt number, EIN, or certificate number if present, or null\",
  \"seller_name\": \"The seller/vendor name on the certificate, or null if not found\",
  \"has_signature\": true/false,
  \"checked_boxes\": [\"List of all exemption boxes/categories that are checked\"],
  \"confidence\": 0.0-1.0 overall confidence in extraction quality,
  \"notes\": \"Any issues noticed: illegible sections, handwritten fields, missing required elements\"
}

Important rules:
- The PURCHASER is the customer claiming exemption. The SELLER is typically Fleetio/Rarestep.
- For state: identify the JURISDICTION the cert covers, not where the purchaser is located. A Texas form covers TX even if the purchaser is in another state.
- For government letters (not standard forms): set form_type to \"[State] Government Letter\" (e.g., \"NY Government Letter\")
- For federal agency letters: set form_type to \"Federal Agency Letter\"
- If a field is truly not present or illegible, use null rather than guessing"""


def _load_openai_api_key() -> str | None:
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key

    config_path = Path(__file__).parent.parent / "config" / "openai_config.json"
    if not config_path.exists():
        return None

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload.get("api_key")


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return parse_date(value)


def _pdf_to_base64_images(pdf_path: str, max_pages: int = 2) -> list[str]:
    from pdf2image import convert_from_path

    images = convert_from_path(pdf_path, first_page=1, last_page=max_pages)
    encoded: list[str] = []
    for image in images:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        encoded.append(base64.b64encode(buffer.getvalue()).decode("utf-8"))
    return encoded


def _fallback_regex_from_pdf(pdf_path: str) -> ExtractedFields:
    extraction = extract_text_from_pdf(pdf_path)
    raw_text = extraction.get("text", "")
    form_type, confidence = identify_form_type(raw_text)
    fields = extract_fields_regex(raw_text, form_type)
    fields.exemption_states = extract_exemption_states(raw_text, form_type)
    fields.form_type_detected = form_type
    fields.raw_text = raw_text
    # Keep fallback confidence below LLM acceptance threshold so caller can route to regex path.
    fields.extraction_confidence = min(max(0.0, confidence), 0.49)
    return fields


def extract_fields_via_llm(pdf_path: str) -> ExtractedFields:
    """Extract certificate fields via GPT-4o vision, with regex fallback on API failure."""
    try:
        api_key = _load_openai_api_key()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

        from openai import OpenAI

        images = _pdf_to_base64_images(pdf_path, max_pages=2)
        if not images:
            raise RuntimeError("No images rendered from PDF")

        client = OpenAI(api_key=api_key)
        content: list[dict] = [{"type": "text", "text": EXTRACTION_PROMPT}]
        for image_data in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                }
            )

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        message_content = response.choices[0].message.content or "{}"
        payload = json.loads(message_content)

        form_type = map_llm_form_type(payload.get("form_type", ""))
        jurisdiction_state = normalize_state(payload.get("state") or "")

        fields = ExtractedFields(
            purchaser_name=payload.get("customer_name"),
            purchaser_address=payload.get("customer_address"),
            purchaser_state=jurisdiction_state or None,
            purchaser_tax_id=payload.get("tax_id"),
            purchaser_fein=payload.get("tax_id"),
            permit_number=payload.get("tax_id"),
            account_number=payload.get("tax_id"),
            seller_name=payload.get("seller_name"),
            exemption_reason=payload.get("exemption_reason"),
            signature_present=payload.get("has_signature"),
            cert_date=_parse_iso_date(payload.get("signed_date")),
            expiration_date=_parse_iso_date(payload.get("expiration_date")),
            form_type_detected=form_type,
            exemption_states=[jurisdiction_state] if jurisdiction_state else [],
            raw_text=payload.get("notes"),
            extraction_confidence=float(payload.get("confidence") or 0.0),
        )
        return fields
    except Exception as exc:
        logger.warning("LLM extraction failed, falling back to regex parsing: %s", exc)
        return _fallback_regex_from_pdf(pdf_path)
