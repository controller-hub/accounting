"""
Usage: python scripts/run_single.py path/to/cert.pdf

Extracts text, identifies form type, extracts fields, classifies entity,
and routes to validation pathway.
"""
import os
import sys

# Add project root to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ingest import extract_certificate
from src.parse import parse_certificate
from src.classify import classify_entity, check_entity_form_compatibility, route_to_pathway


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_single.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    result = extract_certificate(pdf_path)
    parsed = parse_certificate(result.raw_text or "")

    parsed.signature_present = result.signature_present
    parsed.extraction_confidence = result.extraction_confidence

    entity_type = classify_entity(parsed)
    state_for_compatibility = (
        (parsed.exemption_states[0] if parsed.exemption_states else None)
        or parsed.purchaser_state
        or ""
    )
    compatible, compatibility_error = check_entity_form_compatibility(
        state_for_compatibility,
        entity_type,
        parsed.form_type_detected,
    )
    pathway = route_to_pathway(parsed.form_type_detected, entity_type, parsed)

    print(f"\n{'=' * 60}")
    print("Certificate Parse + Classification Results")
    print(f"{'=' * 60}")
    print(f"File: {pdf_path}")
    print(f"Form type: {parsed.form_type_detected}")
    print(f"Entity type: {entity_type}")
    print(f"Validation pathway: {pathway}")
    print(f"Compatible: {compatible}")
    if compatibility_error:
        print(f"Compatibility issue: {compatibility_error}")

    print("\n--- Extracted Fields ---")
    for key, value in parsed.model_dump().items():
        if key == "raw_text":
            continue
        print(f"{key}: {value}")

    print(f"\nText length: {len(result.raw_text or '')} chars")
    print("\n--- Extracted Text (first 500 chars) ---")
    print((result.raw_text or "")[:500])
    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    main()
