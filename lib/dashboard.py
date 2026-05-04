#!/usr/bin/env python3
"""omp 통계 대시보드 - HTML 생성 후 브라우저로 오픈"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _tmp import omp_tmpdir

DB_PATH = Path.home() / ".claude" / "omp.db"


def collect(days: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cutoff = f"date('now', '-{days} days')"

    summary_row = conn.execute(f"""
        SELECT COUNT(*) turns, COALESCE(SUM(input_tokens),0) inp,
               COALESCE(SUM(output_tokens),0) out,
               COALESCE(SUM(cache_read_tokens),0) cr,
               COALESCE(SUM(cache_creation_tokens),0) cc,
               COALESCE(SUM(total_tokens),0) tot
        FROM token_usage WHERE ts >= {cutoff}
    """).fetchone()
    prompts = conn.execute(f"SELECT COUNT(*) FROM prompts WHERE ts >= {cutoff}").fetchone()[0]
    sessions = conn.execute(f"SELECT COUNT(DISTINCT session_id) FROM token_usage WHERE ts >= {cutoff}").fetchone()[0]

    daily = [dict(r) for r in conn.execute(f"""
        SELECT date(ts) day, COUNT(*) turns,
               COALESCE(SUM(input_tokens),0) inp,
               COALESCE(SUM(output_tokens),0) out,
               COALESCE(SUM(cache_read_tokens),0) cache,
               COALESCE(SUM(total_tokens),0) total
        FROM token_usage WHERE ts >= {cutoff}
        GROUP BY day ORDER BY day ASC
    """).fetchall()]

    models = [dict(r) for r in conn.execute(f"""
        SELECT COALESCE(NULLIF(model,''),'(unknown)') model, COUNT(*) turns,
               COALESCE(SUM(total_tokens),0) total
        FROM token_usage WHERE ts >= {cutoff}
        GROUP BY model ORDER BY total DESC
    """).fetchall()]

    buckets = [dict(r) for r in conn.execute(f"""
        SELECT CASE
            WHEN char_count < 100  THEN '0-99자'
            WHEN char_count < 300  THEN '100-299자'
            WHEN char_count < 600  THEN '300-599자'
            WHEN char_count < 1000 THEN '600-999자'
            ELSE '1000자+'
        END bucket, COUNT(*) cnt,
        ROUND(AVG(char_count)) avg_c, MIN(char_count) min_c
        FROM prompts WHERE ts >= {cutoff}
        GROUP BY bucket ORDER BY min_c
    """).fetchall()]

    projects = [dict(r) for r in conn.execute(f"""
        SELECT cwd, COALESCE(SUM(total_tokens),0) total, COUNT(*) turns,
               COUNT(DISTINCT session_id) sessions
        FROM token_usage WHERE ts >= {cutoff}
        GROUP BY cwd ORDER BY total DESC LIMIT 10
    """).fetchall()]

    sess = conn.execute(f"""
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
    session_stats = dict(sess) if sess else {}

    conn.close()

    return {
        "days": days,
        "summary": {
            "sessions": sessions,
            "prompts": prompts,
            "ai_turns": summary_row["turns"] if summary_row else 0,
            "input": summary_row["inp"] if summary_row else 0,
            "output": summary_row["out"] if summary_row else 0,
            "cache_read": summary_row["cr"] if summary_row else 0,
            "cache_creation": summary_row["cc"] if summary_row else 0,
            "total": summary_row["tot"] if summary_row else 0,
        },
        "daily": daily,
        "models": models,
        "buckets": buckets,
        "projects": projects,
        "session_stats": session_stats,
    }


HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<title>omp 통계 — 최근 __DAYS__일</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"
        integrity="sha384-9nhczxUqK87bcKHh20fSQcTGD4qq5GhayNYSYWqwBkINBhOfQLg/P5HG5lF1urn4"
        crossorigin="anonymous"></script>
<style>
  :root {
    --bg: #0b0d10;
    --panel: #14181d;
    --border: #232830;
    --text: #e6e9ee;
    --muted: #8a93a0;
    --accent: #6ea8ff;
    --accent2: #5ad9b1;
    --warn: #ffb86b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 32px;
    background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Pretendard", sans-serif;
  }
  h1 { margin: 0 0 8px; font-size: 22px; font-weight: 600; }
  .sub { color: var(--muted); margin-bottom: 24px; font-size: 13px; }
  .grid { display: grid; gap: 16px; }
  .cards { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
  .card {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px;
  }
  .card .label { color: var(--muted); font-size: 12px; }
  .card .value { font-size: 22px; font-weight: 600; margin-top: 4px; }
  .card .sub2 { color: var(--muted); font-size: 11px; margin-top: 4px; }
  .row { grid-template-columns: 2fr 1fr; }
  @media (max-width: 900px) { .row { grid-template-columns: 1fr; } }
  .panel {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px;
  }
  .panel h2 { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 500; font-size: 11px; text-transform: uppercase; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  .proj { font-family: "SF Mono", ui-monospace, monospace; font-size: 12px; word-break: break-all; }
  canvas { max-height: 280px; }
  .footer { color: var(--muted); font-size: 11px; margin-top: 24px; }
</style>
</head>
<body>
  <h1>omp 통계 — 최근 __DAYS__일</h1>
  <div class="sub" id="meta"></div>

  <div class="grid cards" id="cards"></div>

  <div class="grid row" style="margin-top: 16px;">
    <div class="panel">
      <h2>일별 토큰 사용량</h2>
      <canvas id="dailyChart"></canvas>
    </div>
    <div class="panel">
      <h2>모델별 토큰</h2>
      <canvas id="modelChart"></canvas>
    </div>
  </div>

  <div class="grid row" style="margin-top: 16px;">
    <div class="panel">
      <h2>프로젝트별 토큰 (상위 10)</h2>
      <table id="projTable">
        <thead><tr><th>프로젝트</th><th class="num">토큰</th><th class="num">턴</th><th class="num">세션</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <div class="panel">
      <h2>프롬프트 길이 분포</h2>
      <canvas id="bucketChart"></canvas>
    </div>
  </div>

  <div class="panel" style="margin-top: 16px;">
    <h2>세션 통계</h2>
    <div class="grid cards" id="sessionCards"></div>
  </div>

  <div class="footer">DB: __DBPATH__</div>

<script>
const DATA = __DATA__;

function fmt(n) {
  if (!n) return "0";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

const s = DATA.summary;
const cards = [
  { label: "세션", value: s.sessions },
  { label: "프롬프트", value: s.prompts },
  { label: "AI 응답", value: s.ai_turns },
  { label: "입력 토큰", value: fmt(s.input) },
  { label: "출력 토큰", value: fmt(s.output) },
  { label: "캐시 읽기", value: fmt(s.cache_read) },
  { label: "캐시 생성", value: fmt(s.cache_creation) },
  { label: "토큰 합계", value: fmt(s.total), sub: "입력+출력+캐시" },
];
document.getElementById("cards").innerHTML = cards.map(c =>
  `<div class="card"><div class="label">${c.label}</div><div class="value">${c.value}</div>${c.sub ? `<div class="sub2">${c.sub}</div>` : ""}</div>`
).join("");

document.getElementById("meta").textContent = `생성 시각: ${new Date().toLocaleString()}`;

// daily chart
const daily = DATA.daily;
new Chart(document.getElementById("dailyChart"), {
  type: "bar",
  data: {
    labels: daily.map(d => d.day),
    datasets: [
      { label: "입력", data: daily.map(d => d.inp), backgroundColor: "#6ea8ff" },
      { label: "출력", data: daily.map(d => d.out), backgroundColor: "#5ad9b1" },
      { label: "캐시", data: daily.map(d => d.cache), backgroundColor: "#ffb86b" },
    ],
  },
  options: {
    responsive: true,
    plugins: { legend: { labels: { color: "#e6e9ee" } } },
    scales: {
      x: { stacked: true, ticks: { color: "#8a93a0" }, grid: { color: "#232830" } },
      y: { stacked: true, ticks: { color: "#8a93a0", callback: fmt }, grid: { color: "#232830" } },
    },
  },
});

// model chart
const models = DATA.models;
new Chart(document.getElementById("modelChart"), {
  type: "doughnut",
  data: {
    labels: models.map(m => m.model),
    datasets: [{
      data: models.map(m => m.total),
      backgroundColor: ["#6ea8ff", "#5ad9b1", "#ffb86b", "#c39bff", "#ff7b9c"],
    }],
  },
  options: {
    plugins: {
      legend: { position: "bottom", labels: { color: "#e6e9ee", font: { size: 11 } } },
      tooltip: { callbacks: { label: ctx => `${ctx.label}: ${fmt(ctx.parsed)}` } },
    },
  },
});

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}

// project table
const proj = DATA.projects;
document.querySelector("#projTable tbody").innerHTML = proj.map(p => {
  const path = p.cwd && p.cwd.length > 50 ? "..." + p.cwd.slice(-47) : (p.cwd || "");
  return `<tr><td class="proj">${escapeHtml(path)}</td><td class="num">${fmt(p.total)}</td><td class="num">${p.turns}</td><td class="num">${p.sessions}</td></tr>`;
}).join("");

// bucket chart
const buckets = DATA.buckets;
new Chart(document.getElementById("bucketChart"), {
  type: "bar",
  data: {
    labels: buckets.map(b => b.bucket),
    datasets: [{
      label: "프롬프트 수",
      data: buckets.map(b => b.cnt),
      backgroundColor: "#6ea8ff",
    }],
  },
  options: {
    indexAxis: "y",
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: "#8a93a0" }, grid: { color: "#232830" } },
      y: { ticks: { color: "#8a93a0" }, grid: { color: "#232830" } },
    },
  },
});

// session stats
const ss = DATA.session_stats || {};
const sessCards = [
  { label: "세션 수", value: ss.sessions ?? 0 },
  { label: "평균 턴/세션", value: ss.avg_turns ?? 0 },
  { label: "최대 턴/세션", value: ss.max_turns ?? 0 },
  { label: "평균 토큰/세션", value: fmt(ss.avg_tok || 0) },
  { label: "최대 토큰/세션", value: fmt(ss.max_tok || 0) },
];
document.getElementById("sessionCards").innerHTML = sessCards.map(c =>
  `<div class="card"><div class="label">${c.label}</div><div class="value">${c.value}</div></div>`
).join("");
</script>
</body>
</html>
"""


def _safe_json(d) -> str:
    # `</` would close the surrounding inline <script> tag and let attacker-controlled
    # content (e.g., a stored prompt with `</script><img onerror=...>`) execute.
    return json.dumps(d, ensure_ascii=False).replace("</", "<\\/")


def render(data: dict) -> str:
    return (HTML
            .replace("__DAYS__", str(data["days"]))
            .replace("__DBPATH__", str(DB_PATH))
            .replace("__DATA__", _safe_json(data)))


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    if not DB_PATH.exists():
        print("아직 데이터가 없습니다. 백필: python3 ~/.claude/hooks/backfill.py")
        return

    data = collect(days)
    html = render(data)

    out = omp_tmpdir() / "omp_dashboard.html"
    out.write_text(html, encoding="utf-8")

    try:
        subprocess.run(["open", str(out)], check=False)
    except FileNotFoundError:
        import webbrowser
        webbrowser.open(out.as_uri())

    print(f"대시보드 열림: {out}")


if __name__ == "__main__":
    main()
