import re
from datetime import date

from .models import EntityType, ExtractedFields, FormType
from .utils import load_config, normalize_state, parse_date


STATE_SPECIFIC_FORM_EXCLUSIONS = {
    FormType.MTC_UNIFORM,
    FormType.SST_F0003,
    FormType.FEDERAL_SF_1094,
    FormType.FEDERAL_GSA_CARD,
    FormType.FEDERAL_LETTERHEAD,
    FormType.GOVERNMENT_ISSUED_CARD,
    FormType.STATE_ISSUED_CERT,
    FormType.CUSTOM_LETTER,
    FormType.UNKNOWN,
}


def _safe_form_type(name: str) -> FormType:
    try:
        return FormType[name]
    except KeyError:
        return FormType.UNKNOWN


def _compile_label_pattern(label: str) -> re.Pattern[str]:
    return re.compile(rf"(?i){re.escape(label)}\s*[:\-]?\s*(.+)")


def _normalize_label_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _line_has_label(line: str, labels: list[str]) -> bool:
    normalized_line = _normalize_label_text(line)
    return any(_normalize_label_text(label) in normalized_line for label in labels)


def _extract_same_line_value(line: str, labels: list[str]) -> str | None:
    for label in labels:
        pattern = re.compile(rf"(?i){re.escape(label)}\s*[:\-]\s*(.+)$")
        match = pattern.search(line)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" :-")
            if value:
                return value
    return None


def _next_non_empty(lines: list[str], start_idx: int) -> str | None:
    for idx in range(start_idx, len(lines)):
        candidate = lines[idx].strip()
        if candidate:
            return candidate
    return None


def _is_label_line(line: str) -> bool:
    if not line.strip():
        return False
    if re.match(r"^\s*[A-Za-z][A-Za-z\s,&()\-/]{2,35}\s*[:.]\s*$", line):
        return True
    lowered = line.lower()
    label_keywords = [
        "name of purchaser",
        "purchaser name",
        "buyer",
        "address",
        "city state",
        "city, state",
        "city. state",
        "from",
        "following reason",
        "date",
        "signature",
        "title",
        "seller",
        "vendor",
    ]
    return any(keyword in lowered for keyword in label_keywords)



def _merge_labels(custom_labels: list[str] | None, default_labels: list[str]) -> list[str]:
    merged = list(default_labels)
    for label in custom_labels or []:
        if label not in merged:
            merged.append(label)
    return merged


def _has_form_code(text: str, code: str) -> bool:
    escaped = re.escape(code.lower())
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text) is not None

def identify_form_type(raw_text: str) -> tuple[FormType, float]:
    """Identify the certificate form type from extracted text."""
    if not raw_text:
        return FormType.UNKNOWN, 0.0

    text = raw_text.lower()
    templates = load_config("form_templates.json").get("forms", {})

    # Strong-signal matches first (explicit form numbers / highly specific wording).
    if _has_form_code(text, "dr-14") or (
        "consumer's certificate of exemption" in text and "florida" in text
    ):
        return FormType.FL_DR_14, 0.98

    if _has_form_code(text, "rev-1220") or (
        "pennsylvania" in text and "exemption" in text and "certificate" in text
    ):
        return FormType.PA_REV_1220, 0.98

    if _has_form_code(text, "01-339"):
        return FormType.TX_01_339, 0.98

    if _has_form_code(text, "stec-b") or _has_form_code(text, "stec b"):
        return FormType.OH_STEC_B, 0.98

    if _has_form_code(text, "ste-1") or (
        "alabama" in text and "exemption certificate" in text and "check proper box" in text
    ):
        return FormType.AL_STE_1, 0.96

    if _has_form_code(text, "st-121") or "exempt use certificate" in text:
        return FormType.NY_ST_121, 0.96

    if (
        "new york state department of taxation and finance" in text
        and "dear sir or madam" in text
        and "governmental entities" in text
    ):
        return FormType.NY_GOV_LETTER, 0.97

    if _has_form_code(text, "st-119.1") or _has_form_code(text, "119.1"):
        return FormType.NY_ST_119_1, 0.96

    best_form = FormType.UNKNOWN
    best_count = 0
    best_total = 1

    for form_name, cfg in templates.items():
        identifiers = cfg.get("identifiers", [])

        if form_name == "NY_ST_119_1" and not (
            _has_form_code(text, "st-119.1") or _has_form_code(text, "119.1")
        ):
            continue

        matched = sum(1 for ident in identifiers if ident and ident.lower() in text)
        if matched == 0:
            continue

        total = len(identifiers) or 1
        candidate = _safe_form_type(form_name)

        if best_form == FormType.UNKNOWN or matched > best_count:
            best_form = candidate
            best_count = matched
            best_total = total
            continue

        if matched == best_count:
            if candidate in {FormType.TX_01_339, FormType.MD_GOV_1, FormType.NY_ST_119_1} and best_form in {
                FormType.MTC_UNIFORM,
                FormType.SST_F0003,
            }:
                best_form = candidate
                best_total = total

    if best_form == FormType.UNKNOWN:
        return FormType.UNKNOWN, 0.0

    confidence = min(1.0, best_count / best_total)

    strong_tokens = {
        FormType.TX_01_339: ["01-339", "form 01-339"],
        FormType.MD_GOV_1: ["gov-1"],
        FormType.SST_F0003: ["f0003"],
        FormType.FEDERAL_SF_1094: ["sf-1094", "standard form 1094"],
    }
    for token in strong_tokens.get(best_form, []):
        if token in text:
            confidence = max(confidence, 0.95)
            break

    if best_count == 1 and "exemption certificate" in text:
        confidence = min(confidence, 0.45)

    return best_form, round(confidence, 3)


def map_llm_form_type(form_type_str: str) -> FormType:
    """Map free-text LLM form type strings to known FormType enum values."""
    if not form_type_str:
        return FormType.UNKNOWN

    normalized = re.sub(r"\s+", " ", form_type_str.strip().lower())

    mappings: list[tuple[FormType, tuple[str, ...]]] = [
        (FormType.TX_01_339, ("01-339", "texas 01-339", "tx 01-339")),
        (FormType.PA_REV_1220, ("rev-1220", "pa rev-1220", "pennsylvania rev-1220")),
        (FormType.NY_ST_121, ("st-121", "ny st-121", "new york st-121", "exempt use certificate")),
        (FormType.FL_DR_14, ("dr-14", "fl dr-14", "florida dr-14")),
        (FormType.OH_STEC_B, ("stec-b", "stec b", "oh stec-b", "ohio stec-b")),
        (FormType.MTC_UNIFORM, ("mtc uniform", "multijurisdictional exemption certificate", "uniform certificate")),
        (FormType.NY_GOV_LETTER, ("ny government letter", "new york government letter")),
        (FormType.FEDERAL_LETTERHEAD, ("federal agency letter", "federal letter", "federal agency")),
        (FormType.SST_F0003, ("sst f0003", "f0003", "streamlined sales tax")),
    ]

    for enum_value, tokens in mappings:
        if any(token in normalized for token in tokens):
            return enum_value

    return FormType.UNKNOWN


def map_llm_entity_type(entity_str: str) -> EntityType:
    """Map LLM entity_type values to EntityType enum values."""
    if not entity_str:
        return EntityType.UNKNOWN

    normalized = entity_str.strip().lower()
    mapping = {
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
    }
    return mapping.get(normalized, EntityType.UNKNOWN)


def _extract_after_labels(raw_text: str, labels: list[str], max_chars: int = 180) -> str | None:
    lines = raw_text.splitlines()

    for idx, line in enumerate(lines):
        if not _line_has_label(line, labels):
            continue

        same_line = _extract_same_line_value(line, labels)
        if same_line:
            return same_line[:max_chars]

        next_line = _next_non_empty(lines, idx + 1)
        if next_line:
            return next_line[:max_chars]

    return None


def _extract_address(raw_text: str, labels: list[str]) -> str | None:
    lines = raw_text.splitlines()

    for i, line in enumerate(lines):
        if not _line_has_label(line, labels):
            continue

        collected: list[str] = []

        same_line = _extract_same_line_value(line, labels)
        if same_line:
            collected.append(same_line)

        for j in range(i + 1, len(lines)):
            nxt = lines[j].strip()
            if not nxt:
                if collected:
                    break
                continue
            if _is_label_line(nxt):
                break
            collected.append(nxt)

        if collected:
            return re.sub(r"\s+", " ", ", ".join(collected).strip(" ,"))

    return None


def _find_date_in_text(raw_text: str, labels: list[str]) -> date | None:
    date_patterns = [
        r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
        r"\d{1,2}\.\d{1,2}\.\d{4}",
        r"\d{4}-\d{2}-\d{2}",
        r"[A-Za-z]+\s+\d{1,2},\s+\d{4}",
        r"\d{1,2}\s+[A-Za-z]+\s+\d{4}",
    ]

    lines = raw_text.splitlines()
    for idx, line in enumerate(lines):
        haystacks = [line]
        if idx + 1 < len(lines):
            haystacks.append(lines[idx + 1])

        if labels and not any(label.lower() in line.lower() for label in labels):
            continue

        for hay in haystacks:
            for pat in date_patterns:
                m = re.search(pat, hay)
                if m:
                    parsed = parse_date(m.group(0))
                    if parsed and date(2010, 1, 1) <= parsed <= date.today():
                        return parsed

    for pat in date_patterns:
        for m in re.finditer(pat, raw_text):
            parsed = parse_date(m.group(0))
            if parsed and date(2010, 1, 1) <= parsed <= date.today():
                return parsed
    return None


def _extract_tax_id(raw_text: str) -> str | None:
    patterns = [
        r"(?i)(?:Tax ID|EIN|FEIN|License\s*#|Permit\s*#|Registration\s*#)\s*[:#-]?\s*([A-Z0-9-]{4,})",
        r"(?i)(?:Account\s*Number|Account\s*#)\s*[:#-]?\s*([A-Z0-9-]{4,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_text)
        if match:
            return match.group(1).strip()
    return None


def _extract_city_state_zip(raw_text: str, labels: list[str]) -> tuple[str | None, str | None, str | None]:
    lines = raw_text.splitlines()
    for idx, line in enumerate(lines):
        if not _line_has_label(line, labels):
            continue

        value = _extract_same_line_value(line, labels) or _next_non_empty(lines, idx + 1)
        if not value:
            continue

        match = re.search(r"^\s*(.+?),\s*([A-Za-z]{2})\s+(\d{5}(?:-\d{4})?)\s*$", value)
        if match:
            city = re.sub(r"\s+", " ", match.group(1)).strip(" ,")
            state = normalize_state(match.group(2))
            postal = match.group(3)
            return city or None, state or None, postal or None

    return None, None, None


def _state_from_form_type(form_type: FormType) -> str | None:
    if form_type in STATE_SPECIFIC_FORM_EXCLUSIONS:
        return None
    match = re.match(r"^([A-Z]{2})_", form_type.name)
    if match:
        return match.group(1)
    return None


def extract_fields_regex(raw_text: str, form_type: FormType) -> ExtractedFields:
    """Extract structured fields from certificate text using label-based parsing."""
    forms = load_config("form_templates.json").get("forms", {})
    template = forms.get(form_type.name, {})
    labels = template.get("field_labels", {})

    fields = ExtractedFields(raw_text=raw_text, form_type_detected=form_type)

    purchaser_name_labels = _merge_labels(labels.get("purchaser_name"), ["Name of purchaser", "Purchaser name", "Buyer"])
    fields.purchaser_name = _extract_after_labels(raw_text, purchaser_name_labels)

    purchaser_addr_labels = _merge_labels(labels.get("purchaser_address"), ["Address of purchaser", "Address"])
    fields.purchaser_address = _extract_address(raw_text, purchaser_addr_labels)

    city_state_labels = _merge_labels(labels.get("purchaser_city_state_zip"), ["City, State", "City. State"])
    purchaser_city, purchaser_state, purchaser_zip = _extract_city_state_zip(raw_text, city_state_labels)
    fields.purchaser_city = purchaser_city
    fields.purchaser_state = purchaser_state
    fields.purchaser_zip = purchaser_zip

    seller_labels = _merge_labels(labels.get("seller_name"), ["Name of seller", "Seller", "Vendor", "from:"])
    fields.seller_name = _extract_after_labels(raw_text, seller_labels)

    reason_labels = _merge_labels(labels.get("exemption_reason"), ["Reason", "Nature of business", "Type of exemption", "following reason:"])
    fields.exemption_reason = _extract_after_labels(raw_text, reason_labels)

    date_labels = _merge_labels(labels.get("cert_date"), ["Date", "Signed", "Effective"])
    fields.cert_date = _find_date_in_text(raw_text, date_labels)

    signature_labels = ["Title", "Signature"]
    signature_hit = any(_line_has_label(line, signature_labels) for line in raw_text.splitlines())
    fields.signature_present = signature_hit or fields.cert_date is not None

    tax_id = _extract_tax_id(raw_text)
    fields.purchaser_tax_id = tax_id
    fields.purchaser_fein = tax_id
    fields.permit_number = tax_id
    fields.account_number = tax_id

    if not fields.purchaser_state and fields.purchaser_address:
        state_match = re.search(r"\b([A-Z]{2})\b\s+\d{5}(?:-\d{4})?", fields.purchaser_address)
        if state_match:
            fields.purchaser_state = normalize_state(state_match.group(1))
        else:
            fields.purchaser_state = normalize_state(fields.purchaser_address)

    if not fields.purchaser_zip and fields.purchaser_address:
        zip_match = re.search(r"\b(\d{5}(?:-\d{4})?)\b", fields.purchaser_address)
        if zip_match:
            fields.purchaser_zip = zip_match.group(1)

    return fields


def extract_exemption_states(raw_text: str, form_type: FormType) -> list[str]:
    """Extract which states the exemption covers."""
    implicit_state = _state_from_form_type(form_type)
    if implicit_state:
        return [implicit_state]

    text = raw_text
    states: set[str] = set()

    checked_pattern = re.compile(r"(?:✓|☒|\[\s*[xX]\s*\]|\bx\b)\s*([A-Z]{2})")
    for match in checked_pattern.finditer(text):
        states.add(match.group(1).upper())

    if form_type in {FormType.MTC_UNIFORM, FormType.SST_F0003}:
        for abbr in re.findall(r"\b[A-Z]{2}\b", text.upper()):
            normalized = normalize_state(abbr)
            if len(normalized) == 2 and normalized.isalpha():
                states.add(normalized)

    return sorted(states)


def parse_certificate(raw_text: str) -> ExtractedFields:
    """Main entry point: identify form + extract all fields."""
    form_type, confidence = identify_form_type(raw_text)
    fields = extract_fields_regex(raw_text, form_type)
    fields.exemption_states = extract_exemption_states(raw_text, form_type)
    fields.form_type_detected = form_type
    fields.extraction_confidence = confidence
    if not fields.raw_text:
        fields.raw_text = raw_text
    return fields
