"""Field-level cleaning functions.

Contract for every function here:
  - empty or missing input -> None   (the field is optional at this stage)
  - cleanable input        -> the normalized value
  - uncleanable input      -> ValueError with a message naming the bad value
The pipeline catches ValueError and records a reject reason; these functions
never guess. Whether a field is *required* is decided later, in validation.
"""
import re
from datetime import datetime

# Assumption (documented in the design doc): all-numeric dates are US month/day/year.
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%d-%b-%Y")

STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}
STATE_CODES = set(STATE_NAMES.values())


def _clean(value):
    """Strip whitespace; return None for None or empty strings."""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def normalize_date(value):
    value = _clean(value)
    if value is None:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date: {value!r}")


def normalize_state(value):
    value = _clean(value)
    if value is None:
        return None
    if value.upper() in STATE_CODES:
        return value.upper()
    code = STATE_NAMES.get(value.lower())
    if code is None:
        raise ValueError(f"unrecognized state: {value!r}")
    return code


def normalize_phone(value):
    value = _clean(value)
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError(f"phone must have 10 digits: {value!r}")
    return f"+1{digits}"


def normalize_email(value):
    value = _clean(value)
    return value.lower() if value else None
