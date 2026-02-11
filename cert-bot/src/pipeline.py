from __future__ import annotations

from .classify import check_entity_form_compatibility, classify_entity, route_to_pathway
from .disposition import build_validation_result, determine_disposition
from .ingest import extract_certificate
from .models import CheckResult, CheckSeverity
from .parse import parse_certificate
from .validate import run_all_checks


def _resolve_state(state: str | None, extracted_state: str | None) -> str:
    return (state or extracted_state or "").strip().upper() or "UNKNOWN"


def validate_certificate(pdf_path: str, state: str = None):
    extracted = extract_certificate(pdf_path)
    parsed = parse_certificate(extracted.raw_text or "")

    # preserve ingest-derived values if parse didn't populate them
    if parsed.signature_present is None:
        parsed.signature_present = extracted.signature_present
    parsed.extraction_confidence = max(parsed.extraction_confidence, extracted.extraction_confidence)

    form_type = parsed.form_type_detected
    entity_type = classify_entity(parsed)
    resolved_state = _resolve_state(state, parsed.purchaser_state)

    compatibility_ok, compatibility_error = check_entity_form_compatibility(resolved_state, entity_type, form_type)
    pathway = route_to_pathway(form_type, entity_type, parsed)
    checks = run_all_checks(parsed, form_type, entity_type, pathway, resolved_state)

    if not compatibility_ok and compatibility_error:
        checks.insert(
            0,
            CheckResult(
                check_name="classify.entity_form_compatibility",
                passed=False,
                severity=CheckSeverity.HARD_FAIL,
                message=compatibility_error,
                recommendation="Resubmit using entity-appropriate form.",
            ),
        )

    disposition, confidence_score = determine_disposition(checks, parsed, form_type, entity_type)
    return build_validation_result(
        fields=parsed,
        form_type=form_type,
        entity_type=entity_type,
        pathway=pathway,
        state=resolved_state,
        checks=checks,
        disposition=disposition,
        confidence_score=confidence_score,
    )

