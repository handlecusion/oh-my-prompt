#!/usr/bin/env python3
"""omp 통계 리포트 - python3 hooks/report.py [일수]"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "omp.db"


def fmt(n):
    if not n:
        return "0"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return f"{n:,}"


def report(days: int = 7):
    if not DB_PATH.exists():
        print("아직 데이터가 없습니다. 백필: python3 ~/.claude/hooks/backfill.py")
        return

    conn = sqlite3.connect(DB_PATH)
    cutoff = f"date('now', '-{days} days')"

    # 전체 합계
    print(f"\n{'='*60}")
    print(f"  최근 {days}일 요약")
    print(f"{'='*60}")
    row = conn.execute(f"""
        SELECT COUNT(*) turns, SUM(input_tokens) inp, SUM(output_tokens) out,
               SUM(cache_read_tokens) cr, SUM(cache_creation_tokens) cc, SUM(total_tokens) tot
        FROM token_usage WHERE ts >= {cutoff}
    """).fetchone()
    pcount = conn.execute(f"SELECT COUNT(*) FROM prompts WHERE ts >= {cutoff}").fetchone()[0]
    sessions = conn.execute(f"SELECT COUNT(DISTINCT session_id) FROM token_usage WHERE ts >= {cutoff}").fetchone()[0]
    if row and row[0]:
        print(f"  세션: {sessions}  프롬프트: {pcount}  AI 응답: {row[0]}")
        print(f"  토큰  입력 {fmt(row[1])}  출력 {fmt(row[2])}  캐시읽기 {fmt(row[3])}  캐시생성 {fmt(row[4])}")
        print(f"  합계: {fmt(row[5])}")

    # 일별 토큰
    print(f"\n{'='*60}")
    print(f"  일별 토큰 사용량")
    print(f"{'='*60}")
    rows = conn.execute(f"""
        SELECT date(ts) day, COUNT(*) turns,
               SUM(input_tokens) inp, SUM(output_tokens) out,
               SUM(cache_read_tokens) cache, SUM(total_tokens) total
        FROM token_usage WHERE ts >= {cutoff}
        GROUP BY day ORDER BY day DESC
    """).fetchall()
    if rows:
        print(f"  {'날짜':<12} {'턴':>5} {'입력':>8} {'출력':>8} {'캐시':>8} {'합계':>9}")
        print(f"  {'-'*54}")
        for r in rows:
            print(f"  {r[0]:<12} {r[1]:>5} {fmt(r[2]):>8} {fmt(r[3]):>8} {fmt(r[4]):>8} {fmt(r[5]):>9}")
    else:
        print("  데이터 없음")

    # 모델별
    print(f"\n{'='*60}")
    print(f"  모델별 사용량")
    print(f"{'='*60}")
    rows = conn.execute(f"""
        SELECT COALESCE(NULLIF(model,''),'(unknown)') m, COUNT(*) turns,
               SUM(total_tokens) total
        FROM token_usage WHERE ts >= {cutoff}
        GROUP BY m ORDER BY total DESC
    """).fetchall()
    if rows:
        for r in rows:
            print(f"  {r[0]:<28} {r[1]:>5}턴  {fmt(r[2]):>9}")

    # 프롬프트 길이 분포
    print(f"\n{'='*60}")
    print(f"  프롬프트 길이 분포")
    print(f"{'='*60}")
    rows = conn.execute(f"""
        SELECT CASE
            WHEN char_count < 100  THEN '0-99자'
            WHEN char_count < 300  THEN '100-299자'
            WHEN char_count < 600  THEN '300-599자'
            WHEN char_count < 1000 THEN '600-999자'
            ELSE '1000자+'
        END b, COUNT(*) cnt, ROUND(AVG(char_count)) avg_c, MIN(char_count) min_c
        FROM prompts WHERE ts >= {cutoff}
        GROUP BY b ORDER BY min_c
    """).fetchall()
    if rows:
        for r in rows:
            bar = '#' * min(r[1], 40)
            print(f"  {r[0]:<12} {r[1]:>4}건  {bar}  (평균 {int(r[2])}자)")

    # 프로젝트별
    print(f"\n{'='*60}")
    print(f"  프로젝트별 토큰 (상위 10)")
    print(f"{'='*60}")
    rows = conn.execute(f"""
        SELECT CASE WHEN length(cwd)>45 THEN '...'||substr(cwd,-42) ELSE cwd END proj,
               SUM(total_tokens) total, COUNT(*) turns,
               COUNT(DISTINCT session_id) sessions
        FROM token_usage WHERE ts >= {cutoff}
        GROUP BY cwd ORDER BY total DESC LIMIT 10
    """).fetchall()
    if rows:
        for r in rows:
            print(f"  {r[0]}")
            print(f"    토큰 {fmt(r[1]):>8}  |  턴 {r[2]:>4}  |  세션 {r[3]}")

    # 세션 정보
    print(f"\n{'='*60}")
    print(f"  세션 통계")
    print(f"{'='*60}")
    row = conn.execute(f"""
        SELECT COUNT(DISTINCT session_id) sessions,
               ROUND(AVG(turns_per_session), 1) avg_turns,
               MAX(turns_per_session) max_turns,
               ROUND(AVG(tokens_per_session)) avg_tok,
               MAX(tokens_per_session) max_tok
        FROM (
            SELECT session_id, COUNT(*) turns_per_session, SUM(total_tokens) tokens_per_session
            FROM token_usage WHERE ts >= {cutoff}
            GROUP BY session_id
        )
    """).fetchone()
    if row and row[0]:
        print(f"  세션 수: {row[0]}")
        print(f"  세션당 턴 평균/최대:    {row[1]} / {row[2]}")
        print(f"  세션당 토큰 평균/최대:  {fmt(int(row[3] or 0))} / {fmt(row[4] or 0)}")

    conn.close()
    print(f"\n  DB: {DB_PATH}\n")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    report(days)
