#!/usr/bin/env python3
"""Stop hook - 트랜스크립트에서 토큰 사용량 추출하여 SQLite에 기록"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _db import ingest_transcript, open_db


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tp = data.get("transcript_path")
    if not tp:
        sys.exit(0)

    path = Path(tp)
    if not path.exists():
        sys.exit(0)

    conn = open_db()
    ingest_transcript(conn, path)
    conn.close()


if __name__ == "__main__":
    main()
