import csv
import json
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from generate_data import main as generate
from loader import get_engine
from migrate import check_balanced, format_report, main
from models import Account, Contact


def prepare(tmp_path):
    """Generate source files; return the base CLI args, db url, out dir, answer key."""
    generate(tmp_path)
    url = f"sqlite:///{(tmp_path / 'target.db').as_posix()}"
    out = tmp_path / "out"
    args = ["--accounts", str(tmp_path / "legacy_accounts.csv"),
            "--contacts", str(tmp_path / "legacy_contacts.csv"),
            "--out", str(out), "--database-url", url]
    expected = json.loads((tmp_path / "expected.json").read_text())
    return args, url, out, expected


def row_count(url, model):
    engine = get_engine(url)
    try:
        with Session(engine) as session:
            return session.scalar(select(func.count()).select_from(model))
    finally:
        engine.dispose()


def test_dry_run_writes_reports_but_no_rows(tmp_path):
    args, url, out, expected = prepare(tmp_path)
    assert main(args + ["--dry-run"]) == 0
    report = json.loads((out / "report.json").read_text())
    assert report["load"]["mode"] == "dry_run"
    assert report["accounts"]["loaded"] == expected["accounts"]["loaded"]
    assert row_count(url, Account) == 0
    assert row_count(url, Contact) == 0


def test_real_run_loads_the_database(tmp_path):
    args, url, out, expected = prepare(tmp_path)
    assert main(args) == 0
    report = json.loads((out / "report.json").read_text())
    assert report["load"]["mode"] == "committed"
    assert row_count(url, Account) == expected["accounts"]["loaded"]
    assert row_count(url, Contact) == expected["contacts"]["loaded"]


def test_rejects_file_has_reason_and_original_columns(tmp_path):
    args, url, out, expected = prepare(tmp_path)
    main(args + ["--dry-run"])
    with open(out / "rejects_contacts.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == expected["contacts"]["rejected"]
    assert "EMAIL" in rows[0] and "ACCT_ID" in rows[0]
    assert dict(Counter(r["reason"] for r in rows)) == expected["contacts"]["reject_reasons"]


def test_rerun_exits_nonzero_and_keeps_data_intact(tmp_path, capsys):
    args, url, out, expected = prepare(tmp_path)
    assert main(args) == 0
    capsys.readouterr()
    assert main(args) == 1
    assert "rolled back" in capsys.readouterr().err
    assert row_count(url, Account) == expected["accounts"]["loaded"]


def test_unbalanced_numbers_are_detected():
    good = {"rows_in": 10, "loaded": 6, "rejected": 3, "merged": 1,
            "reject_reasons": {"x": 3}}
    bad = {**good, "loaded": 5}
    assert check_balanced({"accounts": good}) is True
    assert check_balanced({"accounts": bad}) is False


def test_report_text_shows_the_numbers():
    summary = {"accounts": {"rows_in": 128, "loaded": 114, "rejected": 6, "merged": 8,
                            "reject_reasons": {"missing_name": 6}},
               "contacts": {"rows_in": 4, "loaded": 4, "rejected": 0, "merged": 0,
                            "reject_reasons": {}}}
    text = format_report(summary, "dry_run", {"accounts": 114, "contacts": 4})
    assert "128" in text and "114" in text
    assert "missing_name" in text
    assert "dry run" in text
