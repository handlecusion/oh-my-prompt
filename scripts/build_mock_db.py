#!/usr/bin/env python3
"""Build a deterministic mock omp.db for screenshot generation.

Usage:
    python3 scripts/build_mock_db.py --locale en   # writes ~/.claude/omp.db
    python3 scripts/build_mock_db.py --locale ko

Also writes 2 mock analyses into ~/.claude/omp_suggestions/ in the same locale.

The dataset is intentionally small but designed to make every panel produce
something interesting:
- repeated short prompts of varying counts (CLAUDE.md / hook candidates)
- a top-leverage cohort with long, context-rich first prompts
- a bottom-leverage cohort with terse one-liners
- multiple projects with realistic-looking paths
- a mix of models (opus / sonnet / haiku) and tool usage patterns
"""

import argparse
import random
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks"))
from _db import open_db  # noqa: E402

ARCHIVE = Path.home() / ".claude" / "omp_suggestions"


# ---------------- locale-specific corpora ---------------------------------

EN_PROJECTS = [
    "/Users/dev/code/fastapi-todo",
    "/Users/dev/code/react-shop",
    "/Users/dev/code/k8s-cluster",
    "/Users/dev/code/auth-service",
    "/Users/dev/code/data-pipeline",
    "/Users/dev/code/landing-page",
    "/Users/dev/code/cli-tools",
    "/Users/dev/code/ml-inference",
]

KO_PROJECTS = [
    "/Users/dev/code/주문관리-백엔드",
    "/Users/dev/code/쇼핑몰-프론트",
    "/Users/dev/code/결제-서비스",
    "/Users/dev/code/사용자-인증",
    "/Users/dev/code/데이터-파이프라인",
    "/Users/dev/code/관리자-대시보드",
    "/Users/dev/code/모바일-앱",
    "/Users/dev/code/ml-추론서버",
]

EN_REPEATS = [
    ("run the tests", 14),
    ("/lint", 10),
    ("explain this function", 8),
    ("deploy to staging", 6),
    ("commit", 5),
    ("ok proceed", 5),
    ("any errors?", 4),
    ("retry", 4),
    ("looks good", 3),
    ("/format", 3),
]

KO_REPEATS = [
    ("테스트 돌려줘", 14),
    ("/lint", 10),
    ("이 함수 설명해줘", 8),
    ("스테이징에 배포해", 6),
    ("커밋", 5),
    ("진행해", 5),
    ("에러 있어?", 4),
    ("다시 시도해", 4),
    ("좋아", 3),
    ("/format", 3),
]

# Long, context-rich first prompts → high leverage cohort
EN_TOP_FIRSTS = [
    "Look at the auth middleware in src/auth/middleware.ts. The session refresh "
    "fails when the token is exactly at the expiry boundary. Read the related "
    "tests in tests/auth/, find the off-by-one, and submit a fix with a regression "
    "test. Then update CHANGELOG.md.",
    "We need to add OpenTelemetry to the FastAPI service. Read pyproject.toml, "
    "add the right dependencies, instrument the routers under app/api/, wire up "
    "the OTLP exporter behind an OTEL_ENDPOINT env var, and document the change "
    "in docs/observability.md.",
    "Migrate the payment webhook handler from synchronous to async. Audit every "
    "caller in app/, refactor the queue worker, ensure backwards compatibility "
    "behind a feature flag, and add load-test scaffolding under tests/load/.",
    "Walk through the codebase and find all places where we still parse dates "
    "with strptime. Replace with the project's standard parse_iso() helper, "
    "preserving timezone behavior. Add tests covering DST and leap-second edges.",
    "Build a one-page admin view that shows real-time queue depth + worker "
    "health. Use the existing Tailwind tokens, server-render with our SSR shell, "
    "and add a dark-mode variant. Don't add any new dependencies.",
]

KO_TOP_FIRSTS = [
    "src/auth/middleware.ts 의 인증 미들웨어를 봐줘. 토큰 만료 정확한 경계에서 "
    "세션 갱신이 실패해. tests/auth/ 의 관련 테스트들 읽고 off-by-one 찾아서 "
    "회귀 테스트랑 같이 수정 PR 올려. 그 다음 CHANGELOG.md 도 업데이트.",
    "FastAPI 서비스에 OpenTelemetry 붙이자. pyproject.toml 읽고 필요한 의존성 "
    "추가, app/api/ 의 라우터 instrument, OTEL_ENDPOINT 환경변수 뒤로 OTLP "
    "exporter 연결, 그리고 docs/observability.md 에 변경사항 문서화.",
    "결제 웹훅 핸들러를 동기에서 비동기로 마이그레이션. app/ 의 모든 호출자를 "
    "감사하고, 큐 워커를 리팩터, 피처 플래그 뒤로 하위 호환성 보장, "
    "tests/load/ 에 부하 테스트 골격 추가해.",
    "코드베이스 전체에서 strptime 으로 날짜 파싱하는 곳을 다 찾아서 프로젝트 "
    "표준 parse_iso() 헬퍼로 교체. 타임존 동작 유지하고 DST 와 윤초 엣지 "
    "테스트 추가해.",
    "큐 적체 + 워커 상태를 실시간으로 보여주는 어드민 한 페이지 만들어. "
    "기존 Tailwind 토큰 쓰고, SSR 쉘로 서버 렌더링, 다크모드 variant 까지. "
    "의존성은 새로 추가하지 마.",
]

EN_BOT_FIRSTS = [
    "fix it",
    "<local-command-stdout>Login successful</local-command-stdout>",
    "rerun",
    "wait nothing happened",
    "ok",
]

KO_BOT_FIRSTS = [
    "고쳐줘",
    "<local-command-stdout>로그인 성공</local-command-stdout>",
    "다시",
    "어 아무것도 안 됐는데",
    "응",
]

EN_TOPICS = [
    "Add input validation to the signup endpoint",
    "The dashboard renders blank on Safari iOS — investigate",
    "Migrate the legacy SOAP client to REST",
    "Tighten the typescript config — strict mode plus noUncheckedIndexedAccess",
    "Why does the build take 9 minutes? Profile webpack and propose splits.",
    "Set up branch protection rules and required CI checks",
    "Document the metrics emitted by the worker in docs/metrics.md",
    "Bump node 18 → 20 in CI and verify nothing breaks",
]

KO_TOPICS = [
    "회원가입 엔드포인트에 입력 검증 추가",
    "Safari iOS에서 대시보드가 흰 화면으로 뜨는 현상 조사",
    "레거시 SOAP 클라이언트를 REST로 마이그레이션",
    "타입스크립트 설정 강화 — strict 모드 + noUncheckedIndexedAccess",
    "빌드가 9분 걸리는 이유 프로파일링하고 청크 분할안 제안해",
    "브랜치 보호 규칙이랑 필수 CI 체크 설정",
    "워커가 emit 하는 메트릭 docs/metrics.md 에 문서화",
    "CI 의 node 18 → 20 업그레이드하고 깨지는 거 없는지 검증",
]


# ---------------- archive proposals ---------------------------------------

EN_ARCHIVE = [
    (
        "2026-04-22_103015.md",
        """## 1. CLAUDE.md candidate rules

- Auto-handle "ok proceed" / "looks good"
  - (a) "ok proceed" appears 5 times, "looks good" 3 times in normalized prompts.
  - (b) Add to CLAUDE.md: "When the user replies with bare 'ok proceed' or 'looks good', execute the prior plan/proposal without re-asking for confirmation."

- Treat short error follow-ups as a debug request
  - (a) "any errors?" appears 4 times, always after a build or test step.
  - (b) Add to CLAUDE.md: "When the user asks 'any errors?' alone, scan the most recent build/test output for the first error line and report it before suggesting a fix."

## 2. Memory candidates

- Top-leverage sessions front-load context
  - (a) The 5 highest-leverage first prompts all combine 'read X', 'find Y', 'fix Z' in one sentence (avg 17.4K tokens / turn).
  - (b) Save to memory: "User prefers explore-then-execute in a single first prompt; route discovery work to explore subagent and hand off to executor without an intermediate confirmation."

## 3. Slash command / hook candidates

- `/run-tests` macro
  - (a) "run the tests" appears 14 times across 8 projects.
  - (b) Add a project-level slash command that runs the canonical test command per repo (npm test / pytest / cargo test) using a small detector.
""",
    ),
    (
        "2026-04-29_141207.md",
        """## 1. CLAUDE.md candidate rules

- Skip narration after `/lint` runs
  - (a) `/lint` invoked 10 times this period; user almost never engages with the output unless there are violations.
  - (b) Add to CLAUDE.md: "After running /lint or equivalent linter, only summarize if there are warnings/errors; otherwise reply with a single line."

## 2. Memory candidates

- Bash-first verification style
  - (a) Top sessions show 74% Bash + 18% Read tool usage; bottom sessions are 81% Bash + only 12% Read.
  - (b) Save to memory: "User verifies changes by running them and reading output, not by relying on type-check alone — always pair Bash with a Read of the produced artifact."

## 3. Slash command / hook candidates

- This category had no strong signal this week.
""",
    ),
]

KO_ARCHIVE = [
    (
        "2026-04-22_103015.md",
        """## 1. CLAUDE.md에 추가할 동작 규칙

- "진행해" / "좋아" 자동 처리
  - (a) 정규화 후 "진행해" 5회, "좋아" 3회 반복.
  - (b) CLAUDE.md에 "사용자가 단독으로 '진행해' 또는 '좋아'라고 하면 직전 제안/계획을 별도 확인 없이 그대로 실행한다"를 추가.

- 짧은 에러 후속 질의를 디버그 요청으로 해석
  - (a) "에러 있어?" 4회 — 모두 빌드/테스트 실행 직후.
  - (b) CLAUDE.md에 "사용자가 '에러 있어?'만 보내면 직전 빌드/테스트 출력의 첫 에러 라인을 찾아 보고한 뒤 수정안을 제시한다"를 추가.

## 2. 메모리에 저장할 사용자 선호/맥락

- 고지렛대 세션의 첫 프롬프트는 컨텍스트를 한 번에 로드
  - (a) 상위 5개 첫 프롬프트가 모두 '읽고-찾고-고쳐' 를 한 문장에 묶음 (평균 17.4K 토큰/턴).
  - (b) 메모리에 "이 사용자는 첫 프롬프트에서 탐색→실행을 한 번에 묶는 스타일을 선호. explore 에이전트로 보낸 뒤 중간 확인 없이 executor 로 넘기는 흐름이 잘 맞음".

## 3. 슬래시 커맨드 / hook 후보

- `/run-tests` 매크로
  - (a) "테스트 돌려줘" 가 8개 프로젝트에서 총 14회 반복.
  - (b) 프로젝트 레벨 슬래시 커맨드로 추출 — 디텍터로 npm test / pytest / cargo test 자동 선택.
""",
    ),
    (
        "2026-04-29_141207.md",
        """## 1. CLAUDE.md에 추가할 동작 규칙

- `/lint` 후 narration 생략
  - (a) `/lint` 가 이 기간 10회 호출됐고 위반이 없으면 사용자가 거의 응답하지 않음.
  - (b) CLAUDE.md에 "/lint 또는 동등한 린터 실행 후, 경고/에러가 있을 때만 요약하고 그 외엔 한 줄로만 답한다"를 추가.

## 2. 메모리에 저장할 사용자 선호/맥락

- Bash 우선 검증 스타일
  - (a) 상위 세션: Bash 74% + Read 18%, 하위 세션: Bash 81% + Read 12%.
  - (b) 메모리에 "이 사용자는 변경을 직접 실행해 출력을 읽으며 검증함. 타입체크에만 의존하지 말고 항상 Bash 실행 + 결과 Read 까지 묶어서 회신할 것".

## 3. 슬래시 커맨드 / hook 후보

- 이 카테고리에선 이번 주 강한 시그널 없음.
""",
    ),
]


# ---------------- builder -------------------------------------------------

def _project(rng, projects):
    return rng.choice(projects)


def _model_for_session(rng):
    """Mostly opus, some sonnet, occasional haiku."""
    return rng.choices(
        ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
        weights=[60, 30, 10],
    )[0]


def _ts(days_ago_float: float) -> str:
    return (datetime.now() - timedelta(days=days_ago_float)).isoformat()


def _ingest_session(
    conn,
    sid: str,
    cwd: str,
    first_prompt: str,
    follow_ups: list[str],
    model: str,
    ai_turns: int,
    out_per_turn: int,
    tool_per_turn: int,
    tool_choices: list[str],
    days_ago: float,
    rng,
):
    """Insert one session worth of prompts + assistant turns."""
    prompts = [first_prompt] + follow_ups
    for i, p in enumerate(prompts):
        offset = i * 0.001
        pid = f"{sid}-p{i}"
        ts = _ts(days_ago - offset)
        conn.execute(
            "INSERT OR IGNORE INTO prompts(prompt_id, session_id, cwd, prompt, char_count, word_count, is_sidechain, ts) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (pid, sid, cwd, p, len(p), len(p.split()), 0, ts),
        )

    for j in range(ai_turns):
        offset = 0.0005 + j * 0.0003
        mid = f"{sid}-a{j}"
        ts = _ts(days_ago - offset)
        # Vary token amounts by turn so charts look natural
        out_tokens = max(50, int(rng.gauss(out_per_turn, out_per_turn * 0.4)))
        inp = max(100, int(rng.gauss(out_tokens * 0.2, 200)))
        cache_read = max(0, int(rng.gauss(out_tokens * 8, 2000)))
        cache_creation = max(0, int(rng.gauss(out_tokens * 0.5, 500)))
        tools_this = max(0, int(rng.gauss(tool_per_turn, tool_per_turn * 0.5))) if tool_choices else 0
        names = (
            ",".join(sorted(set(rng.choice(tool_choices) for _ in range(min(tools_this, 4)))))
            if tools_this
            else ""
        )
        conn.execute(
            "INSERT OR IGNORE INTO token_usage(msg_id, session_id, cwd, model, input_tokens, output_tokens, "
            "cache_read_tokens, cache_creation_tokens, total_tokens, text_chars, tool_use_count, tool_names, is_sidechain, ts) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                mid, sid, cwd, model,
                inp, out_tokens, cache_read, cache_creation,
                inp + out_tokens + cache_read + cache_creation,
                int(out_tokens * 4),  # rough chars
                tools_this, names, 0, ts,
            ),
        )


def build(locale: str):
    if locale == "en":
        projects = EN_PROJECTS
        repeats = EN_REPEATS
        top_firsts = EN_TOP_FIRSTS
        bot_firsts = EN_BOT_FIRSTS
        topics = EN_TOPICS
        archive = EN_ARCHIVE
    else:
        projects = KO_PROJECTS
        repeats = KO_REPEATS
        top_firsts = KO_TOP_FIRSTS
        bot_firsts = KO_BOT_FIRSTS
        topics = KO_TOPICS
        archive = KO_ARCHIVE

    rng = random.Random(42 if locale == "en" else 43)

    # Wipe DB so the snapshot is reproducible
    db_path = Path.home() / ".claude" / "omp.db"
    if db_path.exists():
        db_path.unlink()

    conn = open_db()

    BASH = "Bash"
    READ = "Read"
    EDIT = "Edit"
    WRITE = "Write"
    AGENT = "Agent"
    TOOLS = [BASH, READ, EDIT, WRITE, AGENT, BASH, READ, BASH, READ]  # Bash/Read weighted

    sid_n = 0

    # Top-leverage sessions
    for i, first in enumerate(top_firsts):
        sid_n += 1
        sid = f"top-{sid_n:03d}"
        cwd = projects[i % len(projects)]
        follow_ups = [rng.choice(topics) for _ in range(rng.randint(2, 5))]
        _ingest_session(
            conn, sid, cwd, first, follow_ups,
            model="claude-opus-4-7",
            ai_turns=rng.randint(50, 90),
            out_per_turn=rng.randint(2500, 4500),
            tool_per_turn=rng.randint(8, 16),
            tool_choices=TOOLS,
            days_ago=rng.uniform(1, 6),
            rng=rng,
        )

    # Bottom-leverage sessions
    for i, first in enumerate(bot_firsts):
        sid_n += 1
        sid = f"bot-{sid_n:03d}"
        cwd = projects[(i + 3) % len(projects)]
        _ingest_session(
            conn, sid, cwd, first, [],
            model=_model_for_session(rng),
            ai_turns=rng.randint(1, 3),
            out_per_turn=rng.randint(150, 400),
            tool_per_turn=rng.randint(0, 1),
            tool_choices=TOOLS,
            days_ago=rng.uniform(1, 28),
            rng=rng,
        )

    # Mid-leverage sessions — pad to ~50 sessions and emit the repeats
    for prompt, count in repeats:
        for k in range(count):
            sid_n += 1
            sid = f"rep-{sid_n:03d}"
            cwd = rng.choice(projects)
            follow_ups = [rng.choice(topics) for _ in range(rng.randint(1, 3))]
            _ingest_session(
                conn, sid, cwd, prompt, follow_ups,
                model=_model_for_session(rng),
                ai_turns=rng.randint(8, 25),
                out_per_turn=rng.randint(400, 1500),
                tool_per_turn=rng.randint(2, 6),
                tool_choices=TOOLS,
                days_ago=rng.uniform(1, 28),
                rng=rng,
            )

    conn.commit()
    conn.close()

    # Mock archive
    if ARCHIVE.exists():
        for f in ARCHIVE.iterdir():
            f.unlink()
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    for name, content in archive:
        (ARCHIVE / name).write_text(content, encoding="utf-8")

    return db_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--locale", choices=["en", "ko"], required=True)
    args = ap.parse_args()
    p = build(args.locale)
    print(f"mock DB written: {p}  (locale={args.locale})")


if __name__ == "__main__":
    main()
