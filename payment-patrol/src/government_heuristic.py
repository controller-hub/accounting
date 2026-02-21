from __future__ import annotations

import re

from .models import GovernmentHeuristicResult


HIGH_PATTERNS = [
    r"\bcity of\b", r"\bcounty of\b", r"\btown of\b", r"\bvillage of\b", r"\bborough of\b",
    r"\btownship of\b", r"\bstate of\b", r"\bcommonwealth of\b", r"\bdepartment of\b",
    r"\bpublic works\b", r"\bwater district\b", r"\bschool district\b", r"\bisd\b",
    r"\btransit authority\b", r"\bhousing authority\b", r"\bport authority\b", r"\bfire district\b",
    r"\bsanitation district\b", r"\buniversity of\b", r"\bus army\b", r"\bus navy\b",
    r"\bus air force\b", r"\bus marine\b", r"\bcoast guard\b", r"\bdepartment of defense\b",
    r"\bva\b", r"\bbureau of\b", r"\bnational guard\b", r"\badministration\b", r"\bmunicipal\b",
]
MEDIUM_PATTERNS = [r"\bauthority\b", r"\bdistrict\b", r"\bcommission\b", r"\bboard of education\b", r"\bcommunity college\b", r"\btribal\b"]


def classify_government_name(customer_name: str) -> GovernmentHeuristicResult:
    name = customer_name.strip()
    for pattern in HIGH_PATTERNS:
        if re.search(pattern, name, flags=re.IGNORECASE):
            return GovernmentHeuristicResult(is_government=True, confidence="high", matched_pattern=pattern)

    for pattern in MEDIUM_PATTERNS:
        if re.search(pattern, name, flags=re.IGNORECASE):
            return GovernmentHeuristicResult(is_government=True, confidence="medium", matched_pattern=pattern)

    return GovernmentHeuristicResult(is_government=False, confidence="none", matched_pattern=None)
