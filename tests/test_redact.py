"""Tests for hooks/_db.py:redact() — known-shape secret masking."""

from _db import redact


def test_anthropic_key_masked():
    s = "Here is my key: sk-ant-1234567890abcdefghijklmnopqr and continue"
    out = redact(s)
    assert "sk-ant-" not in out
    assert "[REDACTED:anthropic-or-openai-key]" in out
    assert "Here is my key:" in out and "and continue" in out


def test_openai_key_masked():
    s = "key=sk-1234567890abcdefghijklmnopqrstuv done"
    out = redact(s)
    assert "sk-1234" not in out
    assert "[REDACTED:anthropic-or-openai-key]" in out


def test_slack_token_masked():
    for token in ("xoxb-1234567890-abc", "xoxp-1234567890-abc", "xoxa-1234567890-abc"):
        out = redact(f"token={token}")
        assert token not in out
        assert "[REDACTED:slack-token]" in out


def test_github_token_masked():
    out = redact("Use ghp_abcdefghijklmnopqrstuvwxyz0123456789")
    assert "ghp_" not in out
    assert "[REDACTED:github-token]" in out


def test_github_pat_masked():
    out = redact("token=github_pat_11AAAAAAA0123456789012_abcdef")
    assert "github_pat_" not in out
    assert "[REDACTED:github-pat]" in out


def test_aws_access_key_masked():
    out = redact("AWS=AKIAIOSFODNN7EXAMPLE end")
    assert "AKIAIOSFODNN7EXAMPLE" not in out
    assert "[REDACTED:aws-access-key]" in out


def test_google_api_key_masked():
    out = redact("AIzaSyD-9tSrke72PouQMnMX-a7eZSW0jkFMBWY8")
    assert "AIzaSy" not in out
    assert "[REDACTED:google-api-key]" in out


def test_jwt_masked():
    jwt = (
        "eyJhbGciOiJIUzI1NiJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    out = redact(f"Authorization: Bearer {jwt}")
    assert jwt not in out
    assert "[REDACTED:jwt]" in out


def test_plain_text_untouched():
    s = "This is just normal text with no secrets in it at all."
    assert redact(s) == s


def test_empty_input():
    assert redact("") == ""
    assert redact(None) is None  # type: ignore[arg-type]


def test_multiple_secrets_in_one_string():
    s = "key1=sk-ant-1234567890abcdefghijklmnopqr key2=ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    out = redact(s)
    assert "sk-ant-" not in out
    assert "ghp_" not in out
    assert out.count("[REDACTED:") == 2
