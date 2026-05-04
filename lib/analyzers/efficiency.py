#!/usr/bin/env python3
"""세션 효율 분석.

- collect_data(): 데이터 dict 반환
- render_text(): 콘솔 출력 (suggest_prep 등 프로그램 소비용)
- render_html(): /omp:efficiency 웹 대시보드용
- CLI 기본 = 웹 출력. `--text` 플래그를 주면 텍스트 출력.
"""

import json
import sqlite3
import subprocess
import sys
from io import StringIO
from pathlib import Path
from statistics import mean, median

# add `lib/` to sys.path so we can import the shared _tmp helper
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _tmp import omp_tmpdir

DB_PATH = Path.home() / ".claude" / "omp.db"


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


def tool_distribution(conn, sids):
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


def percentile_split(sessions, key, top_pct=0.20, bot_pct=0.20):
    if not sessions:
        return [], []
    s = sorted(sessions, key=lambda x: x[key], reverse=True)
    n = len(s)
    top_n = max(1, int(n * top_pct))
    bot_n = max(1, int(n * bot_pct))
    return s[:top_n], s[-bot_n:]


METRIC_LABELS = [
    ("프롬프트 수", "prompts"),
    ("AI 응답 턴", "turns"),
    ("출력 토큰", "out_tokens"),
    ("응답 텍스트 길이(자)", "text_chars"),
    ("도구 호출 수", "tools"),
    ("지렛대(out_tok/prompt)", "leverage"),
    ("자율(turns/prompt)", "autonomy"),
    ("도구/프롬프트", "tools_per_prompt"),
]

COMPARE_LABELS = [
    ("지렛대 (out_tok/prompt)", "leverage"),
    ("자율도 (turns/prompt)", "autonomy"),
    ("프롬프트 수", "prompts"),
    ("총 출력 토큰", "out_tokens"),
    ("도구 호출 수", "tools"),
    ("도구/프롬프트", "tools_per_prompt"),
    ("평균 프롬프트 길이(자)", "avg_pchars"),
]


def collect_data(days: int = 30, min_prompts: int = 3) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cutoff = f"date('now', '-{days} days')"

    sessions = collect_sessions(conn, cutoff)
    sessions = [s for s in sessions if s["prompts"] >= min_prompts]

    if not sessions:
        conn.close()
        return {
            "days": days, "min_prompts": min_prompts, "session_count": 0,
            "summary": [], "compare": [],
            "top_first": [], "bot_first": [],
            "tools": [], "projects": [], "db_path": str(DB_PATH),
        }

    summary = []
    for label, k in METRIC_LABELS:
        vals = [s[k] for s in sessions]
        summary.append({"label": label, "median": median(vals), "mean": mean(vals)})

    top, bot = percentile_split(sessions, "leverage")
    compare = []
    for label, k in COMPARE_LABELS:
        t = mean(x[k] for x in top) if top else 0
        b = mean(x[k] for x in bot) if bot else 0
        ratio = (t / b) if b > 0 else None
        compare.append({"label": label, "top": t, "bot": b, "ratio": ratio})

    top_first = []
    for s in top[:5]:
        fp = first_prompt(conn, s["sid"])
        top_first.append({
            "leverage": s["leverage"],
            "cwd": s["cwd"],
            "cwd_name": Path(s["cwd"]).name or "(no cwd)",
            "prompt": fp,
        })

    bot_first = []
    for s in bot[:5]:
        fp = first_prompt(conn, s["sid"])
        bot_first.append({
            "leverage": s["leverage"],
            "cwd": s["cwd"],
            "cwd_name": Path(s["cwd"]).name or "(no cwd)",
            "prompt": fp,
        })

    top_tools = tool_distribution(conn, [s["sid"] for s in top])
    bot_tools = tool_distribution(conn, [s["sid"] for s in bot])
    all_tools = sorted(
        set(top_tools) | set(bot_tools),
        key=lambda k: -(top_tools.get(k, 0) + bot_tools.get(k, 0))
    )
    top_total = sum(top_tools.values()) or 1
    bot_total = sum(bot_tools.values()) or 1
    tools = []
    for tool in all_tools[:15]:
        tc, bc = top_tools.get(tool, 0), bot_tools.get(tool, 0)
        tools.append({
            "tool": tool,
            "top_count": tc, "top_pct": round(tc / top_total * 100, 1),
            "bot_count": bc, "bot_pct": round(bc / bot_total * 100, 1),
        })

    by_cwd = {}
    for s in sessions:
        by_cwd.setdefault(s["cwd"], []).append(s)
    proj_rows = []
    for cwd, ss in by_cwd.items():
        if len(ss) < 2:
            continue
        proj_rows.append({
            "cwd": cwd,
            "sessions": len(ss),
            "leverage": mean(x["leverage"] for x in ss),
            "avg_prompts": mean(x["prompts"] for x in ss),
            "total_tokens": sum(x["total_tokens"] for x in ss),
        })
    proj_rows.sort(key=lambda r: -r["leverage"])
    projects = proj_rows[:10]

    conn.close()

    return {
        "days": days,
        "min_prompts": min_prompts,
        "session_count": len(sessions),
        "summary": summary,
        "compare": compare,
        "top_first": top_first,
        "bot_first": bot_first,
        "tools": tools,
        "projects": projects,
        "db_path": str(DB_PATH),
    }


def render_text(d: dict) -> str:
    out = StringIO()

    def section(title):
        out.write(f"\n{'='*64}\n  {title}\n{'='*64}\n")

    if d["session_count"] == 0:
        out.write(f"최근 {d['days']}일에 {d['min_prompts']}회 이상 프롬프트가 있는 세션 없음\n")
        return out.getvalue()

    out.write(f"\n분석 대상: 최근 {d['days']}일, "
              f"사용자 프롬프트 {d['min_prompts']}회 이상인 세션 {d['session_count']}개\n")

    section("전체 세션 메트릭 (중앙값 / 평균)")
    out.write(f"  {'메트릭':<24} {'중앙값':>12} {'평균':>12}\n")
    out.write(f"  {'-'*52}\n")
    for s in d["summary"]:
        out.write(f"  {s['label']:<24} {fmt(s['median']):>12} {fmt(s['mean']):>12}\n")

    section("지렛대(leverage = 출력토큰/프롬프트) 상위 20% vs 하위 20%")
    out.write(f"  {'메트릭':<28}  {'상위':>10}        {'하위':>10}\n")
    out.write(f"  {'-'*60}\n")
    for c in d["compare"]:
        delta = ""
        if c["ratio"] is not None:
            delta = f"  ({c['ratio']:.1f}x)" if c["top"] > c["bot"] else f"  ({c['ratio']:.2f}x)"
        out.write(f"  {c['label']:<28}  상위 {fmt(c['top']):>10}   하위 {fmt(c['bot']):>10}{delta}\n")

    section("상위 세션 첫 프롬프트 (어떻게 시작했는가)")
    for s in d["top_first"]:
        out.write(f"  [{fmt(s['leverage']):>8}/턴]  {s['cwd_name']:<22}\n")
        out.write(f"     {truncate(s['prompt'], 100)}\n")

    section("하위 세션 첫 프롬프트")
    for s in d["bot_first"]:
        out.write(f"  [{fmt(s['leverage']):>8}/턴]  {s['cwd_name']:<22}\n")
        out.write(f"     {truncate(s['prompt'], 100)}\n")

    section("도구 사용 분포 (상위 세션 vs 하위 세션 — 응답 횟수 기준)")
    out.write(f"  {'도구':<16} {'상위':>10} {'(%)':>7}   {'하위':>10} {'(%)':>7}\n")
    out.write(f"  {'-'*56}\n")
    for t in d["tools"][:12]:
        out.write(f"  {t['tool']:<16} {t['top_count']:>10} {t['top_pct']:>6.1f}%   "
                  f"{t['bot_count']:>10} {t['bot_pct']:>6.1f}%\n")

    section("프로젝트별 평균 지렛대 (세션 수 ≥2)")
    if d["projects"]:
        out.write(f"  {'프로젝트':<46} {'세션':>5} {'지렛대':>10} {'평균프롬프트':>12}\n")
        out.write(f"  {'-'*78}\n")
        for p in d["projects"]:
            label = "..." + p["cwd"][-43:] if len(p["cwd"]) > 46 else p["cwd"]
            out.write(f"  {label:<46} {p['sessions']:>5} {fmt(p['leverage']):>10} {p['avg_prompts']:>12.1f}\n")
    else:
        out.write("  세션 2개 이상인 프로젝트 없음\n")

    out.write(f"\n  DB: {d['db_path']}\n")
    return out.getvalue()


HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<title>omp 효율 — 최근 __DAYS__일</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"
        integrity="sha384-9nhczxUqK87bcKHh20fSQcTGD4qq5GhayNYSYWqwBkINBhOfQLg/P5HG5lF1urn4"
        crossorigin="anonymous"></script>
<style>
  :root { --bg:#0b0d10; --panel:#14181d; --border:#232830; --text:#e6e9ee;
          --muted:#8a93a0; --accent:#6ea8ff; --accent2:#5ad9b1; --warn:#ffb86b; --bad:#ff7b9c; }
  * { box-sizing:border-box; }
  body { margin:0; padding:32px; background:var(--bg); color:var(--text);
         font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Pretendard",sans-serif; }
  h1 { margin:0 0 8px; font-size:22px; font-weight:600; }
  .sub { color:var(--muted); margin-bottom:24px; font-size:13px; }
  .grid { display:grid; gap:16px; }
  .row2 { grid-template-columns:1fr 1fr; }
  @media (max-width:900px) { .row2 { grid-template-columns:1fr; } }
  .panel { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:16px; }
  .panel h2 { margin:0 0 12px; font-size:14px; font-weight:600; color:var(--muted);
              text-transform:uppercase; letter-spacing:0.5px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--border); }
  th { color:var(--muted); font-weight:500; font-size:11px; text-transform:uppercase; }
  td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
  .top { color:var(--accent2); font-weight:600; }
  .bot { color:var(--bad); font-weight:600; }
  .ratio { color:var(--warn); font-size:11px; margin-left:6px; }
  .session { background:#181d23; border-radius:6px; padding:10px 12px; margin-bottom:8px;
             border-left:3px solid var(--accent); }
  .session.bad { border-left-color:var(--bad); }
  .session .head { display:flex; justify-content:space-between; gap:12px; font-size:12px; color:var(--muted); }
  .session .lev { color:var(--accent2); font-weight:600; }
  .session.bad .lev { color:var(--bad); }
  .session .body { margin-top:6px; font-size:12px; font-family:"SF Mono",ui-monospace,monospace;
                   word-break:break-word; line-height:1.5; }
  .proj { font-family:"SF Mono",ui-monospace,monospace; font-size:12px; word-break:break-all; }
  canvas { max-height:340px; }
  .footer { color:var(--muted); font-size:11px; margin-top:24px; }
  .empty { color:var(--muted); padding:40px; text-align:center; }
</style>
</head>
<body>
  <h1>omp 효율 — 최근 __DAYS__일</h1>
  <div class="sub" id="meta"></div>

  <div class="panel">
    <h2>전체 세션 메트릭 (중앙값 / 평균)</h2>
    <table id="summaryTable">
      <thead><tr><th>메트릭</th><th class="num">중앙값</th><th class="num">평균</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <div class="panel" style="margin-top:16px;">
    <h2>지렛대 상위 20% vs 하위 20%</h2>
    <table id="compareTable">
      <thead><tr><th>메트릭</th><th class="num">상위</th><th class="num">하위</th><th class="num">배율</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <div class="grid row2" style="margin-top:16px;">
    <div class="panel">
      <h2>상위 세션 첫 프롬프트</h2>
      <div id="topFirst"></div>
    </div>
    <div class="panel">
      <h2>하위 세션 첫 프롬프트</h2>
      <div id="botFirst"></div>
    </div>
  </div>

  <div class="grid row2" style="margin-top:16px;">
    <div class="panel">
      <h2>도구 사용 분포 (상위 vs 하위)</h2>
      <canvas id="toolChart"></canvas>
    </div>
    <div class="panel">
      <h2>프로젝트별 평균 지렛대 (세션≥2)</h2>
      <table id="projTable">
        <thead><tr><th>프로젝트</th><th class="num">세션</th><th class="num">지렛대</th><th class="num">프롬프트</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <div class="footer">DB: __DBPATH__</div>

<script>
const DATA = __DATA__;

function fmt(n) {
  if (!n && n !== 0) return "0";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  if (n >= 100) return Math.round(n).toLocaleString();
  if (Number.isInteger(n)) return n.toLocaleString();
  return n.toFixed(1);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}

document.getElementById("meta").textContent =
  `세션 ${DATA.session_count}개 (프롬프트 ${DATA.min_prompts}회 이상) · 생성: ${new Date().toLocaleString()}`;

if (DATA.session_count === 0) {
  document.querySelectorAll(".panel, .grid").forEach(el => el.remove());
  document.body.insertAdjacentHTML("beforeend",
    '<div class="empty">분석할 세션이 없습니다.</div>');
} else {
  // summary
  document.querySelector("#summaryTable tbody").innerHTML =
    DATA.summary.map(s =>
      `<tr><td>${s.label}</td><td class="num">${fmt(s.median)}</td><td class="num">${fmt(s.mean)}</td></tr>`
    ).join("");

  // compare
  document.querySelector("#compareTable tbody").innerHTML =
    DATA.compare.map(c => {
      const ratio = c.ratio == null ? "" :
        `<span class="ratio">${c.top > c.bot ? c.ratio.toFixed(1) : c.ratio.toFixed(2)}x</span>`;
      return `<tr>
        <td>${c.label}</td>
        <td class="num top">${fmt(c.top)}</td>
        <td class="num bot">${fmt(c.bot)}${ratio}</td>
        <td class="num">${c.ratio == null ? "—" : (c.top > c.bot ? c.ratio.toFixed(1) + "x" : c.ratio.toFixed(2) + "x")}</td>
      </tr>`;
    }).join("");

  // first prompts
  const renderSessions = (arr, badClass) => arr.map(s =>
    `<div class="session ${badClass}">
       <div class="head"><span>${escapeHtml(s.cwd_name)}</span>
         <span class="lev">${fmt(s.leverage)} / 턴</span></div>
       <div class="body">${escapeHtml((s.prompt || "").slice(0, 240))}${(s.prompt || "").length > 240 ? "…" : ""}</div>
     </div>`).join("");
  document.getElementById("topFirst").innerHTML = renderSessions(DATA.top_first, "");
  document.getElementById("botFirst").innerHTML = renderSessions(DATA.bot_first, "bad");

  // tool chart
  const tools = DATA.tools.slice(0, 12);
  new Chart(document.getElementById("toolChart"), {
    type: "bar",
    data: {
      labels: tools.map(t => t.tool),
      datasets: [
        { label: "상위 세션 (%)", data: tools.map(t => t.top_pct), backgroundColor: "#5ad9b1" },
        { label: "하위 세션 (%)", data: tools.map(t => t.bot_pct), backgroundColor: "#ff7b9c" },
      ],
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { labels: { color: "#e6e9ee" } } },
      scales: {
        x: { ticks: { color: "#8a93a0", callback: v => v + "%" }, grid: { color: "#232830" } },
        y: { ticks: { color: "#8a93a0", font: { family: "SF Mono, ui-monospace, monospace", size: 11 } },
              grid: { color: "#232830" } },
      },
    },
  });

  // projects
  document.querySelector("#projTable tbody").innerHTML =
    DATA.projects.length
      ? DATA.projects.map(p => {
          const label = p.cwd.length > 40 ? "..." + p.cwd.slice(-37) : p.cwd;
          return `<tr>
            <td class="proj">${escapeHtml(label)}</td>
            <td class="num">${p.sessions}</td>
            <td class="num">${fmt(p.leverage)}</td>
            <td class="num">${p.avg_prompts.toFixed(1)}</td>
          </tr>`;
        }).join("")
      : '<tr><td colspan="4" class="empty">세션 2개 이상인 프로젝트 없음</td></tr>';
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
    min_prompts = int(args[1]) if len(args) > 1 else 3

    if not DB_PATH.exists():
        print("아직 데이터가 없습니다. 백필: python3 ~/.claude/hooks/backfill.py")
        return

    data = collect_data(days, min_prompts)

    if text_mode:
        sys.stdout.write(render_text(data))
        return

    html = render_html(data)
    out = omp_tmpdir() / "omp_efficiency.html"
    out.write_text(html, encoding="utf-8")

    try:
        subprocess.run(["open", str(out)], check=False)
    except FileNotFoundError:
        import webbrowser
        webbrowser.open(out.as_uri())

    print(f"효율 대시보드 열림: {out}")


if __name__ == "__main__":
    main()
