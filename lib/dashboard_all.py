#!/usr/bin/env python3
"""/omp:dashboard — stats + patterns + efficiency + suggest archive 통합 뷰.

각 패널은 기존 단일 페이지 HTML을 그대로 iframe으로 임베드한다.
사이드바 클릭으로 패널 전환.
"""

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.gettempdir())


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dashboard = _load("omp_dashboard", ROOT / "hooks" / "dashboard.py")
patterns = _load("omp_patterns", ROOT / "lib" / "analyzers" / "patterns.py")
efficiency = _load("omp_efficiency", ROOT / "lib" / "analyzers" / "efficiency.py")
suggest_archive = _load("omp_suggest_archive", ROOT / "lib" / "suggest_archive.py")


WRAPPER = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<title>omp dashboard</title>
<style>
  :root { --bg:#0b0d10; --panel:#14181d; --panel2:#181d23; --border:#232830;
          --text:#e6e9ee; --muted:#8a93a0; --accent:#6ea8ff; --accent-bg:#1a2738; }
  * { box-sizing:border-box; }
  html, body { height:100%; margin:0; }
  body { background:var(--bg); color:var(--text);
         font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Pretendard",sans-serif;
         display:grid; grid-template-columns:220px 1fr; }
  aside { background:var(--panel); border-right:1px solid var(--border);
          padding:20px 0; overflow-y:auto; }
  aside .brand { padding:0 20px 16px; font-weight:700; font-size:14px;
                 letter-spacing:0.5px; color:var(--text); }
  aside .brand .ver { color:var(--muted); font-weight:400; font-size:11px; margin-left:6px; }
  aside .nav { display:flex; flex-direction:column; }
  .tab { display:flex; align-items:center; gap:10px; padding:11px 20px;
         cursor:pointer; border-left:2px solid transparent; font-size:13px;
         color:var(--text); user-select:none; }
  .tab:hover { background:var(--panel2); }
  .tab.active { background:var(--accent-bg); border-left-color:var(--accent); color:#fff; font-weight:600; }
  .tab .icon { width:18px; height:18px; display:inline-flex; align-items:center; justify-content:center;
               color:var(--muted); flex-shrink:0; }
  .tab .icon svg { width:16px; height:16px; }
  .tab.active .icon { color:var(--accent); }
  .tab .label { flex:1; }
  .tab .meta { color:var(--muted); font-size:11px; }
  aside .footer { color:var(--muted); font-size:11px; padding:16px 20px; margin-top:8px;
                  border-top:1px solid var(--border); line-height:1.6; }
  main { position:relative; }
  iframe { position:absolute; inset:0; width:100%; height:100%; border:0;
           background:var(--bg); display:none; }
  iframe.active { display:block; }
</style>
</head>
<body>
  <aside>
    <div class="brand">omp <span class="ver">dashboard</span></div>
    <div class="nav">
      <div class="tab active" data-target="stats">
        <span class="icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg></span>
        <span class="label">Stats</span>
        <span class="meta">__DAYS_STATS__일</span>
      </div>
      <div class="tab" data-target="patterns">
        <span class="icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg></span>
        <span class="label">Patterns</span>
        <span class="meta">__DAYS__/__MIN__</span>
      </div>
      <div class="tab" data-target="efficiency">
        <span class="icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg></span>
        <span class="label">Efficiency</span>
        <span class="meta">__DAYS__/__MIN__</span>
      </div>
      <div class="tab" data-target="archive">
        <span class="icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg></span>
        <span class="label">Suggest Archive</span>
        <span class="meta">__ARCHIVE_COUNT__건</span>
      </div>
    </div>
    <div class="footer">
      stats=최근 __DAYS_STATS__일<br>
      patterns/efficiency=최근 __DAYS__일, 최소 __MIN__회<br>
      DB: __DBPATH__
    </div>
  </aside>
  <main>
    <iframe id="frame-stats" class="active" src="__SRC_STATS__"></iframe>
    <iframe id="frame-patterns" src="__SRC_PATTERNS__"></iframe>
    <iframe id="frame-efficiency" src="__SRC_EFFICIENCY__"></iframe>
    <iframe id="frame-archive" src="__SRC_ARCHIVE__"></iframe>
  </main>

<script>
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    const target = tab.dataset.target;
    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t === tab));
    document.querySelectorAll("iframe").forEach(f =>
      f.classList.toggle("active", f.id === "frame-" + target));
  });
});

document.addEventListener("keydown", ev => {
  const tabs = [...document.querySelectorAll(".tab")];
  const cur = tabs.findIndex(t => t.classList.contains("active"));
  if (ev.key === "ArrowDown" || ev.key === "j") {
    if (cur < tabs.length - 1) tabs[cur + 1].click();
  } else if (ev.key === "ArrowUp" || ev.key === "k") {
    if (cur > 0) tabs[cur - 1].click();
  } else if (/^[1-4]$/.test(ev.key)) {
    tabs[parseInt(ev.key) - 1]?.click();
  }
});
</script>
</body>
</html>
"""


def main():
    args = [a for a in sys.argv[1:] if a]
    days_stats = int(args[0]) if len(args) > 0 else 7
    days = int(args[1]) if len(args) > 1 else 30
    min_count = int(args[2]) if len(args) > 2 else 3

    if not dashboard.DB_PATH.exists():
        print("아직 데이터가 없습니다. 백필: python3 ~/.claude/hooks/backfill.py")
        return

    stats_data = dashboard.collect(days_stats)
    stats_html = dashboard.render(stats_data)
    stats_out = TMP / "omp_dashboard.html"
    stats_out.write_text(stats_html, encoding="utf-8")

    patterns_data = patterns.collect_data(days, min_count)
    patterns_html = patterns.render_html(patterns_data)
    patterns_out = TMP / "omp_patterns.html"
    patterns_out.write_text(patterns_html, encoding="utf-8")

    efficiency_data = efficiency.collect_data(days, min_count)
    efficiency_html = efficiency.render_html(efficiency_data)
    efficiency_out = TMP / "omp_efficiency.html"
    efficiency_out.write_text(efficiency_html, encoding="utf-8")

    archive_entries = suggest_archive.collect_entries()
    archive_html = suggest_archive.render_html(archive_entries)
    archive_out = TMP / "omp_suggest_archive.html"
    archive_out.write_text(archive_html, encoding="utf-8")

    wrapper = (WRAPPER
               .replace("__DAYS_STATS__", str(days_stats))
               .replace("__DAYS__", str(days))
               .replace("__MIN__", str(min_count))
               .replace("__ARCHIVE_COUNT__", str(len(archive_entries)))
               .replace("__DBPATH__", str(dashboard.DB_PATH))
               .replace("__SRC_STATS__", stats_out.name)
               .replace("__SRC_PATTERNS__", patterns_out.name)
               .replace("__SRC_EFFICIENCY__", efficiency_out.name)
               .replace("__SRC_ARCHIVE__", archive_out.name))

    out = TMP / "omp_dashboard_all.html"
    out.write_text(wrapper, encoding="utf-8")

    try:
        subprocess.run(["open", str(out)], check=False)
    except FileNotFoundError:
        import webbrowser
        webbrowser.open(out.as_uri())

    print(f"통합 대시보드 열림: {out}  (stats={days_stats}d, "
          f"patterns/efficiency={days}d/{min_count}회, archive={len(archive_entries)}건)")


if __name__ == "__main__":
    main()
