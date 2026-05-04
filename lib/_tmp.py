"""Per-user temp directory for omp dashboards + automatic stale-file pruning.

Centralizes what was previously inlined in each viewer. Two reasons:
- avoids the predictable-name symlink-overwrite race on shared /tmp (Linux)
- prunes stale dashboard re-renders and one-shot suggest_prep input files so
  the directory does not grow unbounded over time
"""

import os
import tempfile
import time
from pathlib import Path

_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 7 days


def omp_tmpdir() -> Path:
    """Return $TMPDIR/omp-<uid>/ (created 0700 if missing) and prune stale files."""
    base = Path(tempfile.gettempdir())
    uid = getattr(os, "getuid", lambda: 0)()
    d = base / f"omp-{uid}"
    d.mkdir(mode=0o700, exist_ok=True)
    try:
        d.chmod(0o700)
    except OSError:
        pass
    _prune(d)
    return d


def _prune(d: Path) -> None:
    cutoff = time.time() - _MAX_AGE_SECONDS
    try:
        for p in d.iterdir():
            try:
                if p.is_file() and p.stat().st_mtime < cutoff:
                    p.unlink()
            except OSError:
                continue
    except OSError:
        pass
