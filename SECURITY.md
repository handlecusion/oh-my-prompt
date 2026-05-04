# Security policy

## Reporting a vulnerability

If you find a security issue in oh-my-prompt, please report it privately
**before** opening a public issue or PR.

- Preferred: open a [private security advisory](https://github.com/handlecusion/oh-my-prompt/security/advisories/new)
  on GitHub.
- Alternative: email the repo owner via the address listed on the GitHub
  profile page.

Please include:
- a short description of the issue and impact,
- a minimal reproduction (a tiny prompt or transcript snippet is plenty —
  do not include real secrets),
- the affected version (`git rev-parse --short HEAD` or release tag).

I will acknowledge within a few business days and aim to ship a patch
release on `main` before the advisory is published. Coordinated
disclosure is appreciated; embargo windows up to 30 days are fine for
non-trivial issues.

## Supported versions

This is a single-author hobby project. Only `main` is supported — please
update to the latest commit before reporting. There is no LTS branch.

## What is in scope

The local-only nature of the plugin means the realistic attack surface
is small. The following are in scope:

- **XSS in the generated dashboards.** All viewers render data from the
  local DB (your own prompts, project paths, suggestion archive
  markdown). If a stored prompt or path can execute script when the
  dashboard is opened, that is in scope.
- **Local file disclosure / overwrite.** Symlink races, predictable
  output paths under shared `/tmp`, world-readable secret-bearing
  files.
- **SQL injection.** All SQL parameters should be cast or bound.
- **Secret leakage.** Patterns that should be redacted before storage
  but are not.
- **Sub-agent prompt injection.** A poisoned prompt in your own history
  manipulating `agents/suggest-analyzer.md` into writing files outside
  `output_path`.

The following are explicitly **out of scope**:
- Anything requiring a malicious user already having write access to
  your `~/.claude/omp.db` or `~/.claude/omp_suggestions/` (they own your
  shell at that point).
- CDN compromise of `cdn.jsdelivr.net` itself — mitigated via SRI hashes
  on every script tag.
- Vulnerabilities in Claude Code, Claude Code plugins infra, or the
  Anthropic API.

## Sensitive data, by design

oh-my-prompt stores **raw user prompts** in `~/.claude/omp.db`. By the
nature of how people use Claude Code, this DB will inevitably contain
fragments of source code, file paths, internal URLs, and — despite the
`redact()` pass — the occasional secret a user pasted in. Treat
`~/.claude/omp.db` and `~/.claude/omp_suggestions/` as roughly as
sensitive as your shell history file.

Mitigations already in place:
- `omp.db` is chmod'd `0600` and `omp_suggestions/` to `0700` on every
  open.
- `prompt_logger` runs all incoming prompt text through `redact()`,
  which masks anthropic / openai / slack / github / google / aws keys
  and JWTs. False-positive-prone generic high-entropy patterns are
  intentionally excluded — additional patterns are welcome via PR.
- Generated dashboard HTML lives in `$TMPDIR/omp-<uid>/` (mode `0700`)
  and any file older than 7 days is auto-pruned on the next run.
- Inline JSON in the dashboards has `</` escaped; user-controlled
  strings go through `escapeHtml`; the suggest-archive markdown viewer
  pipes `marked.parse(...)` through `DOMPurify.sanitize(...)`; CDN
  scripts are pinned with `integrity="sha384-..."` + `crossorigin`.

If any of these mitigations regress, that is a bug — please report.
