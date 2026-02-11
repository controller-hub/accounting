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
from src.validate import run_all_checks
from src.models import CheckSeverity, FormType


FORM_STATE_MAP = {
    FormType.TX_01_339: "TX",
    FormType.OH_STEC_B: "OH",
    FormType.OH_DIRECT_PAY: "OH",
    FormType.PA_REV_1220: "PA",
    FormType.IA_31_014A: "IA",
    FormType.MA_ST_2: "MA",
    FormType.MA_ST_5: "MA",
    FormType.TN_GOV: "TN",
    FormType.TN_EXEMPT_ORG: "TN",
    FormType.CT_CERT_119: "CT",
    FormType.CT_CERT_100: "CT",
    FormType.MD_GOV_1: "MD",
    FormType.MD_NONGOV_1: "MD",
    FormType.FL_DR_14: "FL",
    FormType.IL_E99: "IL",
    FormType.IL_STAX_70: "IL",
    FormType.AL_STE_1: "AL",
    FormType.WA_RESELLER: "WA",
    FormType.VT_S_3: "VT",
    FormType.AZ_5000: "AZ",
    FormType.KY_51A126: "KY",
    FormType.NY_ST_120: "NY",
    FormType.NY_ST_121: "NY",
    FormType.NY_ST_119_1: "NY",
    FormType.NY_GOV_LETTER: "NY",
}


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
    state = (
        (parsed.exemption_states[0] if parsed.exemption_states else None)
        or FORM_STATE_MAP.get(parsed.form_type_detected)
        or parsed.purchaser_state
        or ""
    )
    compatible, compatibility_error = check_entity_form_compatibility(
        state,
        entity_type,
        parsed.form_type_detected,
    )
    pathway = route_to_pathway(parsed.form_type_detected, entity_type, parsed)
    checks = run_all_checks(parsed, parsed.form_type_detected, entity_type, pathway, state)

    passed_count = sum(1 for c in checks if c.passed)
    hard_fails = sum(1 for c in checks if (not c.passed and c.severity == CheckSeverity.HARD_FAIL))
    soft_flags = sum(1 for c in checks if (not c.passed and c.severity == CheckSeverity.SOFT_FLAG))

    print(f"\n{'=' * 60}")
    print("Certificate Parse + Classification Results")
    print(f"{'=' * 60}")
    print(f"File: {pdf_path}")
    print(f"Form type: {parsed.form_type_detected}")
    print(f"Entity type: {entity_type}")
    print(f"Validation pathway: {pathway}")
    print(f"State: {state}")
    print(f"Compatible: {compatible}")
    if compatibility_error:
        print(f"Compatibility issue: {compatibility_error}")

    print("\n--- Validation Checks ---")
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"[{status}] {check.check_name} | {check.severity} | {check.message}")

    print("\n--- Validation Summary ---")
    print(f"Passed: {passed_count}")
    print(f"Hard fails: {hard_fails}")
    print(f"Soft flags: {soft_flags}")

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
