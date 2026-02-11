from .models import EntityType, ExtractedFields, FormType, ValidationPathway
from .utils import load_config

FEDERAL_INDICATORS = [
    "United States", "U.S. Government", "US Government", "GSA",
    "Department of Defense", "Department of the", "Federal",
    "U.S. Army", "U.S. Navy", "U.S. Air Force", "U.S. Marine",
    "U.S. Coast Guard", "Department of Veterans", "USDA",
    "Department of Homeland", "Department of Energy",
    "Department of Justice", "Department of State",
    "Department of the Interior", "Department of Commerce",
    "Department of Labor", "Department of Transportation",
    "Environmental Protection Agency", "EPA", "NASA", "FEMA",
    "General Services Administration", "Bureau of",
    "National Park Service", "Forest Service",
    "Internal Revenue Service", "IRS",
    "Social Security Administration", "SSA",
    "Veterans Affairs", "VA Medical"
]

STATE_GOVERNMENT_INDICATORS = [
    "State of", "Highway Patrol", "State Police",
    "State Department of", "State Board of",
    "Department of Transportation", "DOT",
    "Department of Corrections",
    "State University"
]

LOCAL_GOVERNMENT_INDICATORS = [
    "City of", "County of", "Town of", "Township",
    "Village of", "Borough of", "Parish of",
    "Municipal", "Municipality", "District",
    "Fire Department", "Fire District", "ESD",
    "Emergency Services District",
    "Police Department", "Sheriff",
    "Water Authority", "Water District",
    "Sewer Authority", "Sewer District",
    "Transit Authority", "Transportation Authority",
    "School District", "Board of Education",
    "Independent School District", "ISD",
    "Public Library", "Library District",
    "Housing Authority", "Port Authority",
    "Flood Control District"
]

TRIBAL_INDICATORS = [
    "Tribe", "Tribal", "Nation",
    "Indian Community", "Pueblo", "Reservation",
    "Tribal Enterprise", "Tribal Council",
    "Band of", "Rancheria"
]

EDUCATIONAL_INDICATORS = [
    "University", "College", "Academy",
    "Institute of Technology", "Institute of",
    "School of"
]

NONPROFIT_INDICATORS = [
    "501(c)(3)", "501c3", "nonprofit", "not-for-profit",
    "Foundation", "Association", "Society",
    "Charitable", "Charity"
]

RELIGIOUS_INDICATORS = [
    "Church", "Temple", "Mosque", "Synagogue",
    "Diocese", "Ministry", "Cathedral",
    "Parish"
]

FOR_PROFIT_INDICATORS = [
    "LLC", "Inc.", "Inc", "Corp.", "Corp", "Corporation",
    "Ltd.", "Ltd", "LP", "LLP", "Co.", "Company",
    "Enterprises", "Holdings", "Group"
]


def _contains_any(text: str, indicators: list[str]) -> bool:
    lower_text = text.lower()
    return any(ind.lower() in lower_text for ind in indicators)


def classify_entity(fields: ExtractedFields) -> EntityType:
    """Classify the purchaser's entity type from extracted cert content."""
    source = " ".join([fields.purchaser_name or "", fields.raw_text or ""])
    lower = source.lower()

    if _contains_any(source, FEDERAL_INDICATORS):
        return EntityType.FEDERAL_GOVERNMENT

    if "state university" in lower:
        return EntityType.STATE_GOVERNMENT

    if _contains_any(source, STATE_GOVERNMENT_INDICATORS):
        return EntityType.STATE_GOVERNMENT

    if "parish of" in lower:
        return EntityType.LOCAL_GOVERNMENT

    if _contains_any(source, LOCAL_GOVERNMENT_INDICATORS):
        return EntityType.LOCAL_GOVERNMENT

    tribal_context = _contains_any(source, [i for i in TRIBAL_INDICATORS if i != "Nation"])
    if tribal_context or ("nation" in lower and "tribal" in lower):
        return EntityType.TRIBAL

    education = _contains_any(source, EDUCATIONAL_INDICATORS)
    nonprofit = _contains_any(source, NONPROFIT_INDICATORS)
    if education:
        return EntityType.EDUCATIONAL

    if nonprofit:
        return EntityType.NONPROFIT_501C3

    if "parish" in lower and _contains_any(source, RELIGIOUS_INDICATORS):
        return EntityType.RELIGIOUS

    if _contains_any(source, RELIGIOUS_INDICATORS):
        return EntityType.RELIGIOUS

    if _contains_any(source, FOR_PROFIT_INDICATORS):
        return EntityType.FOR_PROFIT

    return EntityType.UNKNOWN


def check_entity_form_compatibility(
    state: str,
    entity_type: EntityType,
    form_type: FormType,
) -> tuple[bool, str | None]:
    """Check if the form type is valid for this entity type in this state."""
    data = load_config("form_templates.json")
    rules = data.get("entity_form_incompatible", {}).get("rules", [])

    normalized_state = (state or "").strip().upper()

    for rule in rules:
        if rule.get("state", "").upper() != normalized_state:
            continue
        if rule.get("form") != form_type.name:
            continue
        if entity_type.name in rule.get("entity_types", []):
            return False, rule.get("message")

    return True, None


def route_to_pathway(
    form_type: FormType,
    entity_type: EntityType,
    fields: ExtractedFields,
) -> ValidationPathway:
    """Route to validation pathway based on form + entity context."""
    federal_forms = {
        FormType.FEDERAL_SF_1094,
        FormType.FEDERAL_GSA_CARD,
        FormType.FEDERAL_LETTERHEAD,
    }
    if form_type in federal_forms:
        return ValidationPathway.FEDERAL_EXEMPTION

    if form_type in {FormType.MD_GOV_1}:
        return ValidationPathway.GOV_CARD_NO_EXPIRY

    if form_type in {FormType.MD_NONGOV_1, FormType.FL_DR_14}:
        return ValidationPathway.GOV_CARD_WITH_EXPIRY

    if form_type in {FormType.IL_E99, FormType.IL_STAX_70, FormType.TN_GOV, FormType.TN_EXEMPT_ORG, FormType.NY_GOV_LETTER}:
        return ValidationPathway.STATE_ISSUED_CERT

    if form_type in {FormType.OH_DIRECT_PAY, FormType.WA_RESELLER}:
        return ValidationPathway.SPECIAL_PERMIT

    if form_type in {FormType.MTC_UNIFORM, FormType.SST_F0003}:
        return ValidationPathway.MULTI_STATE_UNIFORM

    return ValidationPathway.STANDARD_SELF_COMPLETED
