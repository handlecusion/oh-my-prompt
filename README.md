# oh-my-prompt

> Claude Code 사용 패턴을 분석해 **더 적은 프롬프트로 더 많이** 끌어내기 위한 플러그인

내 프롬프트, 토큰, 세션 데이터를 로컬 SQLite에 쌓아두고:
- 자주 반복되는 지시를 찾아 `CLAUDE.md` / 메모리 / hook 후보로 제안
- 어떤 식으로 시작/지시했을 때 가장 효율 높은 세션이 나왔는지 비교
- `claude -p`를 호출해 분석 결과를 자동으로 개선 패치 초안으로 변환

100% 로컬 동작. 외부 전송 없음.

## 상태

v0.1 (스캐폴드) — 데이터 수집 + 통계 리포트만 구현.
이후 `/omp:patterns`, `/omp:efficiency`, `/omp:suggest` 추가 예정.

## 설치 (개발 중)

```bash
# 현재는 직접 클론 + ~/.claude/settings.json hook 등록 방식
git clone https://github.com/handlecusion/oh-my-prompt ~/Code/oh-my-prompt
```

후속 버전에서 `/plugin marketplace add github.com/handlecusion/oh-my-prompt` 지원 예정.

## 데이터

- DB 위치: `~/.claude/omp.db` (SQLite)
- 수집 대상: 프롬프트 텍스트, 모델별 토큰 사용량, 세션 ID, cwd, 타임스탬프
- 백필: `python3 hooks/backfill.py` 로 `~/.claude/projects/**/*.jsonl` 전체 인제스트

## 슬래시 커맨드

| 커맨드 | 설명 | 상태 |
|---|---|---|
| `/omp:stats [N일]` | 종합 통계 | v0.1 |
| `/omp:patterns` | 반복 지시 발견 + 개선 후보 | v0.3 예정 |
| `/omp:efficiency` | 고/저성과 세션 비교 | v0.4 예정 |
| `/omp:suggest` | 분석 결과를 CLAUDE.md/메모리 패치 초안으로 | v0.5 예정 |

## 라이선스

MIT
