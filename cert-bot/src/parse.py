import re
from datetime import date

from .models import ExtractedFields, FormType
from .utils import load_config, normalize_state, parse_date


def _safe_form_type(name: str) -> FormType:
    try:
        return FormType[name]
    except KeyError:
        return FormType.UNKNOWN


def _compile_label_pattern(label: str) -> re.Pattern[str]:
    return re.compile(rf"(?i){re.escape(label)}\s*[:\-]?\s*(.+)")


def identify_form_type(raw_text: str) -> tuple[FormType, float]:
    """Identify the certificate form type from extracted text."""
    if not raw_text:
        return FormType.UNKNOWN, 0.0

    text = raw_text.lower()
    templates = load_config("form_templates.json").get("forms", {})

    best_form = FormType.UNKNOWN
    best_count = 0
    best_total = 1

    for form_name, cfg in templates.items():
        identifiers = cfg.get("identifiers", [])
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


def _extract_after_labels(raw_text: str, labels: list[str], max_chars: int = 180) -> str | None:
    for label in labels:
        pattern = _compile_label_pattern(label)
        for line in raw_text.splitlines():
            match = pattern.search(line)
            if match:
                value = re.sub(r"\s+", " ", match.group(1)).strip(" :-")
                if value:
                    return value[:max_chars]

    all_lines = raw_text.splitlines()
    for idx, line in enumerate(all_lines):
        line_lower = line.lower()
        for label in labels:
            if label.lower() in line_lower and idx + 1 < len(all_lines):
                nxt = all_lines[idx + 1].strip()
                if nxt and len(nxt) <= max_chars:
                    return nxt
    return None


def _extract_address(raw_text: str, labels: list[str]) -> str | None:
    lines = raw_text.splitlines()
    for i, line in enumerate(lines):
        low = line.lower()
        if any(label.lower() in low for label in labels):
            possible = []
            tail = re.split(r":", line, maxsplit=1)
            if len(tail) == 2 and tail[1].strip():
                possible.append(tail[1].strip())
            for j in range(i + 1, min(i + 4, len(lines))):
                nxt = lines[j].strip()
                if not nxt:
                    break
                if re.search(r"(date|signature|seller|purchaser|reason)", nxt, flags=re.I):
                    break
                possible.append(nxt)
            value = ", ".join(possible).strip(" ,")
            if value:
                return re.sub(r"\s+", " ", value)
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
    for line in lines:
        if labels and not any(label.lower() in line.lower() for label in labels):
            continue
        for pat in date_patterns:
            m = re.search(pat, line)
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


def extract_fields_regex(raw_text: str, form_type: FormType) -> ExtractedFields:
    """Extract structured fields from certificate text using label-based parsing."""
    forms = load_config("form_templates.json").get("forms", {})
    template = forms.get(form_type.name, {})
    labels = template.get("field_labels", {})

    fields = ExtractedFields(raw_text=raw_text, form_type_detected=form_type)

    purchaser_name_labels = labels.get("purchaser_name", ["Name of purchaser", "Purchaser", "Buyer"])
    fields.purchaser_name = _extract_after_labels(raw_text, purchaser_name_labels)

    purchaser_addr_labels = labels.get("purchaser_address", ["Address of purchaser", "Address"])
    fields.purchaser_address = _extract_address(raw_text, purchaser_addr_labels)

    seller_labels = labels.get("seller_name", ["Name of seller", "Seller", "Vendor"])
    fields.seller_name = _extract_after_labels(raw_text, seller_labels)

    reason_labels = labels.get("exemption_reason", ["Reason", "Nature of business", "Type of exemption"])
    fields.exemption_reason = _extract_after_labels(raw_text, reason_labels)

    date_labels = labels.get("cert_date", ["Date", "Signed", "Effective"])
    fields.cert_date = _find_date_in_text(raw_text, date_labels)

    tax_id = _extract_tax_id(raw_text)
    fields.purchaser_tax_id = tax_id
    fields.purchaser_fein = tax_id
    fields.permit_number = tax_id
    fields.account_number = tax_id

    if fields.purchaser_address:
        state_match = re.search(r"\b([A-Z]{2})\b\s+\d{5}(?:-\d{4})?", fields.purchaser_address)
        if state_match:
            fields.purchaser_state = normalize_state(state_match.group(1))
        else:
            fields.purchaser_state = normalize_state(fields.purchaser_address)

    return fields


def extract_exemption_states(raw_text: str, form_type: FormType) -> list[str]:
    """Extract which states the exemption covers."""
    implicit_state_by_form = {
        FormType.TX_01_339: "TX",
        FormType.MD_GOV_1: "MD",
        FormType.MD_NONGOV_1: "MD",
        FormType.FL_DR_14: "FL",
        FormType.NY_ST_119_1: "NY",
    }
    if form_type in implicit_state_by_form:
        return [implicit_state_by_form[form_type]]

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
