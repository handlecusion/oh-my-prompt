<h1 align="center">oh-my-prompt</h1>

<p align="center">
  <strong>뭐가 잘 됐는지 추측 그만. 내 프롬프트가 답을 줍니다.</strong>
</p>

<p align="center">
  <a href="README.md">English</a> |
  <a href="README.ko-KR.md">한국어</a>
</p>

<p align="center">
  <a href="https://github.com/handlecusion/oh-my-prompt/stargazers"><img src="https://img.shields.io/github/stars/handlecusion/oh-my-prompt?style=flat-square" alt="Stars"></a>
  <a href="https://github.com/handlecusion/oh-my-prompt/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square" alt="MIT Licence"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue.svg?style=flat-square" alt="Python 3.10+"></a>
  <a href="https://docs.claude.com/en/docs/claude-code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-blueviolet?style=flat-square" alt="Claude Code plugin"></a>
  <a href="https://www.sqlite.org/"><img src="https://img.shields.io/badge/storage-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite"></a>
  <img src="https://img.shields.io/badge/local--first-100%25-success?style=flat-square" alt="local-first">
</p>

내가 쓴 프롬프트, 토큰, 도구 호출, 세션 정보를 로컬 SQLite에 쌓아두고:

- 자주 반복되는 짧은 지시 → `CLAUDE.md` / 메모리 / 슬래시 커맨드 후보로 자동 제안
- 효율 높은 세션과 낮은 세션을 비교해 "어떤 식으로 시작했을 때 잘 됐는지" 찾기
- 분석 결과를 서브에이전트에 넘겨 패치 초안까지 자동 생성

100% 로컬에서 동작. 외부 전송 없음. API 키 불필요 (`claude` CLI 인증 그대로 사용).

---

## 빠른 시작

```
/plugin marketplace add github.com/handlecusion/oh-my-prompt
/plugin install omp@oh-my-prompt
```

`UserPromptSubmit` / `Stop` 훅이 자동 등록되고 `~/.claude/omp.db`에 데이터가 쌓이기 시작함. 세션 한두 번 돌린 뒤:

```
/omp:dashboard
```

한 페이지 안에 Stats · Patterns · Efficiency · Suggest 보관함이 탭으로 다 들어있음.

---

## 슬래시 커맨드

| 커맨드 | 인자 | 설명 |
|---|---|---|
| `/omp:stats [days]` | 일수 (기본 7) | 일별 토큰, 모델별 사용량, 세션 통계, 프로젝트별 분포 — 웹 대시보드 |
| `/omp:patterns [days] [min]` | 30, 3 | 반복 지시·의도 분포·첫 4단어 패턴·CLAUDE.md 후보 |
| `/omp:efficiency [days] [min]` | 30, 3 | 세션별 지렛대/자율도/도구 메트릭, 상하위 20% 비교, 첫 프롬프트 분석 |
| `/omp:suggest [days] [min]` | 30, 3 | 위 두 분석을 Opus 서브에이전트에 넘겨 규칙/메모리/슬래시 후보를 `~/.claude/omp_suggestions/<timestamp>.md`에 저장 |
| `/omp:suggest-archive` | — | 누적된 `~/.claude/omp_suggestions/`를 사이드바 뷰어로 열기 |
| `/omp:dashboard [stats_days] [days] [min]` | 7, 30, 3 | 위 네 패널을 한 페이지의 탭으로 통합 (`1`-`4` / `j`/`k` / 방향키 전환) |

---

## 스크린샷

> 스크린샷은 다음 커밋에서 추가됩니다 (README 정비 계획 Day 2).

---

## 설치 (옵션 2: 직접 클론)

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

- **위치**: `~/.claude/omp.db` (SQLite, 권한 `0600`)
- **테이블 2개**:
  - `prompts(prompt_id UNIQUE, session_id, cwd, prompt, char_count, word_count, is_sidechain, ts)`
  - `token_usage(msg_id UNIQUE, session_id, cwd, model, input/output/cache_*_tokens, text_chars, tool_use_count, tool_names, is_sidechain, ts)`
- **dedup 키**: 트랜스크립트의 `promptId` / 메시지 `id`. 라이브 훅과 백필이 충돌 없이 같은 데이터를 공유함.
- **시크릿**: 저장 전 `redact()`가 anthropic / openai / slack / github / google / aws 키 + JWT 패턴을 마스킹. 일반 고엔트로피 문자열은 false positive를 피하려 의도적으로 매칭하지 않음.

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

## 보안 / 프라이버시

- 모든 처리는 로컬. 외부 네트워크 호출 없음.
- DB와 suggestion 보관함은 매 open 시 `0600`/`0700`으로 chmod.
- 생성된 대시보드 HTML은 `$TMPDIR/omp-<uid>/`(권한 `0700`)에 저장되며 7일 지난 파일은 다음 실행 때 자동 prune.
- 인라인 JSON `</` 이스케이프, 사용자 문자열 `escapeHtml`, suggest-archive 마크다운 뷰어는 DOMPurify 통과, 모든 CDN 스크립트는 SRI 핀 고정.

자세한 내용 및 신고 채널은 [`SECURITY.md`](./SECURITY.md) 참고.

---

## 기여

[`CONTRIBUTING.md`](./CONTRIBUTING.md) 참고. 이슈/PR 환영 — 특히 `redact()` 패턴 추가, 새 분석기 아이디어가 도움됨.

## 라이선스

[MIT](./LICENSE)
