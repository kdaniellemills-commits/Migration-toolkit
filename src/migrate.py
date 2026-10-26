"""Command line entry point.

Example:
  python src/migrate.py --accounts data/legacy_accounts.csv \
      --contacts data/legacy_contacts.csv --dry-run

Exit codes: 0 success, 1 load failed and was rolled back, 2 reconciliation
did not balance (nothing is loaded in that case).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from loader import get_engine, load
from pipeline import run, summarize

ENTITIES = ("accounts", "contacts")


def check_balanced(summary):
    """Every input row must land in exactly one bucket, and every reject needs a reason."""
    return all(
        s["rows_in"] == s["loaded"] + s["rejected"] + s["merged"]
        and s["rejected"] == sum(s["reject_reasons"].values())
        for s in summary.values()
    )


def format_report(summary, mode, counts):
    lines = ["RECONCILIATION"]
    for entity in ENTITIES:
        s = summary[entity]
        lines.append(
            f"  {entity:<9} in {s['rows_in']} = loaded {s['loaded']}"
            f" + rejected {s['rejected']} + merged {s['merged']}")
        for reason, n in sorted(s["reject_reasons"].items()):
            lines.append(f"      rejected: {reason} x{n}")
    verb = "would write (dry run, rolled back)" if mode == "dry_run" else "written"
    lines.append(f"DATABASE  {verb}: {counts['accounts']} accounts, {counts['contacts']} contacts")
    return "\n".join(lines)


def write_outputs(result, summary, out_dir, mode, counts):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for entity in ENTITIES:
        rejected = result[entity]["rejected"]
        fieldnames = ["reason"] + (list(rejected[0]["row"]) if rejected else [])
        with open(out / f"rejects_{entity}.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rejected:
                writer.writerow({"reason": r["reason"], **r["row"]})
    report = {**summary, "load": {"mode": mode, **counts}}
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Migrate legacy CRM CSV exports into a database.")
    parser.add_argument("--accounts", required=True, help="accounts CSV export")
    parser.add_argument("--contacts", required=True, help="contacts CSV export")
    parser.add_argument("--out", default="out", help="folder for report and reject files")
    parser.add_argument("--database-url", default=None,
                        help="default: $DATABASE_URL, else sqlite:///migration.db")
    parser.add_argument("--dry-run", action="store_true",
                        help="run everything, then roll the load back")
    args = parser.parse_args(argv)

    result = run(args.accounts, args.contacts)
    summary = summarize(result)
    if not check_balanced(summary):
        print("ERROR: reconciliation does not balance; nothing was loaded.", file=sys.stderr)
        return 2

    engine = get_engine(args.database_url)
    try:
        counts = load(result, engine, dry_run=args.dry_run)
    except IntegrityError as exc:
        print("ERROR: load failed and was rolled back; nothing was written.\n  "
              + str(exc.orig), file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    mode = "dry_run" if args.dry_run else "committed"
    write_outputs(result, summary, args.out, mode, counts)
    print(format_report(summary, mode, counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
