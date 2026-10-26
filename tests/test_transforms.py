import pytest

from transforms import normalize_date, normalize_email, normalize_phone, normalize_state


# ---------- dates ----------
@pytest.mark.parametrize("raw", [
    "2021-03-04",       # ISO
    "03/04/2021",       # US month/day/year
    "Mar 04, 2021",     # short month name
    "04-Mar-2021",      # day-month-year
    "  2021-03-04  ",   # surrounding whitespace
])
def test_date_formats_become_iso(raw):
    assert normalize_date(raw) == "2021-03-04"


def test_date_handles_leap_day():
    assert normalize_date("Feb 29, 2020") == "2020-02-29"


@pytest.mark.parametrize("raw", ["02/30/2021", "not a date", "13/45/2021"])
def test_date_invalid_raises(raw):
    with pytest.raises(ValueError):
        normalize_date(raw)


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_date_empty_returns_none(raw):
    assert normalize_date(raw) is None


# ---------- states ----------
@pytest.mark.parametrize("raw", ["TX", "tx", " TX ", "Texas", "texas", "TEXAS"])
def test_state_variants_become_code(raw):
    assert normalize_state(raw) == "TX"


def test_state_multiword_name():
    assert normalize_state("New York") == "NY"
    assert normalize_state(" new york ") == "NY"


def test_state_unknown_raises():
    with pytest.raises(ValueError):
        normalize_state("Narnia")


@pytest.mark.parametrize("raw", ["", "  ", None])
def test_state_empty_returns_none(raw):
    assert normalize_state(raw) is None


# ---------- phones ----------
@pytest.mark.parametrize("raw", [
    "713-555-0142",
    "(713) 555-0142",
    "713.555.0142",
    "7135550142",
    "+1 713 555 0142",
    "1-713-555-0142",
])
def test_phone_formats_become_e164(raw):
    assert normalize_phone(raw) == "+17135550142"


@pytest.mark.parametrize("raw", ["555-0142", "12345", "713-555-01423"])
def test_phone_wrong_length_raises(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)


@pytest.mark.parametrize("raw", ["", "  ", None])
def test_phone_empty_returns_none(raw):
    assert normalize_phone(raw) is None


# ---------- emails ----------
def test_email_trimmed_and_lowercased():
    assert normalize_email("  Ava.Reyes@EXAMPLE.com ") == "ava.reyes@example.com"


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_email_empty_returns_none(raw):
    assert normalize_email(raw) is None


def test_email_does_not_validate():
    # Validation is a separate pipeline step. Normalizing must not reject or "fix" it.
    assert normalize_email("  NOT-AN-EMAIL ") == "not-an-email"
