from __future__ import annotations

from datetime import datetime

from .models import (
    CheckResult,
    CheckSeverity,
    Disposition,
    EntityType,
    ExtractedFields,
    FormType,
    ResaleTier,
    SellerProtectionStandard,
    ValidationPathway,
    ValidationResult,
)
from .utils import load_config


def determine_disposition(checks: list[CheckResult], fields: ExtractedFields, form_type: FormType, entity_type: EntityType) -> tuple[Disposition, int]:
    hard_fails = [c for c in checks if c.severity == CheckSeverity.HARD_FAIL and not c.passed]
    soft_flags = [c for c in checks if c.severity == CheckSeverity.SOFT_FLAG and not c.passed]
    reason_flags = [c for c in checks if c.severity == CheckSeverity.REASONABLENESS and not c.passed]

    if hard_fails:
        disposition = Disposition.NEEDS_CORRECTION
    elif reason_flags:
        disposition = Disposition.NEEDS_HUMAN_REVIEW
    elif soft_flags:
        disposition = Disposition.VALIDATED_WITH_NOTES
    else:
        disposition = Disposition.VALIDATED

    confidence = 100
    confidence -= 3 * len(soft_flags)
    confidence -= 10 * len(reason_flags)
    if fields.extraction_confidence < 0.8:
        confidence -= 15
    if form_type == FormType.UNKNOWN:
        confidence -= 20
    if entity_type == EntityType.UNKNOWN:
        confidence -= 10

    return disposition, max(0, confidence)


def get_seller_protection(state: str) -> SellerProtectionStandard:
    normalized_state = (state or "").strip().upper()
    state_rules = load_config("state_rules.json")
    sst_members = set(state_rules.get("sst_member_states", []))

    if normalized_state in {"FEDERAL", "US", "USA"}:
        return SellerProtectionStandard.FEDERAL_SUPREMACY
    if normalized_state in sst_members:
        return SellerProtectionStandard.SST_FOUR_CORNERS
    return SellerProtectionStandard.GOOD_FAITH


def _find_resale_tier(checks: list[CheckResult]) -> ResaleTier | None:
    for check in checks:
        if check.check_name != "reasonableness.resale_tier":
            continue
        msg = check.message.upper()
        if "TIER=STRONG" in msg:
            return ResaleTier.STRONG
        if "TIER=PLAUSIBLE" in msg:
            return ResaleTier.PLAUSIBLE
        if "TIER=WEAK" in msg:
            return ResaleTier.WEAK
        if "TIER=IMPLAUSIBLE" in msg:
            return ResaleTier.IMPLAUSIBLE
    return None


def build_validation_result(
    fields: ExtractedFields,
    form_type: FormType,
    entity_type: EntityType,
    pathway: ValidationPathway,
    state: str,
    checks: list[CheckResult],
    disposition: Disposition,
    confidence_score: int,
) -> ValidationResult:
    hard_fails = [c for c in checks if c.severity == CheckSeverity.HARD_FAIL and not c.passed]
    soft_flags = [c for c in checks if c.severity == CheckSeverity.SOFT_FLAG and not c.passed]
    reason_flags = [c for c in checks if c.severity == CheckSeverity.REASONABLENESS and not c.passed]

    correction_items = [c.message for c in hard_fails]
    correction_email_needed = len(hard_fails) > 0
    human_review_needed = len(reason_flags) > 0

    expiration_rule = None
    renewal_action = None
    state_rules = load_config("state_rules.json")
    expiration_rules = state_rules.get("expiration_rules", {})
    if state in expiration_rules:
        expiration_rule = expiration_rules[state].get("rule")
        renewal_action = expiration_rules[state].get("note")
    elif "DEFAULT" in expiration_rules:
        expiration_rule = expiration_rules["DEFAULT"].get("rule")
        renewal_action = expiration_rules["DEFAULT"].get("note")

    return ValidationResult(
        customer_name=fields.purchaser_name or "Unknown Customer",
        state=state,
        form_type=form_type,
        entity_type=entity_type,
        pathway=pathway,
        exemption_category=fields.exemption_category,
        seller_protection_standard=get_seller_protection(state),
        disposition=disposition,
        confidence_score=confidence_score,
        checks=checks,
        hard_fails=hard_fails,
        soft_flags=soft_flags,
        reasonableness_flags=reason_flags,
        expiration_date=fields.expiration_date,
        expiration_rule=expiration_rule,
        renewal_action=renewal_action,
        resale_tier=_find_resale_tier(checks),
        validated_at=datetime.utcnow(),
        extraction_confidence=fields.extraction_confidence,
        correction_email_needed=correction_email_needed,
        correction_items=correction_items,
        human_review_needed=human_review_needed,
        human_review_reason="; ".join([c.message for c in reason_flags]) if human_review_needed else None,
    )
