#!/usr/bin/env python3
"""과거 트랜스크립트(~/.claude/projects/**/*.jsonl)를 스캔하여 DB 백필"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _db import ingest_transcript, open_db

PROJECTS = Path.home() / ".claude" / "projects"


def main():
    if not PROJECTS.exists():
        print(f"프로젝트 디렉토리 없음: {PROJECTS}")
        return

    files = sorted(PROJECTS.rglob("*.jsonl"))
    print(f"트랜스크립트 {len(files)}개 발견. 인제스트 시작...")

    conn = open_db()
    total_p, total_t, errs = 0, 0, 0
    for i, f in enumerate(files, 1):
        try:
            p, t = ingest_transcript(conn, f)
            total_p += p
            total_t += t
        except Exception as e:
            errs += 1
            print(f"  [경고] {f.name}: {e}", file=sys.stderr)
        if i % 50 == 0:
            print(f"  진행 {i}/{len(files)}  prompts+={total_p}  tokens+={total_t}")

    conn.close()
    print(f"\n완료: prompts {total_p}건, token_usage {total_t}건 추가 (오류 {errs}건)")


if __name__ == "__main__":
    main()
