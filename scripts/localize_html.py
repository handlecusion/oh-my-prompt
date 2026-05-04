#!/usr/bin/env python3
"""In-place swap of Korean dashboard chrome strings to English.

Used only to produce the English README screenshots. The runtime templates
stay Korean — this is a screenshot-time concern, not a runtime feature.

Usage:
    python3 scripts/localize_html.py /path/to/file.html [more.html ...]
"""

import sys
from pathlib import Path

# Order matters — longer phrases must come before their substrings.
SUBSTITUTIONS = [
    # titles / banners
    ("omp 통계 — 최근 7일", "omp stats — last 7 days"),
    ("omp 통계 — 최근 30일", "omp stats — last 30 days"),
    ("omp 패턴 — 최근 30일", "omp patterns — last 30 days"),
    ("omp 효율 — 최근 30일", "omp efficiency — last 30 days"),
    ("omp 패턴 — 최근 7일", "omp patterns — last 7 days"),

    # sidebar / nav
    ("Suggest Archive", "Suggest Archive"),

    # stats dashboard panels
    ("일별 토큰 사용량", "Daily token usage"),
    ("모델별 토큰", "Tokens by model"),
    ("프로젝트별 토큰 (상위 10)", "Tokens by project (top 10)"),
    ("프롬프트 길이 분포", "Prompt length distribution"),
    ("세션 통계", "Session stats"),

    # patterns dashboard panels + cards
    ("의도별 분포", "Intent distribution"),
    ("의도별 평균 프롬프트 길이", "Avg prompt length by intent"),
    ("정규화 후 동일 프롬프트 — CLAUDE.md/hook 1순위 후보", "Normalized repeated prompts — top CLAUDE.md / hook candidates"),
    ("첫 4단어 패턴 (지시 시작 방식)", "First 4 words (how prompts begin)"),
    ("자동 제안", "Auto suggestions"),
    ("사용자 프롬프트", "User prompts"),
    ("짧은 (<200자)", "Short (<200 chars)"),
    ("긴 (≥200자)", "Long (≥200 chars)"),
    ("반복 후보", "Repeat candidates"),
    ("시작 패턴", "Start patterns"),

    # efficiency dashboard panels + table headers
    ("전체 세션 메트릭 (중앙값 / 평균)", "Session metrics (median / mean)"),
    ("지렛대 상위 20% vs 하위 20%", "Leverage: top 20% vs bottom 20%"),
    ("상위 세션 첫 프롬프트", "Top sessions: first prompt"),
    ("하위 세션 첫 프롬프트", "Bottom sessions: first prompt"),
    ("도구 사용 분포 (상위 vs 하위)", "Tool usage (top vs bottom)"),
    ("프로젝트별 평균 지렛대 (세션≥2)", "Avg leverage by project (≥2 sessions)"),
    ("메트릭", "Metric"),
    ("중앙값", "Median"),
    ("평균", "Mean"),
    ("상위", "Top"),
    ("하위", "Bottom"),
    ("배율", "Ratio"),
    ("프로젝트", "Project"),
    ("세션", "Sessions"),
    ("프롬프트", "Prompts"),
    ("프롬프트 수", "Prompts"),
    ("AI 응답 턴", "AI response turns"),
    ("출력 토큰", "Output tokens"),
    ("응답 텍스트 길이(자)", "Response text length"),
    ("도구 호출 수", "Tool calls"),
    ("지렛대(out_tok/prompt)", "Leverage (out_tok/prompt)"),
    ("자율(turns/prompt)", "Autonomy (turns/prompt)"),
    ("도구/프롬프트", "Tools/prompt"),
    ("지렛대 (out_tok/prompt)", "Leverage (out_tok/prompt)"),
    ("자율도 (turns/prompt)", "Autonomy (turns/prompt)"),
    ("총 출력 토큰", "Total output tokens"),
    ("평균 프롬프트 길이(자)", "Avg prompt length (chars)"),

    # archive viewer
    ("저장된 분석이 없습니다.", "No saved analyses."),
    ("archive ·", "archive ·"),
    ("건", ""),

    # dashboard_all sidebar meta + footer
    ("일", "d"),
    ("최소", "min"),
    ("최근", "last"),
    ("3회", "3"),

    # stats summary cards
    ("입력 토큰", "Input tokens"),
    ("캐시 읽기", "Cache read"),
    ("캐시 생성", "Cache creation"),
    ("토큰 합계", "Total tokens"),
    ("토큰", "Tokens"),
    # `패턴` (pattern) contains `턴` — must be replaced FIRST or `패턴` becomes `패Turns`.
    ("좋은 패턴, 유지 권장", "good pattern, keep"),
    ("패턴", "pattern"),
    ("턴", "Turns"),
    ("입력+출력+캐시", "input + output + cache"),
    ("AI 응답", "AI responses"),
    ("세션 수", "Sessions"),
    ("평균 턴/세션", "Avg turns/session"),
    ("최대 턴/세션", "Max turns/session"),
    ("평균 토큰/세션", "Avg tokens/session"),
    ("최대 토큰/세션", "Max tokens/session"),

    # bucket labels
    ("0-99자", "0-99"),
    ("100-299자", "100-299"),
    ("300-599자", "300-599"),
    ("600-999자", "600-999"),
    ("1000자+", "1000+"),

    # chart axes
    ("입력", "input"),
    ("출력", "output"),
    ("캐시", "cache"),
    ("건수", "count"),
    ("평균 자수", "avg chars"),
    ("회", ""),

    # auto-suggestion bullets — these run BEFORE 프롬프트 → Prompts so the longer
    # phrase wins. Order matters!
    ("개의 짧은 Prompts가 3 이상 반복됨 → CLAUDE.md에 동작 규칙으로 추가하거나 슬래시 커맨드로 빼는 것 검토",
     " short prompts repeated 3+ times → consider promoting to a CLAUDE.md rule or a new slash command"),
    ("개의 짧은 프롬프트가", " short prompts repeated"),
    ("회 이상 반복됨 → CLAUDE.md에 동작 규칙으로 추가하거나 슬래시 커맨드로 빼는 것 검토",
     " or more times → consider promoting to a CLAUDE.md rule or a new slash command"),
    ("이미 슬래시 커맨드로 추출된 호출", "Already-extracted slash command calls:"),
    ("건 — 좋은 패턴, 유지 권장", " — good pattern, keep"),
    ("좋은 패턴, 유지 권장", "good pattern, keep"),
    ("좋은 패턴Turns, 유지 권장", "good pattern, keep"),
    ("좋은 패턴Turns,", "good pattern,"),

    # patterns meta line ("(시스템 의사-Prompts X 제외)")
    ("(시스템 의사-Prompts ", "(system pseudo-prompts excluded: "),
    ("제외)", ""),
    ("min 반복", "min repeats"),

    # patterns repeats table header
    ("횟수", "count"),

    # efficiency dashboard meta + leftovers
    (" sessions (prompts ≥3)", " sessions (≥3 prompts each)"),
    ("Prompts 수", "Prompts"),
    ("Sessions개 (Prompts 3 이상)", "sessions (≥3 prompts each)"),
    ("개 (Prompts 3 이상)", " (≥3 prompts each)"),
    ("개 (Prompts ", " (prompts ≥"),
    ("이상)", ")"),
    ("Sessions개", "sessions"),
    ("개", ""),
    ("도구/Prompts", "Tools/prompt"),
    ("도구", "Tools"),
    ("총 Output tokens", "Total output tokens"),
    ("총", "Total"),
    ("Mean Prompts 길이(자)", "Mean prompt length (chars)"),
    ("Prompts 길이(자)", "prompt length (chars)"),
    ("길이(자)", "length (chars)"),
    ("길이", "length"),
    ("지렛대", "Leverage"),
    ("/ Turns", "/ turn"),

    # meta lines
    ("생성 시각:", "generated:"),
    ("생성:", "generated:"),
    ("생성됩니다", "generated"),
    ("이 카테고리에선", "No strong signal"),

    # session count suffix
    ("개 (프롬프트", " sessions (prompts ≥"),
    ("회 이상)", ")"),
]


def localize(html: str) -> str:
    out = html
    for ko, en in SUBSTITUTIONS:
        out = out.replace(ko, en)
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    for arg in sys.argv[1:]:
        p = Path(arg)
        text = p.read_text(encoding="utf-8")
        p.write_text(localize(text), encoding="utf-8")
        print(f"localized: {p}")


if __name__ == "__main__":
    main()
