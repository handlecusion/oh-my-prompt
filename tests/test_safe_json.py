r"""Tests for the `_safe_json()` helper present in every dashboard.

Each viewer defines its own `_safe_json` because they must remain importable
without `lib/` being on PYTHONPATH; we verify all three share the same
contract: `</` is escaped to `<\/` so a stored prompt cannot break out of
the surrounding inline <script> tag.
"""

import json

import dashboard
import efficiency
import patterns
import suggest_archive

VIEWERS = [
    ("dashboard", dashboard._safe_json),
    ("patterns", patterns._safe_json),
    ("efficiency", efficiency._safe_json),
    ("suggest_archive", suggest_archive._safe_json),
]


def _decode_back(escaped: str):
    r"""The output is JS-safe but should still parse as JSON once `<\/` is undone."""
    return json.loads(escaped.replace("<\\/", "</"))


def test_close_script_is_escaped():
    payload = {"prompt": "evil </script><img src=x onerror=alert(1)>"}
    for name, fn in VIEWERS:
        out = fn(payload)
        assert "</script>" not in out, f"{name} leaked </script>"
        assert "<\\/script>" in out, f"{name} did not escape </"


def test_close_anything_is_escaped():
    for closer in ("</style>", "</a>", "</div>", "</p>"):
        payload = {"x": f"foo{closer}bar"}
        for name, fn in VIEWERS:
            out = fn(payload)
            assert closer not in out, f"{name} leaked {closer}"


def test_round_trips_to_original_data():
    payload = {
        "prompt": "harmless </script> sequence",
        "list": ["a</b>", "c</d>"],
        "nested": {"k": "v</e>"},
    }
    for name, fn in VIEWERS:
        assert _decode_back(fn(payload)) == payload, f"{name} corrupted data"


def test_unicode_preserved():
    payload = {"prompt": "한국어 테스트 </script>"}
    for name, fn in VIEWERS:
        out = fn(payload)
        assert "한국어" in out, f"{name} mangled unicode"
        assert "</script>" not in out
