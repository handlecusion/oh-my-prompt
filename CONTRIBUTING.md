# Contributing to oh-my-prompt

Thanks for considering a contribution. This is a hobby-scale project, so
the bar is "useful + tested + doesn't break the existing slash commands
or the suggest pipeline."

## Local development

The plugin has zero runtime dependencies beyond a system Python 3.10+
and SQLite. Cloning the repo is enough to run it.

```bash
git clone https://github.com/handlecusion/oh-my-prompt
cd oh-my-prompt

# point Claude Code at this repo's hooks (option 2 from the README)
# or use it via /plugin install with --from-source
```

To work on a feature branch without churning your real DB, point the
hooks at a scratch DB:

```bash
OMP_DB_OVERRIDE=$HOME/.claude/omp_dev.db python3 hooks/backfill.py
```

(Currently `_db.py` hard-codes `~/.claude/omp.db`. If you submit an env
var override it is welcome — the existing PRs assume the default.)

## Running the analyzers locally

Each analyzer can be run standalone:

```bash
python3 lib/dashboard.py 7              # /omp:stats
python3 lib/analyzers/patterns.py 30 3  # /omp:patterns
python3 lib/analyzers/efficiency.py 30 3
python3 lib/suggest_archive.py
python3 lib/dashboard_all.py            # /omp:dashboard
python3 lib/suggest_prep.py 30 3        # JSON manifest used by /omp:suggest
```

Pass `--text` to `patterns.py` / `efficiency.py` to get the console
output that `suggest_prep.py` consumes — useful when hacking on the
sub-agent prompt without re-rendering HTML.

## Tests

The `tests/` folder holds unit tests for the small pure functions
that are easy to regress on:

```bash
python3 -m pytest tests/ -v
# or, without pytest:
python3 -m unittest discover tests
```

CI runs the same command on every push and PR (see
`.github/workflows/ci.yml`).

## Code conventions

- Stay dependency-free. The whole point is "no install gymnastics" —
  please justify any new third-party package in the PR description.
- Match the existing file layout:
  - `hooks/` — only real Claude Code hooks (`prompt_logger`,
    `token_logger`, `backfill`) and the shared `_db.py`.
  - `lib/` — slash-command backends and the `_tmp.py` helper.
  - `lib/analyzers/` — long-form analyses split into
    `collect_data` + `render_text` + `render_html`.
  - `commands/` — slash-command markdown.
  - `agents/` — sub-agent definitions.
- Slash-command markdown should print **one line** to the user (e.g.
  `대시보드 열림: <path>`) and tell Claude not to narrate the data —
  this matches the existing UX and avoids the LLM duplicating the
  rendered output back into the chat.
- For new analyzers, keep the `--text` flag working so `suggest_prep.py`
  can pipe their output to the sub-agent.

## Security-relevant changes

Any change that touches one of these surfaces should ship with a unit
test or an explicit reasoning note in the PR:

- `redact()` patterns in `hooks/_db.py`
- `_safe_json()` / `escapeHtml()` in any HTML viewer
- `omp_tmpdir()` perms / prune logic in `lib/_tmp.py`
- File modes (`chmod` calls) anywhere
- New CDN script tags (must include `integrity="sha384-..."` +
  `crossorigin="anonymous"`)
- `agents/suggest-analyzer.md` — keep the "write only to `output_path`"
  contract intact

See [`SECURITY.md`](./SECURITY.md) for the full threat model.

## Commit / PR style

- One logical change per commit. The history is intentionally readable
  (see `git log --oneline`).
- Commit subject: imperative mood, conventional-commits-style scope is
  fine but not required (e.g. `fix(security):`, `docs:`,
  `chore:`).
- PR description should mention which slash command(s) were re-tested
  and whether `suggest_prep.py` still produces the expected JSON
  manifest — that pipeline is the easiest thing to break by accident.

## License

By contributing you agree your contribution is licensed under the
project's [MIT license](./LICENSE).
