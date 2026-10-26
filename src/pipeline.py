"""Extract -> transform -> validate -> deduplicate, in memory.

Loading into a database is a separate step; this module never writes anywhere,
which keeps it fast to test. Every input row ends in exactly one bucket:
loaded, rejected (with a reason code), or merged (a duplicate of a loaded row).

Reject-reason precedence, checked in this order (first failure wins):
  accounts: missing_name, invalid_state, invalid_phone, invalid_date
  contacts: missing_email, invalid_email, invalid_phone, orphan_account
Duplicates are only detected among rows that passed validation.
"""
import csv
from collections import Counter

from transforms import normalize_date, normalize_email, normalize_phone, normalize_state
from validators import is_valid_email


class Reject(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _apply(fn, value, reason):
    """Run a transform; convert its ValueError into a coded rejection."""
    try:
        return fn(value)
    except ValueError:
        raise Reject(reason)


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _text(value):
    value = (value or "").strip()
    return value or None


def _build_account(row):
    name = _text(row.get("ACCT_NAME"))
    if name is None:
        raise Reject("missing_name")
    state = _apply(normalize_state, row.get("STATE"), "invalid_state")
    phone = _apply(normalize_phone, row.get("PHONE"), "invalid_phone")
    created = _apply(normalize_date, row.get("CREATED"), "invalid_date")
    return {
        "legacy_id": _text(row.get("ACCT_ID")),
        "name": name,
        "city": _text(row.get("CITY")),
        "state": state,
        "phone": phone,
        "created": created,
    }


def _build_contact(row, loaded_account_ids):
    email = normalize_email(row.get("EMAIL"))
    if email is None:
        raise Reject("missing_email")
    if not is_valid_email(email):
        raise Reject("invalid_email")
    phone = _apply(normalize_phone, row.get("PHONE"), "invalid_phone")
    account_id = _text(row.get("ACCT_ID"))
    if account_id not in loaded_account_ids:
        raise Reject("orphan_account")
    return {
        "legacy_id": _text(row.get("CONTACT_ID")),
        "account_legacy_id": account_id,
        "first_name": _text(row.get("FIRST")),
        "last_name": _text(row.get("LAST")),
        "email": email,
        "phone": phone,
        "title": _text(row.get("TITLE")),
    }


def _process(rows, build, key):
    loaded, rejected, merged = [], [], []
    seen = set()
    for row in rows:
        try:
            record = build(row)
        except Reject as r:
            rejected.append({"row": row, "reason": r.reason})
            continue
        if record[key] in seen:
            merged.append(record)  # duplicate of a row already loaded; first one wins
        else:
            seen.add(record[key])
            loaded.append(record)
    return {"rows_in": len(rows), "loaded": loaded, "rejected": rejected, "merged": merged}


def run(accounts_csv, contacts_csv):
    accounts = _process(_read(accounts_csv), _build_account, key="legacy_id")
    loaded_ids = {a["legacy_id"] for a in accounts["loaded"]}
    contacts = _process(
        _read(contacts_csv), lambda row: _build_contact(row, loaded_ids), key="email")
    return {"accounts": accounts, "contacts": contacts}


def summarize(result):
    """Counts per entity, in the same shape as the generator's expected.json."""
    summary = {}
    for entity in ("accounts", "contacts"):
        r = result[entity]
        summary[entity] = {
            "rows_in": r["rows_in"],
            "loaded": len(r["loaded"]),
            "rejected": len(r["rejected"]),
            "merged": len(r["merged"]),
            "reject_reasons": dict(Counter(x["reason"] for x in r["rejected"])),
        }
    return summary
