"""Validation rules. Pure checks only; they never modify data."""
import re

# Deliberately simple: one @, something before it, a dotted domain, no spaces.
# Full RFC 5322 validation is out of scope and not needed for a CRM migration.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


def is_valid_email(email):
    return bool(_EMAIL_RE.match(email))
