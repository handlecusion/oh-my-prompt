#!/usr/bin/env python3
"""세션 효율 분석 - 어떤 식의 프롬프트/시작이 더 적은 입력으로 더 많이 끌어냈는지 비교"""

import sqlite3
import sys
from pathlib import Path
from statistics import mean, median

DB_PATH = Path.home() / ".claude" / "omp.db"


def section(title: str):
    print(f"\n{'='*64}\n  {title}\n{'='*64}")


def fmt(n):
    if not n:
        return "0"
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return f"{int(n):,}"


def truncate(s: str, n: int) -> str:
    s = (s or "").replace("\n", " ⏎ ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def collect_sessions(conn, cutoff: str):
    """세션별 메트릭 집계 (사용자 프롬프트 + 사용자 향한 응답만; sidechain 제외)"""
    p_rows = conn.execute(f"""
        SELECT session_id, COUNT(*) prompts,
               AVG(char_count) avg_pchars,
               MIN(ts) first_ts, MAX(ts) last_ts
        FROM prompts
        WHERE ts >= {cutoff} AND COALESCE(is_sidechain,0)=0
        GROUP BY session_id
    """).fetchall()
    p_by_sid = {r[0]: r for r in p_rows}

    t_rows = conn.execute(f"""
        SELECT session_id, COUNT(*) turns,
               SUM(output_tokens) out_tokens,
               SUM(total_tokens) total_tokens,
               SUM(text_chars) text_chars,
               SUM(tool_use_count) tools,
               MAX(cwd) cwd
        FROM token_usage
        WHERE ts >= {cutoff} AND COALESCE(is_sidechain,0)=0
        GROUP BY session_id
    """).fetchall()

    sessions = []
    for r in t_rows:
        sid, turns, out_tok, total_tok, text_chars, tools, cwd = r
        if sid not in p_by_sid:
            continue
        p_meta = p_by_sid[sid]
        prompts = p_meta[1] or 0
        if prompts < 1 or (out_tok or 0) < 1:
            continue
        sessions.append({
            "sid": sid,
            "cwd": cwd or "",
            "prompts": prompts,
            "avg_pchars": p_meta[2] or 0,
            "turns": turns,
            "out_tokens": out_tok or 0,
            "total_tokens": total_tok or 0,
            "text_chars": text_chars or 0,
            "tools": tools or 0,
            "leverage": (out_tok or 0) / prompts,
            "autonomy": turns / prompts,
            "tools_per_prompt": (tools or 0) / prompts,
        })
    return sessions


def first_prompt(conn, sid: str) -> str:
    row = conn.execute(
        "SELECT prompt FROM prompts WHERE session_id=? AND COALESCE(is_sidechain,0)=0 ORDER BY ts ASC LIMIT 1",
        (sid,),
    ).fetchone()
    return row[0] if row else ""


def tool_distribution(conn, sids: list) -> dict:
    """주어진 세션 집합에서 도구 사용 빈도 (tool_names CSV 기반)"""
    if not sids:
        return {}
    placeholders = ",".join("?" * len(sids))
    rows = conn.execute(
        f"""SELECT tool_names FROM token_usage
            WHERE session_id IN ({placeholders}) AND tool_use_count > 0""",
        sids,
    ).fetchall()
    counts = {}
    for (names,) in rows:
        for n in (names or "").split(","):
            n = n.strip()
            if n:
                counts[n] = counts.get(n, 0) + 1
    return counts


def percentile_split(sessions: list, key: str, top_pct=0.20, bot_pct=0.20):
    """key 기준 상위/하위 분할 (기본 20%/20%)"""
    if not sessions:
        return [], []
    s = sorted(sessions, key=lambda x: x[key], reverse=True)
    n = len(s)
    top_n = max(1, int(n * top_pct))
    bot_n = max(1, int(n * bot_pct))
    return s[:top_n], s[-bot_n:]


def compare_table(top, bot, key, label, fmt_fn=fmt):
    t = mean(x[key] for x in top) if top else 0
    b = mean(x[key] for x in bot) if bot else 0
    delta = ""
    if b > 0:
        ratio = t / b
        delta = f"  ({ratio:.1f}x)" if t > b else f"  ({ratio:.2f}x)"
    print(f"  {label:<28}  상위 {fmt_fn(t):>10}   하위 {fmt_fn(b):>10}{delta}")


def analyze(days: int = 30, min_prompts: int = 3):
    conn = sqlite3.connect(DB_PATH)
    cutoff = f"date('now', '-{days} days')"

    sessions = collect_sessions(conn, cutoff)
    sessions = [s for s in sessions if s["prompts"] >= min_prompts]
    if not sessions:
        print(f"최근 {days}일에 {min_prompts}회 이상 프롬프트가 있는 세션 없음")
        return

    n = len(sessions)
    print(f"\n분석 대상: 최근 {days}일, 사용자 프롬프트 {min_prompts}회 이상인 세션 {n}개")

    # ── 전체 분포 ────────────────────────────────────────────
    section("전체 세션 메트릭 (중앙값 / 평균)")
    rows = [
        ("프롬프트 수", "prompts"),
        ("AI 응답 턴", "turns"),
        ("출력 토큰", "out_tokens"),
        ("응답 텍스트 길이(자)", "text_chars"),
        ("도구 호출 수", "tools"),
        ("지렛대(out_tok/prompt)", "leverage"),
        ("자율(turns/prompt)", "autonomy"),
        ("도구/프롬프트", "tools_per_prompt"),
    ]
    print(f"  {'메트릭':<24} {'중앙값':>12} {'평균':>12}")
    print(f"  {'-'*52}")
    for label, k in rows:
        vals = [s[k] for s in sessions]
        print(f"  {label:<24} {fmt(median(vals)):>12} {fmt(mean(vals)):>12}")

    # ── 지렛대 기준 상위 vs 하위 ──────────────────────────────
    section("지렛대(leverage = 출력토큰/프롬프트) 상위 20% vs 하위 20%")
    top, bot = percentile_split(sessions, "leverage")
    print(f"  {'메트릭':<28}  {'상위':>10}        {'하위':>10}")
    print(f"  {'-'*60}")
    compare_table(top, bot, "leverage", "지렛대 (out_tok/prompt)")
    compare_table(top, bot, "autonomy", "자율도 (turns/prompt)")
    compare_table(top, bot, "prompts", "프롬프트 수")
    compare_table(top, bot, "out_tokens", "총 출력 토큰")
    compare_table(top, bot, "tools", "도구 호출 수")
    compare_table(top, bot, "tools_per_prompt", "도구/프롬프트")
    compare_table(top, bot, "avg_pchars", "평균 프롬프트 길이(자)")

    # ── 첫 프롬프트 비교 ─────────────────────────────────────
    section("상위 세션 첫 프롬프트 (어떻게 시작했는가)")
    for s in top[:5]:
        fp = first_prompt(conn, s["sid"])
        print(f"  [{fmt(s['leverage']):>8}/턴]  {Path(s['cwd']).name or '(no cwd)':<22}")
        print(f"     {truncate(fp, 100)}")

    section("하위 세션 첫 프롬프트")
    for s in bot[:5]:
        fp = first_prompt(conn, s["sid"])
        print(f"  [{fmt(s['leverage']):>8}/턴]  {Path(s['cwd']).name or '(no cwd)':<22}")
        print(f"     {truncate(fp, 100)}")

    # ── 도구 분포 ─────────────────────────────────────────────
    section("도구 사용 분포 (상위 세션 vs 하위 세션 — 응답 횟수 기준)")
    top_tools = tool_distribution(conn, [s["sid"] for s in top])
    bot_tools = tool_distribution(conn, [s["sid"] for s in bot])
    all_tools = sorted(set(top_tools) | set(bot_tools), key=lambda k: -(top_tools.get(k, 0) + bot_tools.get(k, 0)))
    top_total = sum(top_tools.values()) or 1
    bot_total = sum(bot_tools.values()) or 1
    print(f"  {'도구':<16} {'상위':>10} {'(%)':>7}   {'하위':>10} {'(%)':>7}")
    print(f"  {'-'*56}")
    for tool in all_tools[:12]:
        tc = top_tools.get(tool, 0)
        bc = bot_tools.get(tool, 0)
        print(f"  {tool:<16} {tc:>10} {tc/top_total*100:>6.1f}%   {bc:>10} {bc/bot_total*100:>6.1f}%")

    # ── 프로젝트별 효율 ───────────────────────────────────────
    section("프로젝트별 평균 지렛대 (세션 수 ≥2)")
    by_cwd = {}
    for s in sessions:
        by_cwd.setdefault(s["cwd"], []).append(s)
    proj_rows = []
    for cwd, ss in by_cwd.items():
        if len(ss) < 2:
            continue
        proj_rows.append((cwd, len(ss), mean(x["leverage"] for x in ss),
                          mean(x["prompts"] for x in ss),
                          sum(x["total_tokens"] for x in ss)))
    proj_rows.sort(key=lambda r: -r[2])
    if proj_rows:
        print(f"  {'프로젝트':<46} {'세션':>5} {'지렛대':>10} {'평균프롬프트':>12}")
        print(f"  {'-'*78}")
        for cwd, sc, lev, p, _ in proj_rows[:10]:
            label = "..." + cwd[-43:] if len(cwd) > 46 else cwd
            print(f"  {label:<46} {sc:>5} {fmt(lev):>10} {p:>12.1f}")
    else:
        print("  세션 2개 이상인 프로젝트 없음")

    print(f"\n  DB: {DB_PATH}\n")
    conn.close()


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    min_prompts = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    analyze(days, min_prompts)
