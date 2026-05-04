#!/usr/bin/env python3
"""분석 결과를 모아 `claude -p`로 보내 CLAUDE.md/메모리/hook 후보 패치 초안을 생성"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def capture(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = r.stdout
    if r.returncode != 0 and r.stderr:
        out += "\n[stderr]\n" + r.stderr
    return out


def main():
    days = sys.argv[1] if len(sys.argv) > 1 else "30"
    min_count = sys.argv[2] if len(sys.argv) > 2 else "3"

    patterns = capture(["python3", str(ROOT / "lib/analyzers/patterns.py"), days, min_count])
    efficiency = capture(["python3", str(ROOT / "lib/analyzers/efficiency.py"), days, min_count])

    prompt = f"""아래는 한 사용자의 최근 {days}일 Claude Code 사용 데이터 분석 결과야.
(이 사용자는 이미 자기 데이터를 동의 하에 본인이 보려고 분석했어. 너는 분석가 역할만 해.)

=== 반복 패턴 분석 ===
{patterns}

=== 효율 분석 ===
{efficiency}

이 데이터를 바탕으로 사용자가 "더 적은 프롬프트로 더 많이 끌어내기" 위해 즉시 적용 가능한 개선책을 다음 세 항목으로 정리해.
각 제안마다 (a) 위 분석의 어느 수치/패턴에서 나왔는지 한 줄 인용 (b) 적용 방법(어디에 어떻게 쓸 한 줄 텍스트인지)을 함께 적어.

## 1. CLAUDE.md에 추가할 동작 규칙
짧은 반복 지시 → 자동 행동 규칙으로 전환할 수 있는 것

## 2. 메모리에 저장할 사용자 선호/맥락
효율 높은 세션의 시작 방식·도구 사용 패턴에서 추출한 사용자 스타일

## 3. 슬래시 커맨드 / hook 후보
반복되는 다단계 작업

규칙:
- 한국어로, 항목당 2~4줄.
- 추측·일반론·"~할 수도 있다" 금지. 데이터에 근거한 것만.
- 제안할 게 빈약하면 솔직히 "이 카테고리에선 강한 시그널 없음"이라고 적어.
"""

    print("=" * 68)
    print("  oh-my-prompt: claude -p로 개선 제안 생성 중... (수십 초 소요)")
    print("=" * 68)
    sys.stdout.flush()

    # --print = -p, dangerously-skip-permissions로 내부 도구 사용 없이 빠르게 응답
    r = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"\nclaude CLI 호출 실패 (exit {r.returncode}):", file=sys.stderr)
        print(r.stderr, file=sys.stderr)
        sys.exit(1)
    print(r.stdout)


if __name__ == "__main__":
    main()
