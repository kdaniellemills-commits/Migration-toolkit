import pytest

from validators import is_valid_email


@pytest.mark.parametrize("email", [
    "ava.reyes@example.com",
    "a@b.co",
    "first.last+tag@sub.example.org",
])
def test_valid_emails(email):
    assert is_valid_email(email) is True


@pytest.mark.parametrize("email", [
    "ava.reyes.example.com",   # no @
    "@example.com",            # nothing before @
    "ava@",                    # nothing after @
    "ava@example",             # no dot in domain
    "ava reyes@example.com",   # space
    "a@@b.com",                # two @
    "",
])
def test_invalid_emails(email):
    assert is_valid_email(email) is False
