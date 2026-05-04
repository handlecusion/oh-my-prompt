"""Tests for lib/_tmp.py:omp_tmpdir() — per-uid dir creation + 7-day prune."""

import os
import tempfile
import time
from pathlib import Path

import pytest

import _tmp


@pytest.fixture
def isolated_tmp(tmp_path, monkeypatch):
    """Redirect `tempfile.gettempdir()` for this test run only."""
    monkeypatch.setattr(_tmp.tempfile, "gettempdir", lambda: str(tmp_path))
    return tmp_path


def test_creates_dir_with_correct_perms(isolated_tmp):
    d = _tmp.omp_tmpdir()
    assert d.exists()
    assert d.is_dir()
    # Owner-only on POSIX; on Windows mode bits are advisory and we just check exists.
    if os.name == "posix":
        assert (d.stat().st_mode & 0o777) == 0o700


def test_prunes_files_older_than_seven_days(isolated_tmp):
    d = _tmp.omp_tmpdir()
    # Plant one ancient file, one fresh file.
    old_file = d / "old.html"
    fresh_file = d / "fresh.html"
    old_file.write_text("old")
    fresh_file.write_text("fresh")
    eight_days_ago = time.time() - (8 * 24 * 60 * 60)
    os.utime(old_file, (eight_days_ago, eight_days_ago))

    # Re-call should trigger a prune.
    _tmp.omp_tmpdir()

    assert not old_file.exists(), "8-day-old file should have been pruned"
    assert fresh_file.exists(), "fresh file must survive the prune"


def test_keeps_files_just_under_cutoff(isolated_tmp):
    d = _tmp.omp_tmpdir()
    six_days_ago = time.time() - (6 * 24 * 60 * 60)
    f = d / "six_days.html"
    f.write_text("x")
    os.utime(f, (six_days_ago, six_days_ago))

    _tmp.omp_tmpdir()

    assert f.exists(), "files newer than 7 days must NOT be pruned"


def test_dir_is_per_uid(isolated_tmp):
    d = _tmp.omp_tmpdir()
    expected_uid = getattr(os, "getuid", lambda: 0)()
    assert d.name == f"omp-{expected_uid}"


def test_idempotent_on_existing_dir(isolated_tmp):
    d1 = _tmp.omp_tmpdir()
    d1.joinpath("keep.txt").write_text("keep")
    d2 = _tmp.omp_tmpdir()
    assert d1 == d2
    assert d2.joinpath("keep.txt").exists()


def test_prune_survives_unreadable_subdir(isolated_tmp):
    """A directory inside the tempdir should not crash the prune (files only)."""
    d = _tmp.omp_tmpdir()
    (d / "subdir").mkdir()
    # No exception means we pass.
    _tmp.omp_tmpdir()
