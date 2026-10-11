---
name: harness-cost-audit
description: "Measure what a window of Codex + Claude Code agent work cost and where it went: tokens by model/ticket/role, idle and polling, review economics, thrown-away work. Use when asked what a wave or a day cost, whether a loop was wasteful, or to re-run the agent-efficiency audit. Read-only over ~/.codex and ~/.claude."
---

Two surfaces, both read-only. Scripts ship with the plugin under `$HARNESS_ROOT` (if unset, the
session-start context names the path). Tiers, bounds and ticket prefix come from
`docs/agents/harness.toml`.

- **Quick:** `python3 "$HARNESS_ROOT/scripts/cost_report.py" --since <date> [--by ticket|model|kind]`
  (the project may wrap it, e.g. a `make cost-report` target). It reads the metrics file the
  Stop/SubagentStop hooks append to. Claude Code sessions only; latest row per transcript wins.
- **Full:** `python3 "$HARNESS_ROOT/scripts/audit/audit.py" --since <date> [--until …]` parses
  every Codex rollout and Claude transcript in the window into `<config [paths].state>/audit/<since>/`:
  `threads.csv` (one row per thread: role, ticket, model, tokens, wall/active, tests, commits,
  outcome) and `tables/*.md` (totals by model/day · by ticket and phase · top threads · cache ·
  tier fit · thinking share · repeated work · orchestrator overhead · idle gaps · review
  economics · full-suite runs · polling cost).

## How to read it

1. `t1_totals.md`: which model consumed the most, and was it the tier `[tiers]` prescribes for that role?
2. `analyze2.md` "by ticket × phase": where did a ticket's spend go (implement, review-1, inner
   passes, review-2+, targeted, merge)? More than `[bounds].broad_reviews` broad reviews is a violation.
3. `t7_polling.md`: poll-only responses in orchestrators must be about 0 (blocking waits).
4. `analyze3.md`: full-suite runs per thread (bound `[bounds].full_suite_per_loop`), files read
   more than 3 times, identical `git status/diff` re-runs, read-gate bytes (about 0 once digests
   exist), idle gaps.
5. `t6_reviews.md`: tokens per review and blocker-class findings; `cheap_check` findings are gate backlog.
6. For an episode, cost a time range with the audit directory's `window_cost.py <thread_id>,<t0>,<t1>`.

## Known toolkit defects: verify before trusting a table

- `t7`: its polling table must take orchestrator threads from the audited window. An empty or
  stale table with orchestrators present in `threads.csv` is the bug, not good news.
- `t6`: it must parse the findings JSON (the reviewer schema). Zero reviews found while review
  threads exist means the parser missed the JSON.
- Prices: every model id in the window needs a row in the prices file. An unpriced id silently
  counts as $0; list the ids missing and flag the totals as lower bounds.
- Forked sessions: a forked or resumed session repeats its parent's turns. Totals are only valid
  if duplicate turns are deduplicated; if not, say so rather than reporting inflated tokens.

Prices are assumptions; accounts may be subscription billed, so report dollars as list-price
equivalents and say so. Never print anything from a transcript that looks like a key; the
parsers redact `sk-`, `ghp_`, tracker keys and JWT-shaped strings, but you are the last line.

## Output

A short table per question above, then the three largest recoverable items with the bound or
script that would remove each. If a bound in the config was violated, name the thread and the
number. Nothing else.
