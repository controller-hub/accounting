from __future__ import annotations

import re
from datetime import date

from .models import (
    CheckResult,
    CheckSeverity,
    EntityType,
    ExemptionCategory,
    ExtractedFields,
    FormType,
    ValidationPathway,
)
from .utils import load_config


_FORM_STATE_MAP: dict[FormType, str] = {
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

_FEDERAL_FORMS = {
    FormType.FEDERAL_SF_1094,
    FormType.FEDERAL_GSA_CARD,
    FormType.FEDERAL_LETTERHEAD,
}


def run_all_checks(
    fields: ExtractedFields,
    form_type: FormType,
    entity_type: EntityType,
    pathway: ValidationPathway,
    state: str,
) -> list[CheckResult]:
    """Run all validation checks in sequence and return results."""
    results: list[CheckResult | None] = []

    results.append(check_purchaser_name(fields))
    results.append(check_purchaser_name_is_entity(fields))
    results.append(check_purchaser_address(fields, pathway))
    results.append(check_seller_name(fields, pathway))
    results.append(check_exemption_reason(fields, pathway))
    results.append(check_signature(fields, pathway))
    results.append(check_date(fields, pathway))
    results.append(check_exemption_state(fields, state))
    results.append(check_compound_failure([r for r in results if r is not None]))

    results.append(check_form_correct_for_state(form_type, state))
    results.append(check_mtc_resale_only(fields, form_type, state))
    results.append(check_sst_member(form_type, state))
    results.append(check_state_specific_requirements(fields, form_type, state))

    results.append(check_expiration(fields, state, form_type))
    results.append(check_future_date(fields))
    results.append(check_cert_age(fields))

    results.append(check_exemption_for_saas(fields, entity_type, state))
    if _derive_exemption_category(fields) == ExemptionCategory.RESALE:
        results.append(check_resale_tier(fields, entity_type))
    results.append(check_entity_exemption_match(fields, entity_type, state))
    results.append(check_saas_taxability(state))

    return [r for r in results if r is not None]


def check_purchaser_name(fields: ExtractedFields) -> CheckResult:
    if not fields.purchaser_name or len(fields.purchaser_name.strip()) < 2:
        return CheckResult(
            check_name="completeness.purchaser_name",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message="Missing purchaser/buyer name",
            field="purchaser_name",
            recommendation="Certificate must identify the purchaser claiming the exemption.",
        )
    return CheckResult(
        check_name="completeness.purchaser_name",
        passed=True,
        severity=CheckSeverity.INFO,
        message=f"Purchaser name present: {fields.purchaser_name}",
    )


def check_purchaser_name_is_entity(fields: ExtractedFields) -> CheckResult:
    name = (fields.purchaser_name or "").strip()
    if not name:
        return CheckResult(
            check_name="completeness.purchaser_name_is_entity",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message="Purchaser name missing; cannot verify entity vs personal name",
            field="purchaser_name",
            recommendation="Provide full legal entity name.",
        )

    entity_indicators = [
        "llc", "inc", "corp", "ltd", "lp", "llp", "co", "company", "department",
        "city of", "county of", "district", "authority", "board", "commission",
        "foundation", "association", "university", "college", "church", "temple",
        "services", "solutions", "group", "holdings", "enterprise", "tribe", "tribal",
        "esd", "isd", "school", "state of", "town of", "village of", "parish",
    ]

    lower = name.lower()
    if any(ind in lower for ind in entity_indicators):
        return CheckResult(
            check_name="completeness.purchaser_name_is_entity",
            passed=True,
            severity=CheckSeverity.INFO,
            message="Purchaser name appears to be an entity.",
        )

    parts = [p for p in re.split(r"\s+", name) if p]
    alpha_parts = [p for p in parts if re.fullmatch(r"[A-Za-z][A-Za-z'\-.]*", p)]
    cap_pattern = all(re.fullmatch(r"[A-Z][a-zA-Z'\-.]*", p) for p in alpha_parts) if alpha_parts else False
    if len(alpha_parts) in {2, 3} and len(alpha_parts) == len(parts) and cap_pattern:
        return CheckResult(
            check_name="completeness.purchaser_name_is_entity",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message=f"Purchaser name '{name}' appears to be a personal name, not a legal entity.",
            field="purchaser_name",
            recommendation="Provide the legal entity name (e.g., LLC, government agency, nonprofit).",
        )

    return CheckResult(
        check_name="completeness.purchaser_name_is_entity",
        passed=False,
        severity=CheckSeverity.SOFT_FLAG,
        message=f"Purchaser name '{name}' is ambiguous and may be a sole proprietor/DBA.",
        field="purchaser_name",
        recommendation="Confirm legal entity name on the certificate.",
    )


def check_purchaser_address(fields: ExtractedFields, pathway: ValidationPathway) -> CheckResult | None:
    if pathway not in {ValidationPathway.STANDARD_SELF_COMPLETED, ValidationPathway.MULTI_STATE_UNIFORM}:
        return None

    if not fields.purchaser_address or len(fields.purchaser_address.strip()) < 5:
        return CheckResult(
            check_name="completeness.purchaser_address",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message="Missing purchaser address",
            field="purchaser_address",
            recommendation="Provide purchaser street/city/state address.",
        )
    return CheckResult(
        check_name="completeness.purchaser_address",
        passed=True,
        severity=CheckSeverity.INFO,
        message="Purchaser address present.",
    )


def check_seller_name(fields: ExtractedFields, pathway: ValidationPathway) -> CheckResult | None:
    if pathway not in {ValidationPathway.STANDARD_SELF_COMPLETED, ValidationPathway.MULTI_STATE_UNIFORM}:
        return None

    seller = (fields.seller_name or "").strip()
    if not seller:
        return CheckResult(
            check_name="completeness.seller_name",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message="Missing seller name",
            field="seller_name",
            recommendation="Certificate must identify seller/vendor name.",
        )

    cfg = load_config("reasonableness_rules.json").get("seller_name_variants", {})
    accepted = {s.lower() for s in cfg.get("exact_matches", []) + cfg.get("acceptable_variants", [])}
    lower = seller.lower()

    if lower in accepted:
        return CheckResult(
            check_name="completeness.seller_name",
            passed=True,
            severity=CheckSeverity.INFO,
            message=f"Seller name matches accepted Fleetio variant: {seller}",
        )

    if "fleetio" in lower or "rarestep" in lower:
        return CheckResult(
            check_name="completeness.seller_name",
            passed=True,
            severity=CheckSeverity.INFO,
            message=f"Seller name contains Fleetio/Rarestep reference: {seller}",
        )

    if lower in {"seller", "vendor", "vendor name", "seller name"}:
        return CheckResult(
            check_name="completeness.seller_name",
            passed=False,
            severity=CheckSeverity.SOFT_FLAG,
            message=f"Seller name '{seller}' is generic and may be incomplete.",
            recommendation="List full legal seller name (Fleetio, Inc.).",
        )

    return CheckResult(
        check_name="completeness.seller_name",
        passed=False,
        severity=CheckSeverity.HARD_FAIL,
        message=f"Seller name '{seller}' does not match Fleetio/Rarestep variants.",
        field="seller_name",
        recommendation="Certificate should list Fleetio (or known Rarestep/Fleetio variant) as seller.",
    )


def check_exemption_reason(fields: ExtractedFields, pathway: ValidationPathway) -> CheckResult | None:
    if pathway not in {ValidationPathway.STANDARD_SELF_COMPLETED, ValidationPathway.MULTI_STATE_UNIFORM}:
        return None

    if not fields.exemption_reason or len(fields.exemption_reason.strip()) < 3:
        return CheckResult(
            check_name="completeness.exemption_reason",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message="Missing exemption reason/type",
            field="exemption_reason",
            recommendation="State the statutory exemption reason or category.",
        )
    return CheckResult(
        check_name="completeness.exemption_reason",
        passed=True,
        severity=CheckSeverity.INFO,
        message=f"Exemption reason present: {fields.exemption_reason}",
    )


def check_signature(fields: ExtractedFields, pathway: ValidationPathway) -> CheckResult | None:
    if pathway not in {ValidationPathway.STANDARD_SELF_COMPLETED, ValidationPathway.MULTI_STATE_UNIFORM}:
        return None

    if not fields.signature_present:
        return CheckResult(
            check_name="completeness.signature",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message="Missing purchaser signature",
            field="signature_present",
            recommendation="Signed certificate required for self-completed forms.",
        )

    return CheckResult(
        check_name="completeness.signature",
        passed=True,
        severity=CheckSeverity.INFO,
        message="Signature present.",
    )


def check_date(fields: ExtractedFields, pathway: ValidationPathway) -> CheckResult | None:
    if pathway not in {ValidationPathway.STANDARD_SELF_COMPLETED, ValidationPathway.MULTI_STATE_UNIFORM}:
        return None

    if not fields.cert_date:
        return CheckResult(
            check_name="completeness.cert_date",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message="Missing certificate date",
            field="cert_date",
            recommendation="Provide execution date on certificate.",
        )

    return CheckResult(
        check_name="completeness.cert_date",
        passed=True,
        severity=CheckSeverity.INFO,
        message=f"Certificate date present: {fields.cert_date.isoformat()}",
    )


def check_exemption_state(fields: ExtractedFields, state: str) -> CheckResult:
    normalized = (state or "").strip().upper()
    if normalized:
        return CheckResult(
            check_name="completeness.exemption_state",
            passed=True,
            severity=CheckSeverity.INFO,
            message=f"Exemption state identified: {normalized}",
        )

    if fields.exemption_states:
        return CheckResult(
            check_name="completeness.exemption_state",
            passed=True,
            severity=CheckSeverity.INFO,
            message=f"Exemption states listed: {', '.join(fields.exemption_states)}",
        )

    return CheckResult(
        check_name="completeness.exemption_state",
        passed=False,
        severity=CheckSeverity.HARD_FAIL,
        message="Could not determine exemption state from certificate.",
        field="exemption_states",
        recommendation="Identify the state claimed or use state-specific certificate form.",
    )


def check_compound_failure(previous_results: list[CheckResult]) -> CheckResult | None:
    hard_fail_count = sum(1 for r in previous_results if (not r.passed and r.severity == CheckSeverity.HARD_FAIL))
    if hard_fail_count >= 3:
        return CheckResult(
            check_name="completeness.compound_failure",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message=f"Compound failure: {hard_fail_count} HARD_FAIL checks triggered.",
            recommendation="Request corrected certificate; multiple independent defects present.",
        )
    return None


def check_form_correct_for_state(form_type: FormType, state: str) -> CheckResult | None:
    normalized_state = (state or "").strip().upper()
    if not normalized_state or form_type == FormType.UNKNOWN:
        return None

    if form_type in _FEDERAL_FORMS:
        return CheckResult(
            check_name="form_correctness.form_state_match",
            passed=True,
            severity=CheckSeverity.INFO,
            message="Federal form accepted in all states.",
        )

    if form_type == FormType.MTC_UNIFORM:
        return CheckResult(
            check_name="form_correctness.form_state_match",
            passed=True,
            severity=CheckSeverity.INFO,
            message=f"MTC Uniform form accepted for evaluation in {normalized_state} (state restrictions checked separately).",
        )

    if form_type == FormType.SST_F0003:
        return CheckResult(
            check_name="form_correctness.form_state_match",
            passed=True,
            severity=CheckSeverity.INFO,
            message=f"SST form routed for {normalized_state}; membership checked separately.",
        )

    expected_state = _FORM_STATE_MAP.get(form_type)
    if expected_state and expected_state != normalized_state:
        return CheckResult(
            check_name="form_correctness.form_state_match",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message=f"{form_type.value} is a {expected_state} form and cannot support a {normalized_state} claim.",
            recommendation=f"Use a {normalized_state}-valid exemption form.",
        )

    return CheckResult(
        check_name="form_correctness.form_state_match",
        passed=True,
        severity=CheckSeverity.INFO,
        message=f"Form type {form_type.value} aligns with state {normalized_state}.",
    )


def _derive_exemption_category(fields: ExtractedFields) -> ExemptionCategory | None:
    if fields.exemption_category:
        return fields.exemption_category

    reason = (fields.exemption_reason or "").lower()
    if "resale" in reason:
        return ExemptionCategory.RESALE
    if "government" in reason or "gov" in reason:
        return ExemptionCategory.GOVERNMENT
    if "nonprofit" in reason or "501" in reason:
        return ExemptionCategory.NONPROFIT
    return None


def _has_state_registration(fields: ExtractedFields, state: str) -> bool:
    haystack = " ".join(
        [
            fields.purchaser_tax_id or "",
            fields.purchaser_fein or "",
            fields.account_number or "",
            fields.permit_number or "",
            fields.raw_text or "",
        ]
    ).upper()

    if state == "PA":
        return bool(re.search(r"\bPA\s*[-#:]?\s*[A-Z0-9]{4,}\b", haystack)) or bool(
            re.search(r"SALES\s+AND\s+USE\s+TAX\s+LICENSE", haystack)
        )
    if state == "MD":
        return bool(re.search(r"\bMD\s*[-#:]?\s*[A-Z0-9]{4,}\b", haystack)) or bool(
            re.search(r"REGISTRATION\s+NUMBER", haystack)
        )
    return bool(re.search(r"\b[A-Z0-9-]{6,}\b", haystack))


def check_mtc_resale_only(fields: ExtractedFields, form_type: FormType, state: str) -> CheckResult | None:
    if form_type != FormType.MTC_UNIFORM:
        return None

    normalized_state = (state or "").strip().upper()
    rules = load_config("mtc_restrictions.json")
    resale_only_states = rules.get("resale_only_states", {})
    registration_required_states = rules.get("registration_required_states", {})

    if normalized_state in resale_only_states:
        category = _derive_exemption_category(fields)
        if category != ExemptionCategory.RESALE:
            alt_forms = resale_only_states[normalized_state].get("alternative_forms", [])
            template = rules.get("correction_template", "MTC restricted in {state}.")
            message = template.format(state=normalized_state, alternative_forms=", ".join(alt_forms) or "state-specific forms")
            return CheckResult(
                check_name="form_correctness.mtc_resale_only",
                passed=False,
                severity=CheckSeverity.HARD_FAIL,
                message=message,
                recommendation="Resubmit on approved form for non-resale exemption.",
            )

    if normalized_state in registration_required_states and not _has_state_registration(fields, normalized_state):
        requirement = registration_required_states[normalized_state].get("requirement", "Required registration missing")
        return CheckResult(
            check_name="form_correctness.mtc_registration_required",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message=f"MTC {normalized_state} requirement not met: {requirement}.",
            recommendation="Provide required state registration/license number on certificate.",
        )

    return CheckResult(
        check_name="form_correctness.mtc_resale_only",
        passed=True,
        severity=CheckSeverity.INFO,
        message=f"MTC form passes {normalized_state} resale/registration restrictions.",
    )


def check_sst_member(form_type: FormType, state: str) -> CheckResult | None:
    if form_type != FormType.SST_F0003:
        return None

    normalized_state = (state or "").strip().upper()
    sst_members = set(load_config("state_rules.json").get("sst_member_states", []))
    if normalized_state not in sst_members:
        alternative = _FORM_STATE_MAP.get(FormType.TX_01_339, "a state-specific form") if normalized_state == "TX" else "a state-specific form"
        return CheckResult(
            check_name="form_correctness.sst_member",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message=(
                f"SST Certificate of Exemption is not accepted in {normalized_state}. "
                f"{normalized_state} is not an SST member state. Please submit {alternative}."
            ),
        )

    return CheckResult(
        check_name="form_correctness.sst_member",
        passed=True,
        severity=CheckSeverity.INFO,
        message=f"{normalized_state} is an SST member state.",
    )


def check_state_specific_requirements(fields: ExtractedFields, form_type: FormType, state: str) -> CheckResult | None:
    normalized_state = (state or "").strip().upper()

    if normalized_state == "PA" and form_type == FormType.MTC_UNIFORM and not _has_state_registration(fields, "PA"):
        return CheckResult(
            check_name="state_specific.pa_mtc_license",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message="PA + MTC requires PA Sales and Use Tax license number.",
            recommendation="Provide PA license number on certificate.",
        )

    if normalized_state == "MD" and form_type == FormType.MTC_UNIFORM and not _has_state_registration(fields, "MD"):
        return CheckResult(
            check_name="state_specific.md_mtc_registration",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message="MD + MTC requires MD registration number.",
            recommendation="Provide MD registration number.",
        )

    if normalized_state == "MA" and form_type == FormType.MA_ST_2:
        txt = (fields.raw_text or "").lower()
        if "501(c)(3)" not in txt and "determination letter" not in txt:
            return CheckResult(
                check_name="state_specific.ma_st2_501c3_letter",
                passed=False,
                severity=CheckSeverity.SOFT_FLAG,
                message="MA ST-2 generally supported by IRS 501(c)(3) determination letter; not found in packet.",
                recommendation="Request determination letter if not already on file.",
            )

    if normalized_state == "TX" and fields.exemption_category == ExemptionCategory.GOVERNMENT:
        return CheckResult(
            check_name="state_specific.tx_gov_tax_id_optional",
            passed=True,
            severity=CheckSeverity.INFO,
            message="TX government entities do not require tax ID number on exemption cert.",
        )

    return None


def _resolve_expiration_rule(state: str, form_type: FormType) -> tuple[dict, str]:
    rules = load_config("state_rules.json").get("expiration_rules", {})

    if form_type in _FEDERAL_FORMS:
        return rules.get("FEDERAL", {"rule": "never"}), "FEDERAL"

    state_rule = rules.get(state, rules.get("DEFAULT", {"rule": "never"}))
    rule = state_rule.get("rule", "never")

    if rule != "form_specific":
        return state_rule, state

    forms = state_rule.get("forms", {})
    key_map = {
        FormType.MD_GOV_1: "GOV-1",
        FormType.MD_NONGOV_1: "NONGOV-1",
        FormType.MA_ST_2: "ST-2",
        FormType.MA_ST_5: "ST-5",
        FormType.TN_GOV: "gov",
        FormType.TN_EXEMPT_ORG: "exempt_org",
    }
    selected = forms.get(key_map.get(form_type, ""), {"rule": "never"})
    merged = {**state_rule, **selected}
    return merged, f"{state}:{key_map.get(form_type, 'default')}"


def _date_window_result(check_name: str, expiration: date, state: str, citation: str | None) -> CheckResult:
    today = date.today()
    cite_suffix = f" Citation: {citation}." if citation else ""
    if today > expiration:
        return CheckResult(
            check_name=check_name,
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message=f"Certificate expired on {expiration.isoformat()} per {state} rules.{cite_suffix}",
            recommendation="Obtain renewed certificate.",
        )
    if (expiration - today).days <= 90:
        return CheckResult(
            check_name=check_name,
            passed=False,
            severity=CheckSeverity.SOFT_FLAG,
            message=f"Certificate expiring within 90 days ({expiration.isoformat()}). Queue renewal.{cite_suffix}",
            recommendation="Request updated certificate proactively.",
        )
    return CheckResult(
        check_name=check_name,
        passed=True,
        severity=CheckSeverity.INFO,
        message=f"Certificate valid through {expiration.isoformat()} under {state} expiration rules.{cite_suffix}",
    )


def check_expiration(fields: ExtractedFields, state: str, form_type: FormType) -> CheckResult:
    normalized_state = (state or "").strip().upper() or "DEFAULT"
    rule_cfg, rule_source = _resolve_expiration_rule(normalized_state, form_type)
    rule = rule_cfg.get("rule", "never")
    citation = rule_cfg.get("citation")

    if rule == "never":
        return CheckResult(
            check_name="expiration.state_rule",
            passed=True,
            severity=CheckSeverity.INFO,
            message=f"No expiration under rule '{rule}' ({rule_source}). {citation or ''}".strip(),
        )

    cert_date = fields.cert_date

    if rule in {"fixed_years", "annual"}:
        years = 1 if rule == "annual" else int(rule_cfg.get("years", 0) or 0)
        if not cert_date:
            return CheckResult(
                check_name="expiration.state_rule",
                passed=False,
                severity=CheckSeverity.SOFT_FLAG,
                message=f"Cannot compute expiration for rule '{rule}' without certificate date.",
                field="cert_date",
                recommendation="Extract/confirm certificate execution date.",
            )
        try:
            expiration = cert_date.replace(year=cert_date.year + years)
        except ValueError:
            expiration = cert_date.replace(month=2, day=28, year=cert_date.year + years)
        return _date_window_result("expiration.state_rule", expiration, normalized_state, citation)

    if rule in {"state_printed", "period_cert"}:
        if not fields.expiration_date:
            return CheckResult(
                check_name="expiration.state_rule",
                passed=False,
                severity=CheckSeverity.SOFT_FLAG,
                message="No expiration date found on state-issued certificate.",
                field="expiration_date",
                recommendation="Capture printed expiration date from certificate.",
            )
        return _date_window_result("expiration.state_rule", fields.expiration_date, normalized_state, citation)

    return CheckResult(
        check_name="expiration.state_rule",
        passed=True,
        severity=CheckSeverity.INFO,
        message=f"Unhandled expiration rule '{rule}' defaulted to pass.",
    )


def check_future_date(fields: ExtractedFields) -> CheckResult | None:
    if not fields.cert_date:
        return None
    if fields.cert_date > date.today():
        return CheckResult(
            check_name="expiration.future_date",
            passed=False,
            severity=CheckSeverity.HARD_FAIL,
            message=f"Certificate date {fields.cert_date.isoformat()} is in the future.",
            field="cert_date",
            recommendation="Use actual execution date; pre-dated certificates are invalid.",
        )
    return CheckResult(
        check_name="expiration.future_date",
        passed=True,
        severity=CheckSeverity.INFO,
        message="Certificate date is not in the future.",
    )


def check_cert_age(fields: ExtractedFields) -> CheckResult | None:
    if not fields.cert_date:
        return None

    age_years = (date.today() - fields.cert_date).days / 365.25
    notes = load_config("state_rules.json").get("cert_age_flags", {})

    if age_years < 3:
        return CheckResult(
            check_name="expiration.cert_age",
            passed=True,
            severity=CheckSeverity.INFO,
            message="Certificate age within 0-3 years.",
        )
    if age_years < 4:
        return CheckResult(
            check_name="expiration.cert_age",
            passed=False,
            severity=CheckSeverity.SOFT_FLAG,
            message=notes.get("3_to_4_years", {}).get("note", "Renewal recommended within next year"),
            recommendation="Consider requesting renewal in next cycle.",
        )
    if age_years < 5:
        return CheckResult(
            check_name="expiration.cert_age",
            passed=False,
            severity=CheckSeverity.SOFT_FLAG,
            message=notes.get("4_to_5_years", {}).get("note", "Certificate aging; request updated cert"),
            recommendation="Request refreshed certificate.",
        )
    return CheckResult(
        check_name="expiration.cert_age",
        passed=False,
        severity=CheckSeverity.SOFT_FLAG,
        message=notes.get("5_plus_years", {}).get(
            "note", "Certificate is 5+ years old; best practice is to obtain updated documentation"
        ),
        recommendation="Obtain updated documentation as best practice.",
    )


def check_exemption_for_saas(
    fields: ExtractedFields,
    entity_type: EntityType,
    state: str,
) -> CheckResult | None:
    rules = load_config("reasonableness_rules.json").get("exemption_validity_for_saas", {})
    category = _derive_exemption_category(fields)
    if category is None:
        return None

    category_cfg = rules.get(category.name, {})
    state_upper = (state or "").strip().upper()

    if category in {ExemptionCategory.GOVERNMENT, ExemptionCategory.NONPROFIT, ExemptionCategory.DIRECT_PAY}:
        note = category_cfg.get("note", "Exemption category is generally plausible for SaaS.")
        return CheckResult(
            check_name="reasonableness.exemption_for_saas",
            passed=True,
            severity=CheckSeverity.INFO,
            message=note,
        )

    if category == ExemptionCategory.CONSTRUCTION:
        return CheckResult(
            check_name="reasonableness.exemption_for_saas",
            passed=True,
            severity=CheckSeverity.INFO,
            message=category_cfg.get("note", "Construction claims are plausible for fleet SaaS but state-specific."),
            recommendation=category_cfg.get("review_note"),
        )

    if category == ExemptionCategory.RESALE:
        return CheckResult(
            check_name="reasonableness.exemption_for_saas",
            passed=True,
            severity=CheckSeverity.INFO,
            message=category_cfg.get("note", "Resale claims require tiering review."),
        )

    if category in {
        ExemptionCategory.MANUFACTURING,
        ExemptionCategory.AGRICULTURE,
        ExemptionCategory.COMMON_CARRIER,
        ExemptionCategory.INDUSTRIAL_RD,
    }:
        citations = category_cfg.get("citations", [])
        cite = f" Citations: {', '.join(citations)}." if citations else ""
        msg = category_cfg.get("reason", "Exemption category appears implausible for SaaS purchases.")
        if category == ExemptionCategory.COMMON_CARRIER and state_upper and state_upper != "OH":
            msg = f"Common carrier exemption is primarily an Ohio concept and is generally not valid for SaaS in {state_upper}."
        return CheckResult(
            check_name="reasonableness.exemption_for_saas",
            passed=False,
            severity=CheckSeverity.REASONABLENESS,
            message=f"{msg}{cite}",
            recommendation=category_cfg.get("review_note") or "Route to human review.",
        )

    return CheckResult(
        check_name="reasonableness.exemption_for_saas",
        passed=False,
        severity=CheckSeverity.REASONABLENESS,
        message=f"Exemption category '{category.value}' requires human review for SaaS reasonableness.",
        recommendation="Route to tax reviewer for classification.",
    )


def check_resale_tier(
    fields: ExtractedFields,
    entity_type: EntityType,
) -> CheckResult | None:
    if _derive_exemption_category(fields) != ExemptionCategory.RESALE:
        return None

    tiers = load_config("reasonableness_rules.json").get("resale_tiers", {})
    text = " ".join(filter(None, [fields.business_type, fields.purchaser_name])).lower()

    tier_map = [
        ("TIER_1_STRONG", "STRONG", True, CheckSeverity.INFO),
        ("TIER_2_PLAUSIBLE", "PLAUSIBLE", True, CheckSeverity.INFO),
        ("TIER_3_WEAK", "WEAK", False, CheckSeverity.REASONABLENESS),
        ("TIER_4_IMPLAUSIBLE", "IMPLAUSIBLE", False, CheckSeverity.REASONABLENESS),
    ]

    for key, label, passed, severity in tier_map:
        cfg = tiers.get(key, {})
        for pattern in cfg.get("patterns", []):
            if pattern.lower() in text:
                outcome = "accepted" if passed else "flagged for review"
                return CheckResult(
                    check_name="reasonableness.resale_tier",
                    passed=passed,
                    severity=severity,
                    message=f"Resale tier={label} based on pattern '{pattern}' in purchaser profile; claim {outcome}.",
                    field="business_type",
                    recommendation=cfg.get("note") or cfg.get("review_note"),
                )

    return CheckResult(
        check_name="reasonableness.resale_tier",
        passed=False,
        severity=CheckSeverity.REASONABLENESS,
        message="Resale tier=WEAK by default (no known resale pattern matched); conservative human review required.",
        field="business_type",
        recommendation="Confirm customer has a genuine SaaS resale channel.",
    )


def check_entity_exemption_match(
    fields: ExtractedFields,
    entity_type: EntityType,
    state: str,
) -> CheckResult | None:
    category = _derive_exemption_category(fields)
    if category is None:
        return None

    cfg = load_config("reasonableness_rules.json")
    mismatches = cfg.get("wrong_box_rules", {})
    state_rules = load_config("state_rules.json")
    sst_states = set(state_rules.get("sst_member_states", []))

    state_upper = (state or "").strip().upper()
    is_sst = state_upper in sst_states
    sev = CheckSeverity.SOFT_FLAG if is_sst else CheckSeverity.REASONABLENESS

    gov_entities = {EntityType.FEDERAL_GOVERNMENT, EntityType.STATE_GOVERNMENT, EntityType.LOCAL_GOVERNMENT, EntityType.TRIBAL}
    mismatch_reason: str | None = None

    if entity_type in gov_entities and category in {ExemptionCategory.MANUFACTURING, ExemptionCategory.AGRICULTURE}:
        mismatch_reason = "Government entity appears to have selected an inapplicable manufacturing/agriculture exemption box."
        sev = CheckSeverity.INFO
    elif entity_type in {EntityType.NONPROFIT_501C3, EntityType.EXEMPT_ORG_OTHER, EntityType.RELIGIOUS, EntityType.EDUCATIONAL} and category == ExemptionCategory.RESALE:
        mismatch_reason = "Nonprofit entity claiming resale is unusual and should be reviewed."
    elif entity_type == EntityType.FOR_PROFIT and category == ExemptionCategory.GOVERNMENT:
        mismatch_reason = "For-profit entity appears to claim a government exemption."

    if not mismatch_reason:
        return CheckResult(
            check_name="reasonableness.entity_exemption_match",
            passed=True,
            severity=CheckSeverity.INFO,
            message="Entity type and exemption category are not obviously mismatched.",
        )

    if sev == CheckSeverity.INFO:
        return CheckResult(
            check_name="reasonableness.entity_exemption_match",
            passed=False,
            severity=CheckSeverity.INFO,
            message=f"{mismatch_reason} Government status still supports exemption; note only.",
            recommendation=mismatches.get("government_wrong_box", {}).get("note") if isinstance(mismatches, dict) else None,
        )

    review_message = "SST four-corners protections may reduce seller risk." if is_sst else "Good-faith documentation standard applies."
    return CheckResult(
        check_name="reasonableness.entity_exemption_match",
        passed=False,
        severity=sev,
        message=f"{mismatch_reason} {review_message}",
        recommendation="Route for manual review of correct exemption basis.",
    )


def check_saas_taxability(state: str) -> CheckResult:
    state_upper = (state or "").strip().upper()
    taxability = load_config("state_rules.json").get("taxability", {})
    record = taxability.get(state_upper, {})

    if record.get("no_sales_tax"):
        return CheckResult(
            check_name="info.saas_taxability",
            passed=True,
            severity=CheckSeverity.INFO,
            message=f"{state_upper} has no sales tax.",
        )

    if record.get("taxable") is False:
        note = f" {record.get('note')}" if record.get("note") else ""
        return CheckResult(
            check_name="info.saas_taxability",
            passed=True,
            severity=CheckSeverity.INFO,
            message=f"SaaS is not taxable in {state_upper}. Certificate on file as insurance but may not be required.{note}",
        )

    if record.get("taxable") is True:
        rate = record.get("rate", "state rate")
        return CheckResult(
            check_name="info.saas_taxability",
            passed=True,
            severity=CheckSeverity.INFO,
            message=f"SaaS is taxable in {state_upper} at {rate}. Certificate IS required for exempt transactions.",
        )

    return CheckResult(
        check_name="info.saas_taxability",
        passed=True,
        severity=CheckSeverity.INFO,
        message=f"SaaS taxability not found for {state_upper}; verify state treatment manually.",
    )



def _normalize_name(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"[^a-z0-9\s]", "", value.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def find_duplicates(results: list[dict]) -> list[tuple[str, str]]:
    """
    Identify duplicate certificates in a batch.

    Fingerprint algorithm:
    - Normalize customer_name (lowercase, strip whitespace, remove punctuation)
    - Combine: customer_name + state + exemption_category + cert_date
    - If two certs have identical fingerprints, they're duplicates

    For certs with no cert_date, use customer_name + state + form_type as fingerprint.

    Returns list of tuples: (cert_id_1, cert_id_2) indicating duplicate pairs.
    Mark the NEWER cert (by cert_date or file modification date) as the duplicate.
    """
    buckets: dict[str, list[dict]] = {}
    for result in results:
        customer = _normalize_name(result.get("customer_name"))
        state = (result.get("state") or "").strip().upper()
        exemption_category = (result.get("exemption_category") or "").strip().lower()
        cert_date = result.get("cert_date") or result.get("expiration_date") or ""
        form_type = (result.get("form_type") or "").strip()

        if cert_date:
            fingerprint = f"{customer}|{state}|{exemption_category}|{cert_date}"
        else:
            fingerprint = f"{customer}|{state}|{form_type}"

        buckets.setdefault(fingerprint, []).append(result)

    duplicates: list[tuple[str, str]] = []
    for bucket in buckets.values():
        if len(bucket) < 2:
            continue

        def sort_key(item: dict):
            date_marker = item.get("cert_date") or item.get("validated_at") or ""
            return str(date_marker)

        sorted_bucket = sorted(bucket, key=sort_key)
        canonical = sorted_bucket[0]
        canonical_id = str(canonical.get("cert_id") or canonical.get("avalara_cert_id") or "unknown")
        for duplicate in sorted_bucket[1:]:
            dup_id = str(duplicate.get("cert_id") or duplicate.get("avalara_cert_id") or "unknown")
            duplicates.append((canonical_id, dup_id))

    return duplicates
