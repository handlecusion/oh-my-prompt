#!/usr/bin/env python3
"""UserPromptSubmit hook - 프롬프트를 SQLite에 기록"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _db import open_db, redact


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    prompt = redact(data.get("prompt", ""))
    session_id = data.get("session_id", "")
    cwd = data.get("cwd", "")
    ts = datetime.now().isoformat()
    pid = f"{session_id}:{ts}"

    conn = open_db()
    conn.execute(
        "INSERT OR IGNORE INTO prompts (prompt_id, session_id, cwd, prompt, char_count, word_count, ts) VALUES (?,?,?,?,?,?,?)",
        (pid, session_id, cwd, prompt, len(prompt), len(prompt.split()), ts),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
