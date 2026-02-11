import json
import re
from datetime import date, datetime
from pathlib import Path


_STATE_MAP = {
    "AL": "AL",
    "ALABAMA": "AL",
    "AK": "AK",
    "ALASKA": "AK",
    "AZ": "AZ",
    "ARIZONA": "AZ",
    "AR": "AR",
    "ARKANSAS": "AR",
    "CA": "CA",
    "CALIFORNIA": "CA",
    "CO": "CO",
    "COLORADO": "CO",
    "CT": "CT",
    "CONNECTICUT": "CT",
    "DE": "DE",
    "DELAWARE": "DE",
    "DC": "DC",
    "DISTRICT OF COLUMBIA": "DC",
    "FL": "FL",
    "FLORIDA": "FL",
    "GA": "GA",
    "GEORGIA": "GA",
    "HI": "HI",
    "HAWAII": "HI",
    "ID": "ID",
    "IDAHO": "ID",
    "IL": "IL",
    "ILLINOIS": "IL",
    "IN": "IN",
    "INDIANA": "IN",
    "IA": "IA",
    "IOWA": "IA",
    "KS": "KS",
    "KANSAS": "KS",
    "KY": "KY",
    "KENTUCKY": "KY",
    "LA": "LA",
    "LOUISIANA": "LA",
    "ME": "ME",
    "MAINE": "ME",
    "MD": "MD",
    "MARYLAND": "MD",
    "MA": "MA",
    "MASSACHUSETTS": "MA",
    "MI": "MI",
    "MICHIGAN": "MI",
    "MN": "MN",
    "MINNESOTA": "MN",
    "MS": "MS",
    "MISSISSIPPI": "MS",
    "MO": "MO",
    "MISSOURI": "MO",
    "MT": "MT",
    "MONTANA": "MT",
    "NE": "NE",
    "NEBRASKA": "NE",
    "NV": "NV",
    "NEVADA": "NV",
    "NH": "NH",
    "NEW HAMPSHIRE": "NH",
    "NJ": "NJ",
    "NEW JERSEY": "NJ",
    "NM": "NM",
    "NEW MEXICO": "NM",
    "NY": "NY",
    "NEW YORK": "NY",
    "NC": "NC",
    "NORTH CAROLINA": "NC",
    "ND": "ND",
    "NORTH DAKOTA": "ND",
    "OH": "OH",
    "OHIO": "OH",
    "OK": "OK",
    "OKLAHOMA": "OK",
    "OR": "OR",
    "OREGON": "OR",
    "PA": "PA",
    "PENNSYLVANIA": "PA",
    "RI": "RI",
    "RHODE ISLAND": "RI",
    "SC": "SC",
    "SOUTH CAROLINA": "SC",
    "SD": "SD",
    "SOUTH DAKOTA": "SD",
    "TN": "TN",
    "TENNESSEE": "TN",
    "TX": "TX",
    "TEXAS": "TX",
    "UT": "UT",
    "UTAH": "UT",
    "VT": "VT",
    "VERMONT": "VT",
    "VA": "VA",
    "VIRGINIA": "VA",
    "WA": "WA",
    "WASHINGTON": "WA",
    "WV": "WV",
    "WEST VIRGINIA": "WV",
    "WI": "WI",
    "WISCONSIN": "WI",
    "WY": "WY",
    "WYOMING": "WY",
    # Common typos/variants
    "PENNSYLVANIAA": "PA",
    "TENNESEE": "TN",
    "MASS": "MA",
    "ILL": "IL",
}


def load_config(config_name: str) -> dict:
    """
    Load a JSON config file from the config/ directory.

    Args:
        config_name: filename (e.g., "state_rules.json")
    Returns:
        Parsed JSON as dict
    """
    config_dir = Path(__file__).parent.parent / "config"
    with open(config_dir / config_name) as f:
        return json.load(f)


def normalize_state(state_input: str) -> str:
    """
    Normalize state input to 2-letter abbreviation.
    Handles: full name ("Texas" → "TX"), abbreviation ("tx" → "TX"),
    common typos, and state names in addresses.
    """
    if not state_input:
        return ""

    normalized = state_input.strip().upper().replace(".", "")

    if normalized in _STATE_MAP:
        return _STATE_MAP[normalized]

    # Handle state names in address strings (e.g. "Austin, Texas 78701")
    for key, abbreviation in _STATE_MAP.items():
        if len(key) > 2 and key in normalized:
            return abbreviation

    return normalized[:2] if len(normalized) >= 2 else normalized


def parse_date(date_str: str) -> date | None:
    """
    Parse a date string in common tax-form formats.

    Returns None if parsing fails or year is outside 2000..(current year + 1).
    """
    if not date_str:
        return None

    value = date_str.strip()
    if not value:
        return None

    formats = [
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%m.%d.%Y",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]

    parsed: date | None = None
    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt).date()
            break
        except ValueError:
            continue

    if parsed is None:
        two_digit = re.fullmatch(r"\s*(\d{1,2})[\/-](\d{1,2})[\/-](\d{2})\s*", value)
        if two_digit:
            month = int(two_digit.group(1))
            day = int(two_digit.group(2))
            yy = int(two_digit.group(3))
            year = 2000 + yy if yy <= 30 else 1900 + yy
            try:
                parsed = date(year, month, day)
            except ValueError:
                return None

    if parsed is None:
        return None

    current_year = datetime.utcnow().year
    if parsed.year < 2000 or parsed.year > current_year + 1:
        return None

    return parsed
