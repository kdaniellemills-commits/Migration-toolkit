"""Generate a messy, synthetic 'legacy CRM' export plus a ground-truth answer key.

Every row's fate (loaded / rejected / merged) is decided when the row is created,
so expected.json does not depend on the migration pipeline we test later.
All data is fictional. Output is deterministic for a given seed.
"""
import csv
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

SEED = 42
N_ACCOUNTS = 120          # unique accounts in the source
N_MISSING_NAME = 6        # accounts with no name -> rejected
N_DUP_ACCOUNTS = 8        # valid accounts that appear twice -> merged
N_ORPHAN_CONTACTS = 5     # contacts pointing at accounts that do not exist

STATES = {
    "TX": "Texas", "CA": "California", "NY": "New York", "FL": "Florida",
    "IL": "Illinois", "WA": "Washington", "CO": "Colorado", "GA": "Georgia",
}
CITIES = ["Houston", "Austin", "Dallas", "Denver", "Seattle", "Chicago", "Atlanta", "Miami"]
WORDS_A = ["Summit", "Harbor", "Pioneer", "Northwind", "Bluebird", "Ironwood", "Crescent", "Atlas"]
WORDS_B = ["Logistics", "Dental", "Foods", "Robotics", "Capital", "Supply", "Health", "Media"]
SUFFIXES = ["LLC", "Inc", "Co", "Group"]
FIRST = ["Ava", "Liam", "Noah", "Mia", "Zoe", "Eli", "Ivy", "Leo", "Nia", "Omar"]
LAST = ["Reyes", "Chen", "Patel", "Nguyen", "Brooks", "Kim", "Singh", "Lopez", "Davis", "Ward"]
TITLES = ["Owner", "Office Manager", "Controller", "IT Lead", "Operations Director"]
DOMAINS = ["example.com", "example.org", "example.net"]


def messy_date(rng, d):
    """Return the same date in one of several formats."""
    fmt = rng.choice(["iso", "us", "long", "dmy"])
    if fmt == "iso":
        return d.strftime("%Y-%m-%d")
    if fmt == "us":
        return d.strftime("%m/%d/%Y")
    if fmt == "long":
        return d.strftime("%b %d, %Y")
    return d.strftime("%d-%b-%Y")


def messy_state(rng, abbr):
    style = rng.choice(["abbr", "full", "lower", "padded"])
    if style == "abbr":
        return abbr
    if style == "full":
        return STATES[abbr]
    if style == "lower":
        return abbr.lower()
    return f" {abbr} "


def messy_phone(rng, digits):
    style = rng.choice(["dash", "paren", "dots", "plain"])
    a, b, c = digits[:3], digits[3:6], digits[6:]
    if style == "dash":
        return f"{a}-{b}-{c}"
    if style == "paren":
        return f"({a}) {b}-{c}"
    if style == "dots":
        return f"{a}.{b}.{c}"
    return digits


def messy_email(rng, email):
    style = rng.choice(["same", "upper", "padded"])
    if style == "upper":
        return email.upper()
    if style == "padded":
        return f"  {email}  "
    return email


def main(out_dir):
    rng = random.Random(SEED)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ---- accounts: decide each account's fate up front ----
    account_ids = [f"A{i:04d}" for i in range(1, N_ACCOUNTS + 1)]
    missing_name_ids = set(rng.sample(account_ids, N_MISSING_NAME))
    valid_ids = [a for a in account_ids if a not in missing_name_ids]
    dup_ids = set(rng.sample(valid_ids, N_DUP_ACCOUNTS))

    account_rows = []
    used_names = set()
    for acct_id in account_ids:
        while True:
            name = f"{rng.choice(WORDS_A)} {rng.choice(WORDS_B)} {rng.choice(SUFFIXES)}"
            if name not in used_names:
                used_names.add(name)
                break
        abbr = rng.choice(list(STATES))
        city = rng.choice(CITIES)
        digits = "".join(rng.choice("0123456789") for _ in range(10))
        created = date(2018, 1, 1) + timedelta(days=rng.randint(0, 2500))

        def make_row():
            return {
                "ACCT_ID": acct_id,
                "ACCT_NAME": "" if acct_id in missing_name_ids else name,
                "CITY": city,
                "STATE": messy_state(rng, abbr),
                "PHONE": messy_phone(rng, digits),
                "CREATED": messy_date(rng, created),
            }

        account_rows.append(make_row())
        if acct_id in dup_ids:
            account_rows.append(make_row())  # same account exported twice

    rng.shuffle(account_rows)

    # ---- contacts: decide each contact's fate up front ----
    contact_rows = []
    counters = {"ok": 0, "missing_email": 0, "invalid_email": 0,
                "orphan_account": 0, "merged": 0}
    n = 0

    def add_contact(acct_id, fate):
        nonlocal n
        n += 1
        first, last = rng.choice(FIRST), rng.choice(LAST)
        clean_email = f"{first}.{last}{n}@{rng.choice(DOMAINS)}".lower()
        digits = "".join(rng.choice("0123456789") for _ in range(10))
        if fate == "missing_email":
            email = ""
        elif fate == "invalid_email":
            email = clean_email.replace("@", "")  # no @ sign
        else:
            email = messy_email(rng, clean_email)
        row = {
            "CONTACT_ID": f"C{n:05d}",
            "ACCT_ID": acct_id,
            "FIRST": first,
            "LAST": last,
            "EMAIL": email,
            "PHONE": messy_phone(rng, digits),
            "TITLE": rng.choice(TITLES),
        }
        contact_rows.append(row)
        counters[fate if fate != "ok" else "ok"] += 1
        return clean_email

    ok_contacts = []  # (acct_id, clean_email) eligible to be duplicated
    for acct_id in account_ids:
        for _ in range(rng.randint(1, 4)):
            if acct_id in missing_name_ids:
                # account will be rejected, so its contacts become orphans
                add_contact(acct_id, "orphan_account")
            else:
                fate = rng.choices(
                    ["ok", "missing_email", "invalid_email"], weights=[88, 6, 6])[0]
                clean = add_contact(acct_id, fate)
                if fate == "ok":
                    ok_contacts.append((acct_id, clean))

    for i in range(N_ORPHAN_CONTACTS):
        add_contact(f"A9{i:03d}", "orphan_account")  # accounts that never existed

    # duplicate some valid contacts: same person, re-exported with new CONTACT_ID
    for acct_id, clean in rng.sample(ok_contacts, 10):
        n += 1
        first, last = clean.split("@")[0].split(".")[0].title(), rng.choice(LAST)
        contact_rows.append({
            "CONTACT_ID": f"C{n:05d}", "ACCT_ID": acct_id,
            "FIRST": first, "LAST": last,
            "EMAIL": messy_email(rng, clean),
            "PHONE": messy_phone(rng, "".join(rng.choice("0123456789") for _ in range(10))),
            "TITLE": rng.choice(TITLES),
        })
        counters["merged"] += 1

    rng.shuffle(contact_rows)

    # ---- write files ----
    with open(out / "legacy_accounts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(account_rows[0]))
        w.writeheader()
        w.writerows(account_rows)
    with open(out / "legacy_contacts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(contact_rows[0]))
        w.writeheader()
        w.writerows(contact_rows)

    expected = {
        "seed": SEED,
        "accounts": {
            "rows_in": len(account_rows),
            "loaded": N_ACCOUNTS - N_MISSING_NAME,
            "rejected": N_MISSING_NAME,
            "merged": N_DUP_ACCOUNTS,
            "reject_reasons": {"missing_name": N_MISSING_NAME},
        },
        "contacts": {
            "rows_in": len(contact_rows),
            "loaded": counters["ok"],
            "rejected": counters["missing_email"] + counters["invalid_email"]
                        + counters["orphan_account"],
            "merged": counters["merged"],
            "reject_reasons": {
                "missing_email": counters["missing_email"],
                "invalid_email": counters["invalid_email"],
                "orphan_account": counters["orphan_account"],
            },
        },
    }
    with open(out / "expected.json", "w", encoding="utf-8") as f:
        json.dump(expected, f, indent=2)

    for entity in ("accounts", "contacts"):
        e = expected[entity]
        assert e["rows_in"] == e["loaded"] + e["rejected"] + e["merged"], entity
        assert e["rejected"] == sum(e["reject_reasons"].values()), entity
    print(json.dumps(expected, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data")
