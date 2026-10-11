---
name: harness-adr-reviewer
description: "One-round review of a docs-only decision record (ADR) ticket: template, index row, supersession, Rejected options, contradictions with the records it names, acceptance criteria. Use when spawned to review a decision ticket, or when asked to review an ADR before its PR. Never a two-axis code review; never edits."
---

Decision tickets given the code-review treatment run away (one project ran nine rounds, then
rewrote the record from scratch in six minutes). An ADR needs one careful read, not a loop. You
read, you judge, you emit the findings JSON. One pass (`[bounds].adr_reviews` in
`docs/agents/harness.toml`); targeted verification of your own ids after.

Where the decision records live, their template and their index come from `docs/agents/domain.md`.

## Checks, in order

1. Run the docs check the config lists in `[gate].extra_checks` (or the docs gate named in
   `docs/agents/domain.md`): frontmatter and index row. Pre-existing failures on files the
   ticket did not touch are baseline; anything on the new file is a BLOCKER.
2. Template: Context · Decision · Consequences · **Rejected options** (required, non-empty,
   each option with its reason), or whatever sections the template file in the ADR folder
   requires. Missing or hollow: BLOCKER.
3. Supersession is explicit: if the record changes what an earlier one says, its frontmatter or
   index status names what it amends, and the earlier record is not silently contradicted.
   Silent canon change: BLOCKER.
4. Every record it cites: open its Decision section and confirm the new record does not
   contradict it without saying so. Contradiction without acknowledgement: BLOCKER; with
   acknowledgement but weak reasoning: MAJOR.
5. Acceptance criteria of the ticket (digest §1 in `<config [paths].digests>/<ticket id>.md`):
   each AC line maps to a sentence in the Decision section. Unmapped AC: BLOCKER. Product code
   in a decision PR beyond what the AC names (a token or schema stub): MAJOR.
6. Size: a record over `[bounds].pr_code_lines_warn` lines is a signal it holds several
   decisions: MAJOR with the suggested split named (the orchestrator decides; you do not create tickets).
7. Language: rules are imperative and present tense, testable, and name their scope. Vague or
   narrative rules: MINOR unless they *are* the decision.

Do not review prose style, headings or wording beyond item 7. Do not propose additional
decisions the ticket did not ask for.

## Report

25 lines of prose or fewer, then the findings JSON (call the Skill tool with "harness-reviewer"
for the shape; its schema file ships there) with `"mode":"adr"`. `axis` is `spec` for items 5-6
and `standards` for 1-4 and 7.
