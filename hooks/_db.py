"""공통 DB 스키마 + 트랜스크립트 파서"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "omp.db"


def open_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_id  TEXT UNIQUE,
            session_id TEXT,
            cwd        TEXT,
            prompt     TEXT,
            char_count INTEGER,
            word_count INTEGER,
            ts         TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id                TEXT UNIQUE,
            session_id            TEXT,
            cwd                   TEXT,
            model                 TEXT,
            input_tokens          INTEGER DEFAULT 0,
            output_tokens         INTEGER DEFAULT 0,
            cache_read_tokens     INTEGER DEFAULT 0,
            cache_creation_tokens INTEGER DEFAULT 0,
            total_tokens          INTEGER DEFAULT 0,
            ts                    TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prompts_ts ON prompts(ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tokens_ts  ON token_usage(ts)")
    conn.commit()
    return conn


def _user_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_result":
                return None
            if b.get("type") == "text":
                parts.append(b.get("text", ""))
        return "\n".join(parts) if parts else None
    return None


def ingest_transcript(conn, path: Path):
    """JSONL 트랜스크립트 한 파일에서 prompts + token_usage 추출"""
    inserted_p, inserted_t = 0, 0
    try:
        f = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return 0, 0

    with f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            t = d.get("type")
            sid = d.get("sessionId", "")
            cwd = d.get("cwd", "")
            ts = d.get("timestamp", "")

            if t == "user":
                msg = d.get("message", {})
                if msg.get("role") != "user":
                    continue
                text = _user_text(msg.get("content"))
                if text is None or not text.strip():
                    continue
                # skip system-injected prompts (caveats, command-stdout, etc.)
                if text.startswith("<command-") or text.startswith("Caveat:"):
                    continue
                pid = d.get("promptId") or f"{sid}:{ts}"
                cur = conn.execute(
                    "INSERT OR IGNORE INTO prompts (prompt_id, session_id, cwd, prompt, char_count, word_count, ts) VALUES (?,?,?,?,?,?,?)",
                    (pid, sid, cwd, text, len(text), len(text.split()), ts),
                )
                inserted_p += cur.rowcount

            elif t == "assistant":
                msg = d.get("message", {})
                usage = msg.get("usage")
                if not usage:
                    continue
                mid = msg.get("id") or d.get("uuid")
                if not mid:
                    continue
                inp = usage.get("input_tokens", 0) or 0
                out = usage.get("output_tokens", 0) or 0
                cr = usage.get("cache_read_input_tokens", 0) or 0
                cc = usage.get("cache_creation_input_tokens", 0) or 0
                cur = conn.execute(
                    """INSERT OR IGNORE INTO token_usage
                       (msg_id, session_id, cwd, model,
                        input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens, total_tokens, ts)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (mid, sid, cwd, msg.get("model", ""),
                     inp, out, cr, cc, inp + out + cr + cc, ts),
                )
                inserted_t += cur.rowcount

    conn.commit()
    return inserted_p, inserted_t
