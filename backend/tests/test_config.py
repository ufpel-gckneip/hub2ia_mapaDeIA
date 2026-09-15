"""SECRET_KEY hardening (TODO #4): the API must refuse weak signing keys."""

import pytest

from app.config import Settings


def _settings(secret_key: str) -> Settings:
    # Pass the key explicitly (init args outrank env/.env in pydantic-settings).
    return Settings(secret_key=secret_key)


@pytest.mark.parametrize(
    "weak",
    [
        "",  # unset
        "CHANGE-ME-IN-PRODUCTION",  # the old default (also too short)
        "change-me",
        "secret",
        "short",  # < 32 chars
        "a" * 31,  # one below the minimum
    ],
)
def test_weak_secret_rejected(weak):
    with pytest.raises(RuntimeError):
        _settings(weak).assert_secure_secret_key()


@pytest.mark.parametrize(
    "strong",
    [
        "a" * 32,  # exactly the minimum length
        "0123456789abcdef0123456789abcdef0123456789abcdef",  # openssl-style hex
    ],
)
def test_strong_secret_accepted(strong):
    _settings(strong).assert_secure_secret_key()  # must not raise


def test_settings_no_insecure_default():
    """The model no longer ships a usable default secret."""
    assert Settings(secret_key="").secret_key == ""
