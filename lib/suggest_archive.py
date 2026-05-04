#!/usr/bin/env python3
"""/omp:suggest-archive 웹 뷰어.

~/.claude/omp_suggestions/*.md 를 읽어 자체 포함 HTML(좌측 목록 + 우측 마크다운)을
생성하고 브라우저로 띄운다.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ARCHIVE = Path.home() / ".claude" / "omp_suggestions"


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


HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<title>omp suggest archive (__COUNT__건)</title>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"
        integrity="sha384-/TQbtLCAerC3jgaim+N78RZSDYV7ryeoBCVqTuzRrFec2akfBkHS7ACQ3PQhvMVi"
        crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.11/dist/purify.min.js"
        integrity="sha384-Ic7KEGROu37YaruU6NyiYeib7UhjFyDZQ5fzBAji965L75T/4LGk5nzwMEjNGexs"
        crossorigin="anonymous"></script>
<style>
  :root {
    --bg: #0b0d10;
    --panel: #14181d;
    --panel2: #181d23;
    --border: #232830;
    --text: #e6e9ee;
    --muted: #8a93a0;
    --accent: #6ea8ff;
    --accent-bg: #1a2738;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Pretendard", sans-serif;
    display: grid; grid-template-columns: 280px 1fr;
  }
  aside {
    background: var(--panel); border-right: 1px solid var(--border);
    overflow-y: auto; padding: 16px 0;
  }
  aside h1 {
    margin: 0 16px 12px; font-size: 13px; font-weight: 600;
    color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px;
  }
  .item {
    padding: 10px 16px; cursor: pointer; border-left: 2px solid transparent;
    font-size: 13px;
  }
  .item:hover { background: var(--panel2); }
  .item.active {
    background: var(--accent-bg); border-left-color: var(--accent);
  }
  .item .ts { font-family: "SF Mono", ui-monospace, monospace; font-size: 12px; }
  .item .meta { color: var(--muted); font-size: 11px; margin-top: 2px; }
  main {
    overflow-y: auto; padding: 32px 40px;
  }
  main .header {
    color: var(--muted); font-size: 12px; margin-bottom: 16px;
    font-family: "SF Mono", ui-monospace, monospace;
  }
  .empty { color: var(--muted); padding: 40px; text-align: center; }
  /* markdown */
  .md h1, .md h2, .md h3 { margin-top: 28px; margin-bottom: 12px; font-weight: 600; }
  .md h2 { font-size: 18px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
  .md h3 { font-size: 15px; color: var(--accent); }
  .md p { line-height: 1.65; margin: 8px 0; }
  .md ul { line-height: 1.7; padding-left: 22px; }
  .md li { margin: 4px 0; }
  .md code {
    background: var(--panel); padding: 2px 6px; border-radius: 4px;
    font-family: "SF Mono", ui-monospace, monospace; font-size: 13px;
  }
  .md pre {
    background: var(--panel); padding: 12px; border-radius: 6px;
    overflow-x: auto; border: 1px solid var(--border);
  }
  .md pre code { background: transparent; padding: 0; }
  .md strong { color: #fff; }
  .md blockquote {
    border-left: 3px solid var(--accent); padding-left: 12px;
    color: var(--muted); margin: 12px 0;
  }
</style>
</head>
<body>
  <aside>
    <h1>archive · __COUNT__건</h1>
    <div id="list"></div>
  </aside>
  <main>
    <div class="header" id="meta"></div>
    <div class="md" id="content"></div>
  </main>

<script>
const ENTRIES = __DATA__;

function render(idx) {
  const e = ENTRIES[idx];
  document.querySelectorAll(".item").forEach((el, i) =>
    el.classList.toggle("active", i === idx));
  if (!e) {
    document.getElementById("meta").textContent = "";
    document.getElementById("content").innerHTML = '<div class="empty">저장된 분석이 없습니다.</div>';
    return;
  }
  document.getElementById("meta").textContent = `${e.stem}   ·   ${(e.size/1024).toFixed(1)} KB`;
  // marked v12 does not sanitize; route through DOMPurify so a poisoned
  // suggestion file (e.g., one quoting a malicious user prompt) cannot
  // execute scripts when rendered.
  document.getElementById("content").innerHTML = DOMPurify.sanitize(marked.parse(e.content));
  window.scrollTo(0, 0);
  document.querySelector("main").scrollTo(0, 0);
}

const list = document.getElementById("list");
ENTRIES.forEach((e, i) => {
  const div = document.createElement("div");
  div.className = "item";
  div.innerHTML = `<div class="ts">${e.stem}</div><div class="meta">${(e.size/1024).toFixed(1)} KB</div>`;
  div.addEventListener("click", () => render(i));
  list.appendChild(div);
});

if (ENTRIES.length === 0) {
  document.getElementById("content").innerHTML =
    '<div class="empty">저장된 분석이 없습니다.<br>먼저 <code>/omp:suggest</code> 를 실행하세요.</div>';
} else {
  render(0);
}

document.addEventListener("keydown", (ev) => {
  if (ENTRIES.length === 0) return;
  const cur = [...document.querySelectorAll(".item")].findIndex(el => el.classList.contains("active"));
  if (ev.key === "ArrowDown" && cur < ENTRIES.length - 1) render(cur + 1);
  if (ev.key === "ArrowUp" && cur > 0) render(cur - 1);
});
</script>
</body>
</html>
"""


def collect_entries():
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    try:
        ARCHIVE.chmod(0o700)
    except OSError:
        pass
    files = sorted(ARCHIVE.glob("*.md"), reverse=True)
    entries = []
    for f in files:
        try:
            f.chmod(0o600)  # archived analyses can quote raw prompts; keep them owner-only.
        except OSError:
            pass
        entries.append({
            "stem": f.stem,
            "name": f.name,
            "size": f.stat().st_size,
            "content": f.read_text(encoding="utf-8"),
        })
    return entries


def _safe_json(d) -> str:
    return json.dumps(d, ensure_ascii=False).replace("</", "<\\/")


def render_html(entries) -> str:
    return (HTML
            .replace("__COUNT__", str(len(entries)))
            .replace("__DATA__", _safe_json(entries)))


def main():
    entries = collect_entries()
    html = render_html(entries)
    out = omp_tmpdir() / "omp_suggest_archive.html"
    out.write_text(html, encoding="utf-8")

    try:
        subprocess.run(["open", str(out)], check=False)
    except FileNotFoundError:
        import webbrowser
        webbrowser.open(out.as_uri())

    print(f"보관함 열림: {out}  ({len(entries)}건)")


if __name__ == "__main__":
    main()
