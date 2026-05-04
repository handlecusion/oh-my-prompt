"""공통 DB 스키마 + 트랜스크립트 파서"""
import json
import re
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "omp.db"

# Best-effort secret masking on stored prompt text. Patterns that produce too many
# false positives (generic long base64) are intentionally excluded.
_SECRET_PATTERNS = [
    (re.compile(r"sk-(?:ant-)?[A-Za-z0-9_-]{20,}"),     "[REDACTED:anthropic-or-openai-key]"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),        "[REDACTED:slack-token]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),          "[REDACTED:github-token]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),        "[REDACTED:github-pat]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"),                    "[REDACTED:aws-access-key]"),
    (re.compile(r"AIza[0-9A-Za-z_-]{35}"),               "[REDACTED:google-api-key]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
                                                          "[REDACTED:jwt]"),
]


def redact(text: str) -> str:
    if not text:
        return text
    out = text
    for rx, label in _SECRET_PATTERNS:
        out = rx.sub(label, out)
    return out


def _add_col(conn, table, col_def):
    # `table`/`col_def` are always module-internal literals; never accept user input here.
    col_name = col_def.split()[0]
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if col_name not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")


def open_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=3.0)
    # Tighten file perms — DB stores raw user prompts (potentially secrets).
    try:
        DB_PATH.chmod(0o600)
    except OSError:
        pass
    # WAL allows concurrent reads while a writer holds the lock — important because
    # both UserPromptSubmit and Stop hooks may write to the same DB simultaneously
    # under parallel sessions. busy_timeout retries on transient locks.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=3000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_id    TEXT UNIQUE,
            session_id   TEXT,
            cwd          TEXT,
            prompt       TEXT,
            char_count   INTEGER,
            word_count   INTEGER,
            is_sidechain INTEGER DEFAULT 0,
            ts           TEXT
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
            text_chars            INTEGER DEFAULT 0,
            tool_use_count        INTEGER DEFAULT 0,
            tool_names            TEXT,
            is_sidechain          INTEGER DEFAULT 0,
            ts                    TEXT
        )
    """)
    # idempotent migrations for older DBs
    _add_col(conn, "prompts", "is_sidechain INTEGER DEFAULT 0")
    _add_col(conn, "token_usage", "text_chars INTEGER DEFAULT 0")
    _add_col(conn, "token_usage", "tool_use_count INTEGER DEFAULT 0")
    _add_col(conn, "token_usage", "tool_names TEXT")
    _add_col(conn, "token_usage", "is_sidechain INTEGER DEFAULT 0")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_prompts_ts ON prompts(ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tokens_ts  ON token_usage(ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prompts_session ON prompts(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tokens_session ON token_usage(session_id)")
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


def _assistant_breakdown(content):
    """assistant 메시지 content에서 텍스트 길이/도구 호출/도구명을 추출"""
    text_chars = 0
    tools = []
    if isinstance(content, str):
        text_chars = len(content)
    elif isinstance(content, list):
        for b in content:
            if not isinstance(b, dict):
                continue
            t = b.get("type")
            if t == "text":
                text_chars += len(b.get("text", "") or "")
            elif t == "thinking":
                text_chars += len(b.get("thinking", "") or "")
            elif t == "tool_use":
                name = b.get("name", "")
                if name:
                    tools.append(name)
    # unique tool names, preserving first-seen order
    seen = set()
    unique = []
    for n in tools:
        if n not in seen:
            seen.add(n)
            unique.append(n)
    return text_chars, len(tools), ",".join(unique)


def ingest_transcript(conn, path: Path):
    """JSONL 트랜스크립트 한 파일에서 prompts + token_usage 추출 (UPSERT)"""
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
            sidechain = 1 if d.get("isSidechain") else 0

            if t == "user":
                msg = d.get("message", {})
                if msg.get("role") != "user":
                    continue
                text = _user_text(msg.get("content"))
                if text is None or not text.strip():
                    continue
                if text.startswith("<command-") or text.startswith("Caveat:"):
                    continue
                text = redact(text)
                pid = d.get("promptId") or f"{sid}:{ts}"
                cur = conn.execute(
                    """INSERT INTO prompts
                       (prompt_id, session_id, cwd, prompt, char_count, word_count, is_sidechain, ts)
                       VALUES (?,?,?,?,?,?,?,?)
                       ON CONFLICT(prompt_id) DO UPDATE SET
                         session_id=excluded.session_id,
                         cwd=excluded.cwd,
                         prompt=excluded.prompt,
                         char_count=excluded.char_count,
                         word_count=excluded.word_count,
                         is_sidechain=excluded.is_sidechain,
                         ts=excluded.ts""",
                    (pid, sid, cwd, text, len(text), len(text.split()), sidechain, ts),
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
                text_chars, tool_count, tool_names = _assistant_breakdown(msg.get("content"))
                cur = conn.execute(
                    """INSERT INTO token_usage
                       (msg_id, session_id, cwd, model,
                        input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens, total_tokens,
                        text_chars, tool_use_count, tool_names, is_sidechain, ts)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(msg_id) DO UPDATE SET
                         session_id=excluded.session_id,
                         cwd=excluded.cwd,
                         model=excluded.model,
                         input_tokens=excluded.input_tokens,
                         output_tokens=excluded.output_tokens,
                         cache_read_tokens=excluded.cache_read_tokens,
                         cache_creation_tokens=excluded.cache_creation_tokens,
                         total_tokens=excluded.total_tokens,
                         text_chars=excluded.text_chars,
                         tool_use_count=excluded.tool_use_count,
                         tool_names=excluded.tool_names,
                         is_sidechain=excluded.is_sidechain,
                         ts=excluded.ts""",
                    (mid, sid, cwd, msg.get("model", ""),
                     inp, out, cr, cc, inp + out + cr + cc,
                     text_chars, tool_count, tool_names, sidechain, ts),
                )
                inserted_t += cur.rowcount

    conn.commit()
    return inserted_p, inserted_t
