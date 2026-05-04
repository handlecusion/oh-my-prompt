#!/usr/bin/env python3
"""반복 지시 패턴 분석.

- collect_data(): 데이터 dict 반환 (텍스트/HTML 양쪽에서 공유)
- render_text(): 기존 콘솔 출력 (suggest_prep 등 프로그램 소비용)
- render_html(): /omp:patterns 웹 대시보드용
- CLI 기본 = 웹 출력. `--text` 플래그를 주면 텍스트 출력.
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from io import StringIO
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "omp.db"


def omp_tmpdir() -> Path:
    """Per-user tempdir; avoids predictable-name symlink races on shared /tmp."""
    base = Path(tempfile.gettempdir())
    uid = getattr(os, "getuid", lambda: 0)()
    d = base / f"omp-{uid}"
    d.mkdir(mode=0o700, exist_ok=True)
    try:
        d.chmod(0o700)
    except OSError:
        pass
    return d

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
    if s.startswith("<") and re.match(r"<[a-zA-Z][\w-]*", s):
        return True
    return False


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


def truncate(s: str, n: int) -> str:
    s = s.replace("\n", " ⏎ ")
    return s if len(s) <= n else s[: n - 1] + "…"


def collect_data(days: int = 30, min_count: int = 3) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cutoff = f"date('now', '-{days} days')"

    raw = conn.execute(f"""
        SELECT prompt, char_count, ts FROM prompts
        WHERE ts >= {cutoff} AND COALESCE(is_sidechain,0) = 0
    """).fetchall()
    conn.close()

    rows = [r for r in raw if r[0] and not is_system_msg(r[0])]
    skipped = len(raw) - len(rows)

    if not rows:
        return {
            "days": days, "min_count": min_count, "total": 0, "skipped": skipped,
            "short_count": 0, "long_count": 0,
            "intents": [], "repeats": [], "starts": [], "intent_lengths": [],
            "suggestions": [], "db_path": str(DB_PATH),
        }

    total = len(rows)
    short_prompts = [r[0] for r in rows if r[1] < 200]
    long_prompts = [r[0] for r in rows if r[1] >= 200]

    intents_c = Counter(tag_intent(p) for p in (r[0] for r in rows))
    intents = [
        {"tag": t, "count": c, "pct": round(c / total * 100, 1)}
        for t, c in intents_c.most_common()
    ]

    norm_counter = Counter()
    norm_to_orig = {}
    for p in short_prompts:
        n = normalize(p)
        if not n or len(n) < 3:
            continue
        norm_counter[n] += 1
        norm_to_orig.setdefault(n, p)
    repeats = [
        {"count": c, "prompt": norm_to_orig[n]}
        for n, c in norm_counter.most_common(20) if c >= min_count
    ]

    starts_c = Counter()
    for r in rows:
        s = first_words(r[0], 4)
        if len(s) < 5:
            continue
        starts_c[s] += 1
    starts = [
        {"count": c, "words": s}
        for s, c in starts_c.most_common(15) if c >= min_count
    ]

    by_intent = {}
    for r in rows:
        t = tag_intent(r[0])
        by_intent.setdefault(t, []).append(r[1] or 0)
    intent_lengths = []
    for tag in sorted(by_intent.keys(), key=lambda k: -len(by_intent[k]))[:10]:
        lens = by_intent[tag]
        avg = sum(lens) / len(lens) if lens else 0
        intent_lengths.append({"tag": tag, "count": len(lens), "avg_chars": int(avg)})

    suggestions = []
    if repeats:
        suggestions.append(
            f"{len(repeats)}개의 짧은 프롬프트가 {min_count}회 이상 반복됨 → "
            "CLAUDE.md에 동작 규칙으로 추가하거나 슬래시 커맨드로 빼는 것 검토"
        )
    if intents_c.get("undo", 0) > total * 0.05:
        suggestions.append(
            f"'undo/취소/그거말고' 류가 {intents_c['undo']}건 ({intents_c['undo']/total*100:.0f}%) — "
            "프롬프트에 더 명시적인 제약을 거는 게 효율적일 수 있음"
        )
    if intents_c.get("ack", 0) > total * 0.10:
        suggestions.append(
            f"단순 응답('ok/응/굿' 등)이 {intents_c['ack']}건 — "
            "Stop hook이나 메모리에 사용자 톤을 저장해 자동화 여지 있음"
        )
    if intents_c.get("slash", 0) > 0:
        suggestions.append(
            f"이미 슬래시 커맨드로 추출된 호출 {intents_c['slash']}건 — 좋은 패턴, 유지 권장"
        )
    if not suggestions:
        suggestions.append("특별히 두드러진 반복 패턴 없음")

    return {
        "days": days,
        "min_count": min_count,
        "total": total,
        "skipped": skipped,
        "short_count": len(short_prompts),
        "long_count": len(long_prompts),
        "intents": intents,
        "repeats": repeats,
        "starts": starts,
        "intent_lengths": intent_lengths,
        "suggestions": suggestions,
        "db_path": str(DB_PATH),
    }


def render_text(d: dict) -> str:
    out = StringIO()

    def section(title):
        out.write(f"\n{'='*64}\n  {title}\n{'='*64}\n")

    if d["total"] == 0:
        out.write(f"최근 {d['days']}일에 사용자 프롬프트가 없습니다.\n")
        return out.getvalue()

    out.write(f"\n분석 대상: 최근 {d['days']}일 사용자 프롬프트 {d['total']}건"
              f"  (시스템 의사-프롬프트 {d['skipped']}건 제외)\n")
    out.write(f"  짧은 프롬프트 (<200자): {d['short_count']}  |  "
              f"긴 프롬프트 (>=200자): {d['long_count']}\n")

    section("의도별 분포")
    for it in d["intents"]:
        bar = "#" * min(it["count"], 40)
        out.write(f"  {it['tag']:<12} {it['count']:>4}건 ({it['pct']:5.1f}%)  {bar}\n")

    section("정규화 후 동일 프롬프트 (반복 지시) — CLAUDE.md/hook 1순위 후보")
    if d["repeats"]:
        out.write(f"  {'횟수':>4}  프롬프트\n")
        out.write(f"  {'-'*60}\n")
        for r in d["repeats"]:
            out.write(f"  {r['count']:>4}회  {truncate(r['prompt'], 56)}\n")
    else:
        out.write(f"  {d['min_count']}회 이상 반복된 짧은 프롬프트 없음\n")

    section("첫 4단어 패턴 (지시 시작 방식)")
    if d["starts"]:
        for s in d["starts"]:
            bar = "#" * min(s["count"], 30)
            out.write(f"  {s['count']:>4}회  {truncate(s['words'], 40):<42} {bar}\n")
    else:
        out.write("  반복되는 시작 패턴 없음\n")

    section("의도별 평균 프롬프트 길이")
    for il in d["intent_lengths"]:
        out.write(f"  {il['tag']:<12} {il['count']:>4}건  평균 {il['avg_chars']:>5}자\n")

    section("자동 제안")
    for s in d["suggestions"]:
        out.write(f"  • {s}\n")

    out.write(f"\n  DB: {d['db_path']}\n")
    return out.getvalue()


HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<title>omp 패턴 — 최근 __DAYS__일</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"
        integrity="sha384-9nhczxUqK87bcKHh20fSQcTGD4qq5GhayNYSYWqwBkINBhOfQLg/P5HG5lF1urn4"
        crossorigin="anonymous"></script>
<style>
  :root { --bg:#0b0d10; --panel:#14181d; --border:#232830; --text:#e6e9ee;
          --muted:#8a93a0; --accent:#6ea8ff; --accent2:#5ad9b1; --warn:#ffb86b; }
  * { box-sizing: border-box; }
  body { margin:0; padding:32px; background:var(--bg); color:var(--text);
         font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Pretendard",sans-serif; }
  h1 { margin:0 0 8px; font-size:22px; font-weight:600; }
  .sub { color:var(--muted); margin-bottom:24px; font-size:13px; }
  .grid { display:grid; gap:16px; }
  .cards { grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); }
  .card { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:16px; }
  .card .label { color:var(--muted); font-size:12px; }
  .card .value { font-size:22px; font-weight:600; margin-top:4px; }
  .row { grid-template-columns:1fr 1fr; }
  @media (max-width:900px) { .row { grid-template-columns:1fr; } }
  .panel { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:16px; }
  .panel h2 { margin:0 0 12px; font-size:14px; font-weight:600; color:var(--muted);
              text-transform:uppercase; letter-spacing:0.5px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--border); }
  th { color:var(--muted); font-weight:500; font-size:11px; text-transform:uppercase; }
  td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
  td.prompt { font-family:"SF Mono",ui-monospace,monospace; font-size:12px; word-break:break-all; }
  canvas { max-height:320px; }
  ul.suggest { margin:0; padding-left:20px; line-height:1.7; }
  ul.suggest li { color:var(--text); font-size:13px; }
  .footer { color:var(--muted); font-size:11px; margin-top:24px; }
  .empty { color:var(--muted); padding:40px; text-align:center; }
</style>
</head>
<body>
  <h1>omp 패턴 — 최근 __DAYS__일</h1>
  <div class="sub" id="meta"></div>

  <div class="grid cards" id="cards"></div>

  <div class="grid row" style="margin-top:16px;">
    <div class="panel">
      <h2>의도별 분포</h2>
      <canvas id="intentChart"></canvas>
    </div>
    <div class="panel">
      <h2>의도별 평균 프롬프트 길이</h2>
      <canvas id="lenChart"></canvas>
    </div>
  </div>

  <div class="panel" style="margin-top:16px;">
    <h2>정규화 후 동일 프롬프트 — CLAUDE.md/hook 1순위 후보</h2>
    <table id="repeatTable">
      <thead><tr><th class="num">횟수</th><th>프롬프트</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <div class="panel" style="margin-top:16px;">
    <h2>첫 4단어 패턴 (지시 시작 방식)</h2>
    <canvas id="startChart"></canvas>
  </div>

  <div class="panel" style="margin-top:16px;">
    <h2>자동 제안</h2>
    <ul class="suggest" id="suggestList"></ul>
  </div>

  <div class="footer">DB: __DBPATH__</div>

<script>
const DATA = __DATA__;

document.getElementById("meta").textContent =
  `사용자 프롬프트 ${DATA.total}건 (시스템 의사-프롬프트 ${DATA.skipped}건 제외) · ` +
  `최소 반복 ${DATA.min_count}회 · 생성: ${new Date().toLocaleString()}`;

if (DATA.total === 0) {
  document.querySelector("body").innerHTML +=
    '<div class="empty">최근 ' + DATA.days + '일에 사용자 프롬프트가 없습니다.</div>';
} else {
  const cards = [
    { label: "사용자 프롬프트", value: DATA.total },
    { label: "짧은 (<200자)", value: DATA.short_count },
    { label: "긴 (≥200자)", value: DATA.long_count },
    { label: "반복 후보", value: DATA.repeats.length },
    { label: "시작 패턴", value: DATA.starts.length },
  ];
  document.getElementById("cards").innerHTML = cards.map(c =>
    `<div class="card"><div class="label">${c.label}</div><div class="value">${c.value}</div></div>`
  ).join("");

  // intent chart
  const intents = DATA.intents;
  new Chart(document.getElementById("intentChart"), {
    type: "bar",
    data: {
      labels: intents.map(i => i.tag),
      datasets: [{ label: "건수", data: intents.map(i => i.count), backgroundColor: "#6ea8ff" }],
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${ctx.parsed.x}건 (${intents[ctx.dataIndex].pct}%)` } } },
      scales: {
        x: { ticks: { color: "#8a93a0" }, grid: { color: "#232830" } },
        y: { ticks: { color: "#8a93a0" }, grid: { color: "#232830" } },
      },
    },
  });

  // length chart
  const lens = DATA.intent_lengths;
  new Chart(document.getElementById("lenChart"), {
    type: "bar",
    data: {
      labels: lens.map(l => l.tag),
      datasets: [{ label: "평균 자수", data: lens.map(l => l.avg_chars), backgroundColor: "#5ad9b1" }],
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: ctx => `평균 ${ctx.parsed.x}자 · ${lens[ctx.dataIndex].count}건` } } },
      scales: {
        x: { ticks: { color: "#8a93a0" }, grid: { color: "#232830" } },
        y: { ticks: { color: "#8a93a0" }, grid: { color: "#232830" } },
      },
    },
  });

  // repeats table
  document.querySelector("#repeatTable tbody").innerHTML =
    DATA.repeats.length
      ? DATA.repeats.map(r =>
          `<tr><td class="num">${r.count}회</td><td class="prompt">${escapeHtml(r.prompt)}</td></tr>`
        ).join("")
      : '<tr><td colspan="2" class="empty">최소 반복 횟수 이상의 짧은 프롬프트 없음</td></tr>';

  // starts chart
  const starts = DATA.starts;
  if (starts.length) {
    new Chart(document.getElementById("startChart"), {
      type: "bar",
      data: {
        labels: starts.map(s => s.words),
        datasets: [{ label: "건수", data: starts.map(s => s.count), backgroundColor: "#ffb86b" }],
      },
      options: {
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "#8a93a0" }, grid: { color: "#232830" } },
          y: { ticks: { color: "#8a93a0", font: { family: "SF Mono, ui-monospace, monospace" } },
                grid: { color: "#232830" } },
        },
      },
    });
  } else {
    document.getElementById("startChart").outerHTML =
      '<div class="empty">반복되는 시작 패턴 없음</div>';
  }

  document.getElementById("suggestList").innerHTML =
    DATA.suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join("");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}
</script>
</body>
</html>
"""


def _safe_json(d) -> str:
    # Prevent `</script>` in stored prompts from breaking out of the inline data block.
    return json.dumps(d, ensure_ascii=False).replace("</", "<\\/")


def render_html(d: dict) -> str:
    return (HTML
            .replace("__DAYS__", str(d["days"]))
            .replace("__DBPATH__", d["db_path"])
            .replace("__DATA__", _safe_json(d)))


def main():
    args = [a for a in sys.argv[1:] if a]
    text_mode = "--text" in args
    args = [a for a in args if a != "--text"]

    days = int(args[0]) if len(args) > 0 else 30
    min_count = int(args[1]) if len(args) > 1 else 3

    if not DB_PATH.exists():
        print("아직 데이터가 없습니다. 백필: python3 ~/.claude/hooks/backfill.py")
        return

    data = collect_data(days, min_count)

    if text_mode:
        sys.stdout.write(render_text(data))
        return

    html = render_html(data)
    out = omp_tmpdir() / "omp_patterns.html"
    out.write_text(html, encoding="utf-8")

    try:
        subprocess.run(["open", str(out)], check=False)
    except FileNotFoundError:
        import webbrowser
        webbrowser.open(out.as_uri())

    print(f"패턴 대시보드 열림: {out}")


if __name__ == "__main__":
    main()
