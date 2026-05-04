#!/usr/bin/env python3
"""반복 지시 패턴 분석 - 사용자가 자주 치는 프롬프트를 발견하고 CLAUDE.md 후보로 제안"""

import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "omp.db"

# 시스템이 트랜스크립트에 끼워넣는 의사-프롬프트 (사용자가 친 게 아님)
SYSTEM_PREFIXES = (
    "<local-command-",
    "<bash-input>", "<bash-stdout>", "<bash-stderr>",
    "<command-name>", "<command-message>", "<command-args>",
    "<system-reminder>",
    "<task-notification",
    "[Request interrupted",
    "[Image:",
    "Caveat:",
)


def is_system_msg(p: str) -> bool:
    s = p.lstrip()
    if any(s.startswith(prefix) for prefix in SYSTEM_PREFIXES):
        return True
    # 임의의 XML/HTML 태그로 시작하면 시스템 메시지로 간주
    if s.startswith("<") and re.match(r"<[a-zA-Z][\w-]*", s):
        return True
    return False

# 의도 태깅 룰 — 한국어/영어 키워드, 단순 부분 문자열 매칭
INTENT_RULES = [
    ("slash",     r"^/"),
    ("debug/fix", r"\b(fix|debug|버그|고쳐|수정|에러|error|오류)\b"),
    ("test",      r"\b(test|테스트|spec|jest|vitest|pytest)\b"),
    ("build",     r"\b(build|빌드|compile|컴파일|tsc|타입.*체크)\b"),
    ("git",       r"\b(commit|커밋|push|pr|merge|rebase|stash|git)\b"),
    ("explain",   r"\b(explain|설명|왜|어떻게|무슨|이게뭐|왜그래|이거뭐)\b"),
    ("refactor",  r"\b(refactor|리팩토|정리|cleanup|단순화|추상화)\b"),
    ("run/exec",  r"\b(run|실행|돌려|launch|start|시작)\b"),
    ("install",   r"\b(install|설치|npm i|pnpm add|pip install)\b"),
    ("plan",      r"\b(plan|계획|기획|설계|design|architecture|아키텍처)\b"),
    ("review",    r"\b(review|리뷰|검토|확인해|체크해)\b"),
    ("doc",       r"\b(readme|docs|문서|주석|comment)\b"),
    ("research",  r"\b(research|조사|찾아|search|문서)\b"),
    ("ack",       r"^(ok|okay|좋아|응|네|예|good|nice|thanks|고마워|굿)\b"),
    ("undo",      r"\b(undo|stop|취소|되돌|아니|그거말고|중단)\b"),
]


def normalize(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[`*_>#~]+", "", s)
    return s


def tag_intent(prompt: str) -> str:
    p = prompt.strip().lower()
    for tag, rx in INTENT_RULES:
        if re.search(rx, p, re.IGNORECASE):
            return tag
    return "other"


def first_words(s: str, n: int = 4) -> str:
    words = re.findall(r"\S+", s.strip())
    return " ".join(words[:n]).lower()


def section(title: str):
    print(f"\n{'='*64}\n  {title}\n{'='*64}")


def fmt_int(n):
    return f"{n:,}" if n else "0"


def truncate(s: str, n: int) -> str:
    s = s.replace("\n", " ⏎ ")
    return s if len(s) <= n else s[: n - 1] + "…"


def analyze(days: int = 30, min_count: int = 3):
    conn = sqlite3.connect(DB_PATH)
    cutoff = f"date('now', '-{days} days')"

    # 사용자 프롬프트만 (서브에이전트, 시스템 의사-프롬프트 제외)
    raw = conn.execute(f"""
        SELECT prompt, char_count, ts FROM prompts
        WHERE ts >= {cutoff} AND COALESCE(is_sidechain,0) = 0
    """).fetchall()
    rows = [r for r in raw if r[0] and not is_system_msg(r[0])]
    if not rows:
        print(f"최근 {days}일에 사용자 프롬프트가 없습니다.")
        return
    skipped = len(raw) - len(rows)

    total = len(rows)
    short_prompts = [r[0] for r in rows if r[1] < 200]
    long_prompts = [r[0] for r in rows if r[1] >= 200]

    print(f"\n분석 대상: 최근 {days}일 사용자 프롬프트 {total}건  (시스템 의사-프롬프트 {skipped}건 제외)")
    print(f"  짧은 프롬프트 (<200자): {len(short_prompts)}  |  긴 프롬프트 (>=200자): {len(long_prompts)}")

    # ── 1. 의도 태그 분포 ────────────────────────────────────
    section("의도별 분포")
    intents = Counter(tag_intent(p) for p in (r[0] for r in rows))
    for tag, cnt in intents.most_common():
        bar = "#" * min(cnt, 40)
        pct = cnt / total * 100
        print(f"  {tag:<12} {cnt:>4}건 ({pct:5.1f}%)  {bar}")

    # ── 2. 정규화 후 정확 매칭 (반복 지시) ────────────────────
    section("정규화 후 동일 프롬프트 (반복 지시) — CLAUDE.md/hook 1순위 후보")
    norm_counter = Counter()
    norm_to_orig = {}
    for p in short_prompts:
        n = normalize(p)
        if not n or len(n) < 3:
            continue
        norm_counter[n] += 1
        norm_to_orig.setdefault(n, p)
    repeats = [(n, c) for n, c in norm_counter.most_common(20) if c >= min_count]
    if repeats:
        print(f"  {'횟수':>4}  프롬프트")
        print(f"  {'-'*60}")
        for n, c in repeats:
            print(f"  {c:>4}회  {truncate(norm_to_orig[n], 56)}")
    else:
        print(f"  {min_count}회 이상 반복된 짧은 프롬프트 없음")

    # ── 3. 첫 4단어 패턴 ────────────────────────────────────
    section("첫 4단어 패턴 (지시 시작 방식)")
    starts = Counter()
    for r in rows:
        s = first_words(r[0], 4)
        if len(s) < 5:
            continue
        starts[s] += 1
    top_starts = [(s, c) for s, c in starts.most_common(15) if c >= min_count]
    if top_starts:
        for s, c in top_starts:
            bar = "#" * min(c, 30)
            print(f"  {c:>4}회  {truncate(s, 40):<42} {bar}")
    else:
        print("  반복되는 시작 패턴 없음")

    # ── 4. 의도별 평균 길이/효율 힌트 ─────────────────────────
    section("의도별 평균 프롬프트 길이")
    by_intent = {}
    for r in rows:
        t = tag_intent(r[0])
        by_intent.setdefault(t, []).append(r[1] or 0)
    for tag in sorted(by_intent.keys(), key=lambda k: -len(by_intent[k]))[:10]:
        lens = by_intent[tag]
        avg = sum(lens) / len(lens) if lens else 0
        print(f"  {tag:<12} {len(lens):>4}건  평균 {int(avg):>5}자")

    # ── 5. 자동 제안 ────────────────────────────────────────
    section("자동 제안")
    suggestions = []
    if repeats:
        suggestions.append(
            f"• {len(repeats)}개의 짧은 프롬프트가 {min_count}회 이상 반복됨 → "
            "CLAUDE.md에 동작 규칙으로 추가하거나 슬래시 커맨드로 빼는 것 검토"
        )
    if intents.get("undo", 0) > total * 0.05:
        suggestions.append(
            f"• 'undo/취소/그거말고' 류가 {intents['undo']}건 ({intents['undo']/total*100:.0f}%) — "
            "프롬프트에 더 명시적인 제약을 거는 게 효율적일 수 있음"
        )
    if intents.get("ack", 0) > total * 0.10:
        suggestions.append(
            f"• 단순 응답('ok/응/굿' 등)이 {intents['ack']}건 — "
            "Stop hook이나 메모리에 사용자 톤을 저장해 자동화 여지 있음"
        )
    if intents.get("slash", 0) > 0:
        suggestions.append(
            f"• 이미 슬래시 커맨드로 추출된 호출 {intents['slash']}건 — 좋은 패턴, 유지 권장"
        )
    if not suggestions:
        suggestions.append("• 특별히 두드러진 반복 패턴 없음")
    for s in suggestions:
        print(f"  {s}")

    print(f"\n  DB: {DB_PATH}\n")
    conn.close()


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    min_count = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    analyze(days, min_count)
