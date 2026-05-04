# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to a loose [SemVer](https://semver.org/) — `0.x` while the on-disk
schema and slash-command set are still moving.

## [Unreleased]

## [1.6.0] — 2026-05-04
### Changed
- Centralized the per-uid tempdir helper into `lib/_tmp.py`; the previous
  18-line copy in each of the six viewers/preprocessors is gone.
- `omp_tmpdir()` now prunes any file under `$TMPDIR/omp-<uid>/` whose mtime
  is older than 7 days on every call, so one-shot
  `omp_suggest_input_<ts>.md` files and abandoned dashboard re-renders no
  longer accumulate.

## [1.5.0] — 2026-05-04
### Changed
- README is now English by default; the Korean version moved to
  `README.ko.md`, both linked at the top of each file.
- Documentation updated for `/omp:dashboard` and `/omp:suggest-archive`.
- `/omp:suggest` description rewritten to reflect the sub-agent workflow.

## [1.4.0] — 2026-05-04
### Added
- `/omp:dashboard` — single tabbed page that wraps Stats, Patterns,
  Efficiency, and Suggest Archive as iframes. Sidebar click / `1`-`4` /
  `j`/`k` / arrow keys to switch.
- Lucide-style inline SVG icons in the sidebar, color-synced to the
  `--accent` token.

### Security & privacy (merged from the harden PR)
- `</script>` injection through stored prompts is now closed in all four
  viewers (`_safe_json` helper).
- `lib/dashboard.py` escapes `cwd` strings with `escapeHtml`.
- Suggest-archive markdown viewer routes `marked.parse(...)` through
  `DOMPurify.sanitize`.
- Chart.js, marked, DOMPurify CDN scripts pinned with `integrity`
  (sha384) + `crossorigin`.
- `omp.db` chmodded to `0600`; `~/.claude/omp_suggestions/` to `0700`;
  archived analyses to `0600`.
- `redact()` masks anthropic / openai / slack / github / google / aws keys
  and JWTs in stored prompt text (best-effort, known-shape only).
- Generated HTML moves to `$TMPDIR/omp-<uid>/` (mode `0700`).
- SQLite opens with `journal_mode=WAL` and `busy_timeout=3000` to handle
  concurrent writes from `prompt_logger` and `token_logger`.

### Removed
- Dead scripts: `hooks/report.py` (replaced by `dashboard.py` in 1.1) and
  `lib/suggest.py` (replaced by `suggest_prep.py` + sub-agent in 1.2).

### Changed
- `hooks/dashboard.py` moved to `lib/dashboard.py` so all slash-command
  backends live under `lib/` and `hooks/` only contains real hook
  scripts.

## [1.3.0] — 2026-05-04
### Changed
- `/omp:patterns` and `/omp:efficiency` now render as web dashboards
  (Chart.js) by default, matching `/omp:stats`. Pass `--text` to either
  CLI to keep the original console output (used by `suggest_prep.py`).
- Both analyzers are split into `collect_data` / `render_text` /
  `render_html` so the same data drives a console table or an HTML page.

## [1.2.0] — 2026-05-04
### Added
- `lib/suggest_prep.py` — collects raw analyzer output to `/tmp` and
  emits a one-line JSON manifest (`input_path`, `output_path`, `days`,
  `min_count`, `timestamp`).
- `agents/suggest-analyzer.md` — Opus sub-agent that reads `input_path`,
  writes a structured CLAUDE.md / memory / slash candidate proposal to
  `output_path` under `~/.claude/omp_suggestions/`.
- `lib/suggest_archive.py` + `commands/suggest-archive.md` — web viewer
  for the cumulative archive (sidebar list + rendered markdown).

### Changed
- `commands/suggest.md` rewritten as a 3-step pipeline (prep → Agent →
  Read & echo verbatim) replacing the old single-shot `claude -p` call.

## [1.1.0] — 2026-05-04
### Added
- `hooks/dashboard.py` — HTML stats dashboard (Chart.js) opened in the
  browser. Replaces the text-only `report.py`.

### Changed
- `commands/stats.md` now prints only one line (`대시보드 열림: …`) so
  Claude does not narrate the data.

## [1.0.0] — 2026-05-04
### Added
- Public README documenting install, command surface, schema, and metric
  definitions.

## [0.5.0] — 2026-05-04
### Added
- First version of `/omp:suggest` (single-shot `claude -p` invocation —
  later replaced in 1.2).

## [0.4.0] — 2026-05-04
### Added
- `/omp:efficiency` analyzer: per-session leverage / autonomy / tool
  metrics, top vs bottom 20% comparison, first-prompt analysis.

## [0.3.0] — 2026-05-04
### Added
- `/omp:patterns` analyzer: repeated-prompt detection, intent
  distribution, first-4-words pattern surfacing, auto suggestions.

## [0.2.0] — 2026-05-04
### Added
- Extended transcript parser: token usage breakdown by model, cache
  read/creation, tool use count and tool names per assistant turn.

## [0.1.0] — 2026-05-04
### Added
- Initial scaffold: plugin manifest, `UserPromptSubmit` and `Stop` hooks,
  `prompt_logger`, `token_logger`, `backfill`, SQLite schema, basic text
  `report`.

[Unreleased]: https://github.com/handlecusion/oh-my-prompt/compare/v1.6.0...HEAD
[1.6.0]: https://github.com/handlecusion/oh-my-prompt/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/handlecusion/oh-my-prompt/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/handlecusion/oh-my-prompt/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/handlecusion/oh-my-prompt/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/handlecusion/oh-my-prompt/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/handlecusion/oh-my-prompt/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/handlecusion/oh-my-prompt/compare/v0.5.0...v1.0.0
[0.5.0]: https://github.com/handlecusion/oh-my-prompt/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/handlecusion/oh-my-prompt/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/handlecusion/oh-my-prompt/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/handlecusion/oh-my-prompt/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/handlecusion/oh-my-prompt/releases/tag/v0.1.0
