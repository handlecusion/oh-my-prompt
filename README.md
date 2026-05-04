[한국어](./README.ko.md)

# oh-my-prompt

> A Claude Code plugin that analyzes your usage so you can get **more output from fewer prompts**.

It quietly logs your prompts, tokens, tool calls, and session metadata into a local SQLite database, then helps you turn that data into actionable improvements:

- Surface short prompts you keep retyping → candidates for `CLAUDE.md` rules, memory entries, or new slash commands
- Compare your high-leverage sessions against your low-leverage ones to learn what kind of opening prompt actually works for you
- Hand the raw analysis to a sub-agent and let it draft the patches

100% local. No outbound calls. No API key required (uses your existing `claude` CLI auth).

---

## Slash commands

| Command | Args | What it does |
|---|---|---|
| `/omp:stats [days]` | days (default 7) | Daily token usage, per-model breakdown, per-project distribution, session stats — rendered as a web dashboard |
| `/omp:patterns [days] [min]` | 30, 3 | Repeated prompts, intent distribution, first-4-words patterns, `CLAUDE.md` candidates — web dashboard |
| `/omp:efficiency [days] [min]` | 30, 3 | Per-session leverage / autonomy / tool metrics, top vs bottom 20% comparison, first-prompt analysis — web dashboard |
| `/omp:suggest [days] [min]` | 30, 3 | Runs both analyses, hands the raw output to an Opus sub-agent, and writes a structured proposal (rules, memory, slash candidates) to `~/.claude/omp_suggestions/<timestamp>.md` |
| `/omp:suggest-archive` | — | Browse the cumulative `~/.claude/omp_suggestions/` archive in a sidebar viewer |
| `/omp:dashboard [stats_days] [days] [min]` | 7, 30, 3 | All four panels above in a single tabbed page (`1`-`4` / `j`/`k` / arrows to switch) |

---

## Install

### Option 1: Plugin marketplace (recommended)

```
/plugin marketplace add github.com/handlecusion/oh-my-prompt
/plugin install omp@oh-my-prompt
```

The `UserPromptSubmit` and `Stop` hooks register themselves automatically and start writing to `~/.claude/omp.db`. After your first session:

```
/omp:stats
```

### Option 2: Clone and wire up `settings.json` manually

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

- **Location**: `~/.claude/omp.db` (SQLite)
- **Two tables**:
  - `prompts(prompt_id UNIQUE, session_id, cwd, prompt, char_count, word_count, is_sidechain, ts)`
  - `token_usage(msg_id UNIQUE, session_id, cwd, model, input/output/cache_*_tokens, text_chars, tool_use_count, tool_names, is_sidechain, ts)`
- **Dedup keys**: the transcript's `promptId` / message `id`. The live hook and the backfill safely share the same rows.

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

## License

MIT
