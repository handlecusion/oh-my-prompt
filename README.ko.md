[English](./README.md)

# oh-my-prompt

> Claude Code 사용 패턴을 분석해 **더 적은 프롬프트로 더 많은 결과**를 끌어내기 위한 플러그인

내가 쓴 프롬프트, 토큰, 도구 호출, 세션 정보를 로컬 SQLite에 쌓아두고:

- 자주 반복되는 짧은 지시 → `CLAUDE.md` / 메모리 / 슬래시 커맨드 후보로 자동 제안
- 효율 높은 세션과 낮은 세션을 비교해 "어떤 식으로 시작했을 때 잘 됐는지" 찾기
- 분석 결과를 서브에이전트에 넘겨 패치 초안까지 자동 생성

100% 로컬에서 동작. 외부 전송 없음. API 키 불필요 (`claude` CLI 인증 그대로 사용).

---

## 슬래시 커맨드

| 커맨드 | 인자 | 설명 |
|---|---|---|
| `/omp:stats [days]` | 일수 (기본 7) | 일별 토큰, 모델별 사용량, 세션 통계, 프로젝트별 분포 — 웹 대시보드 |
| `/omp:patterns [days] [min]` | 30, 3 | 반복 지시·의도 분포·첫 4단어 패턴·CLAUDE.md 후보 — 웹 대시보드 |
| `/omp:efficiency [days] [min]` | 30, 3 | 세션별 지렛대/자율도/도구 메트릭, 상하위 20% 비교, 첫 프롬프트 분석 — 웹 대시보드 |
| `/omp:suggest [days] [min]` | 30, 3 | 위 두 분석을 Opus 서브에이전트에 넘겨 규칙/메모리/슬래시 후보를 `~/.claude/omp_suggestions/<timestamp>.md`에 저장 |
| `/omp:suggest-archive` | — | 누적된 `~/.claude/omp_suggestions/`를 사이드바 뷰어로 열기 |
| `/omp:dashboard [stats_days] [days] [min]` | 7, 30, 3 | 위 네 패널을 한 페이지의 탭으로 통합 (`1`-`4` / `j`/`k` / 방향키 전환) |

---

## 설치

### 옵션 1: 플러그인 마켓플레이스 (권장)

```
/plugin marketplace add github.com/handlecusion/oh-my-prompt
/plugin install omp@oh-my-prompt
```

설치하면 `UserPromptSubmit` / `Stop` 훅이 자동으로 등록되고, `~/.claude/omp.db`에 데이터가 쌓이기 시작함. 첫 실행 후:

```
/omp:stats
```

### 옵션 2: 직접 클론 후 settings.json 수동 등록

```bash
git clone https://github.com/handlecusion/oh-my-prompt ~/Code/oh-my-prompt
```

`~/.claude/settings.json` 의 `hooks` 에 추가:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{ "type": "command", "command": "python3 ~/Code/oh-my-prompt/hooks/prompt_logger.py", "async": true }]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{ "type": "command", "command": "python3 ~/Code/oh-my-prompt/hooks/token_logger.py", "async": true }]
    }]
  }
}
```

### 백필 (과거 트랜스크립트 import)

`~/.claude/projects/**/*.jsonl` 의 모든 과거 세션을 한 번에 인제스트:

```bash
python3 ~/Code/oh-my-prompt/hooks/backfill.py
```

UPSERT 기반이라 여러 번 돌려도 안전 (새 세션만 추가됨).

---

## 데이터

- **위치**: `~/.claude/omp.db` (SQLite)
- **테이블 2개**:
  - `prompts(prompt_id UNIQUE, session_id, cwd, prompt, char_count, word_count, is_sidechain, ts)`
  - `token_usage(msg_id UNIQUE, session_id, cwd, model, input/output/cache_*_tokens, text_chars, tool_use_count, tool_names, is_sidechain, ts)`
- **dedup 키**: 트랜스크립트의 `promptId` / 메시지 `id`. 라이브 훅과 백필이 충돌 없이 같은 데이터를 공유함.

raw SQL이 편하면:

```bash
sqlite3 ~/.claude/omp.db "SELECT cwd, COUNT(*), SUM(total_tokens) FROM token_usage GROUP BY cwd ORDER BY 3 DESC LIMIT 10;"
```

---

## 분석 메트릭 의미

- **leverage** = `output_tokens / user_prompts` — 한 프롬프트당 얼마나 길게 답했는가
- **autonomy** = `assistant_turns / user_prompts` — 사용자 끼어들기 사이 평균 턴 수 (높을수록 한 번 시켜놓고 길게 자율 진행)
- **tools_per_prompt** — 한 프롬프트 후 도구를 몇 번 호출했는가

상위 leverage 세션의 첫 프롬프트가 길고 컨텍스트가 명확하면 → "긴 첫 프롬프트가 효과적"이라는 시그널.

---

## 라이선스

MIT
