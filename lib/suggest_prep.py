#!/usr/bin/env python3
"""/omp:suggest 전처리: 분석 데이터 수집 + 입력파일 작성 + 보관 경로 산출.

stdout으로 JSON 한 줄만 출력한다 (input_path, output_path, days, min_count, timestamp).
"""

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = Path.home() / ".claude" / "omp_suggestions"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _tmp import omp_tmpdir


def capture(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = r.stdout
    if r.returncode != 0 and r.stderr:
        out += "\n[stderr]\n" + r.stderr
    return out


def main():
    days = sys.argv[1] if len(sys.argv) > 1 else "30"
    min_count = sys.argv[2] if len(sys.argv) > 2 else "3"

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    try:
        ARCHIVE.chmod(0o700)
    except OSError:
        pass

    patterns = capture(["python3", str(ROOT / "lib/analyzers/patterns.py"), days, min_count, "--text"])
    efficiency = capture(["python3", str(ROOT / "lib/analyzers/efficiency.py"), days, min_count, "--text"])

    ts = time.strftime("%Y-%m-%d_%H%M%S")
    input_path = omp_tmpdir() / f"omp_suggest_input_{ts}.md"
    output_path = ARCHIVE / f"{ts}.md"

    input_path.write_text(
        f"""# omp 분석 입력 (days={days}, min_count={min_count})

## 반복 패턴 분석
{patterns}

## 효율 분석
{efficiency}
""",
        encoding="utf-8",
    )
    try:
        input_path.chmod(0o600)  # may quote raw user prompts (with secrets if redact missed any).
    except OSError:
        pass

    print(json.dumps({
        "days": days,
        "min_count": min_count,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "timestamp": ts,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
