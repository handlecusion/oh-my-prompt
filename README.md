<h1 align="center">oh-my-prompt</h1>

<p align="center">
  <strong>Stop guessing what works. Let your prompts tell you.</strong>
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

A Claude Code plugin that turns your own usage data into actionable improvements. It quietly logs every prompt, token, tool call, and session into a local SQLite database, then helps you:

- Surface short prompts you keep retyping → candidates for `CLAUDE.md` rules, memory entries, or new slash commands
- Compare your high-leverage sessions against your low-leverage ones to learn what kind of opening prompt actually works for you
- Hand the raw analysis to a sub-agent and let it draft the patches

100% local. No outbound calls. No API key required (uses your existing `claude` CLI auth).

---

## Quick start

```
/plugin marketplace add github.com/handlecusion/oh-my-prompt
/plugin install omp@oh-my-prompt
```

The `UserPromptSubmit` and `Stop` hooks register themselves and start writing to `~/.claude/omp.db`. After a session or two:

```
/omp:dashboard
```

That single tabbed page gives you Stats, Patterns, Efficiency, and your Suggest archive — all in one window.

---

## Slash commands

| Command | Args | What it does |
|---|---|---|
| `/omp:stats [days]` | days (default 7) | Daily token usage, per-model breakdown, per-project distribution, session stats — rendered as a web dashboard |
| `/omp:patterns [days] [min]` | 30, 3 | Repeated prompts, intent distribution, first-4-words patterns, `CLAUDE.md` candidates |
| `/omp:efficiency [days] [min]` | 30, 3 | Per-session leverage / autonomy / tool metrics, top vs bottom 20% comparison, first-prompt analysis |
| `/omp:suggest [days] [min]` | 30, 3 | Runs both analyses, hands the raw output to an Opus sub-agent, and writes a structured proposal (rules, memory, slash candidates) to `~/.claude/omp_suggestions/<timestamp>.md` |
| `/omp:suggest-archive` | — | Browse the cumulative `~/.claude/omp_suggestions/` archive in a sidebar viewer |
| `/omp:dashboard [stats_days] [days] [min]` | 7, 30, 3 | All four panels above in a single tabbed page (`1`-`4` / `j`/`k` / arrows to switch) |

---

## Screenshots

> Screenshots are added in a follow-up commit (Day 2 of the README polish plan).

---

## Install (option 2: clone manually)

```bash
git clone https://github.com/handlecusion/oh-my-prompt ~/Code/oh-my-prompt
```

Add to the `hooks` block of `~/.claude/settings.json`:

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

### Backfill (import past transcripts)

Walks every `~/.claude/projects/**/*.jsonl` and ingests it in one shot:

```bash
python3 ~/Code/oh-my-prompt/hooks/backfill.py
```

UPSERT-based, so you can rerun safely (only new sessions are added).

---

## Data

- **Location**: `~/.claude/omp.db` (SQLite, perms `0600`)
- **Two tables**:
  - `prompts(prompt_id UNIQUE, session_id, cwd, prompt, char_count, word_count, is_sidechain, ts)`
  - `token_usage(msg_id UNIQUE, session_id, cwd, model, input/output/cache_*_tokens, text_chars, tool_use_count, tool_names, is_sidechain, ts)`
- **Dedup keys**: the transcript's `promptId` / message `id`. The live hook and the backfill safely share the same rows.
- **Secrets**: prompts pass through a best-effort `redact()` pass (anthropic / openai / slack / github / google / aws keys + JWTs) before insert. Generic high-entropy strings are intentionally not matched.

If you prefer raw SQL:

```bash
sqlite3 ~/.claude/omp.db "SELECT cwd, COUNT(*), SUM(total_tokens) FROM token_usage GROUP BY cwd ORDER BY 3 DESC LIMIT 10;"
```

---

## Metric definitions

- **leverage** = `output_tokens / user_prompts` — how much output you got per prompt
- **autonomy** = `assistant_turns / user_prompts` — average turns between user interruptions (higher = you set it up once and it runs longer)
- **tools_per_prompt** — how many tool calls were issued per prompt

If your top-leverage sessions consistently start with a long, context-rich first prompt, that's a strong signal that "front-load the context" works for you.

---

## Security & privacy

- All processing is local. No outbound network calls.
- The DB and the suggestion archive are chmod'd `0600` / `0700` on every open.
- Generated dashboard HTML is written to `$TMPDIR/omp-<uid>/` (mode `0700`) and any file older than 7 days is auto-pruned on the next run.
- Inline JSON in dashboards is `</`-escaped; user-generated strings are `escapeHtml`-wrapped; the suggest-archive markdown viewer routes through DOMPurify; all CDN scripts pinned with SRI.

For details and reporting, see [`SECURITY.md`](./SECURITY.md).

---

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md). Issues and PRs welcome — especially additional `redact()` patterns and analyzer ideas.

## License

[MIT](./LICENSE)
