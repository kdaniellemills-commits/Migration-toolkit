import csv
import json

from generate_data import main as generate
from pipeline import run, summarize

ACCT_HEADER = ["ACCT_ID", "ACCT_NAME", "CITY", "STATE", "PHONE", "CREATED"]
CONTACT_HEADER = ["CONTACT_ID", "ACCT_ID", "FIRST", "LAST", "EMAIL", "PHONE", "TITLE"]


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def make_small(tmp_path, accounts, contacts):
    a, c = tmp_path / "a.csv", tmp_path / "c.csv"
    write_csv(a, ACCT_HEADER, accounts)
    write_csv(c, CONTACT_HEADER, contacts)
    return run(a, c)


def reasons(result, entity):
    return [r["reason"] for r in result[entity]["rejected"]]


GOOD_ACCT = ["A1", "Acme LLC", "Houston", "Texas", "(713) 555-0142", "03/04/2021"]


def test_clean_rows_load_and_are_normalized(tmp_path):
    result = make_small(tmp_path, [GOOD_ACCT], [
        ["C1", "A1", "Ava", "Reyes", " Ava@Example.com ", "713-555-0199", "Owner"],
    ])
    acct = result["accounts"]["loaded"][0]
    assert acct["state"] == "TX"
    assert acct["created"] == "2021-03-04"
    assert acct["phone"] == "+17135550142"
    contact = result["contacts"]["loaded"][0]
    assert contact["email"] == "ava@example.com"


def test_account_without_name_is_rejected(tmp_path):
    result = make_small(tmp_path, [["A1", "  ", "Houston", "TX", "", ""]], [])
    assert reasons(result, "accounts") == ["missing_name"]


def test_bad_account_fields_get_specific_reasons(tmp_path):
    result = make_small(tmp_path, [
        ["A1", "One", "", "Narnia", "", ""],
        ["A2", "Two", "", "TX", "123", ""],
        ["A3", "Three", "", "TX", "", "garbage"],
    ], [])
    assert reasons(result, "accounts") == ["invalid_state", "invalid_phone", "invalid_date"]


def test_duplicate_accounts_keep_first_and_count_merged(tmp_path):
    result = make_small(tmp_path, [GOOD_ACCT, GOOD_ACCT], [])
    assert len(result["accounts"]["loaded"]) == 1
    assert len(result["accounts"]["merged"]) == 1


def test_contact_reject_reasons(tmp_path):
    result = make_small(tmp_path, [GOOD_ACCT], [
        ["C1", "A1", "A", "B", "", "", ""],                    # missing email
        ["C2", "A1", "A", "B", "no-at-sign", "", ""],          # invalid email
        ["C3", "A1", "A", "B", "ok@example.com", "12", ""],    # invalid phone
        ["C4", "A9", "A", "B", "x@example.com", "", ""],       # account never existed
    ])
    assert reasons(result, "contacts") == [
        "missing_email", "invalid_email", "invalid_phone", "orphan_account"]


def test_email_problem_wins_over_orphan(tmp_path):
    # Precedence is documented: email checks run before the orphan check.
    result = make_small(tmp_path, [GOOD_ACCT], [
        ["C1", "A9", "A", "B", "", "", ""],
    ])
    assert reasons(result, "contacts") == ["missing_email"]


def test_contact_of_rejected_account_is_orphan(tmp_path):
    result = make_small(tmp_path, [["A1", "", "", "", "", ""]], [
        ["C1", "A1", "A", "B", "ok@example.com", "", ""],
    ])
    assert reasons(result, "contacts") == ["orphan_account"]


def test_duplicate_contacts_merge_on_normalized_email(tmp_path):
    result = make_small(tmp_path, [GOOD_ACCT], [
        ["C1", "A1", "A", "B", "ava@example.com", "", ""],
        ["C2", "A1", "A", "B", "  AVA@EXAMPLE.COM ", "", ""],
    ])
    assert len(result["contacts"]["loaded"]) == 1
    assert len(result["contacts"]["merged"]) == 1


def test_every_input_row_is_accounted_for(tmp_path):
    generate(tmp_path)
    result = run(tmp_path / "legacy_accounts.csv", tmp_path / "legacy_contacts.csv")
    for entity in ("accounts", "contacts"):
        r = summarize(result)[entity]
        assert r["rows_in"] == r["loaded"] + r["rejected"] + r["merged"]


def test_pipeline_matches_ground_truth(tmp_path):
    """The key test: results must equal the answer key decided at data-creation time."""
    generate(tmp_path)
    expected = json.loads((tmp_path / "expected.json").read_text())
    result = run(tmp_path / "legacy_accounts.csv", tmp_path / "legacy_contacts.csv")
    summary = summarize(result)
    assert summary["accounts"] == expected["accounts"]
    assert summary["contacts"] == expected["contacts"]
