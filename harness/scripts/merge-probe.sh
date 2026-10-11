#!/usr/bin/env bash
# merge-probe: will branch B merge cleanly onto A? Uses `git merge-tree` (no worktree, no checkout).
# Usage: scripts/agents/merge-probe.sh <A> <B> [<B2> ...]   (probes A+B, then A+B+B2 cumulatively)
# Prints conflicting paths per step; exit 0 clean, 1 conflicts. Replaces the disposable
# `merge-probe` worktree the 09-18 orchestrator built by hand.
set -uo pipefail
A="${1:?usage: merge-probe.sh <base-branch> <branch>...}"; shift
[ $# -ge 1 ] || { echo "merge-probe: need at least one branch to probe" >&2; exit 2; }
TREE="$(git rev-parse "$A^{tree}")"; BASE_REF="$A"; RC=0
for B in "$@"; do
  MB="$(git merge-base "$BASE_REF" "$B")"
  OUT="$(git merge-tree --write-tree --merge-base "$MB" "$BASE_REF" "$B" 2>&1)"; ST=$?
  if [ $ST -eq 0 ]; then
    echo "clean   $BASE_REF + $B"
  else
    RC=1; echo "CONFLICT $BASE_REF + $B"
    printf '%s\n' "$OUT" | awk '/^$/{f=1;next} f && /^CONFLICT|^Auto-merging|^[0-9]+ /{print "   " $0}' | head -40
    printf '%s\n' "$OUT" | grep -E '^CONFLICT' | sed 's/^/   /' | head -40
  fi
  # cumulative: next probe is against the (possibly conflicted) merged tree only when clean
  if [ $ST -eq 0 ]; then
    MERGED="$(printf '%s\n' "$OUT" | head -1)"
    BASE_REF="$(git commit-tree "$MERGED" -p "$(git rev-parse "$BASE_REF")" -p "$(git rev-parse "$B")" -m "probe: $A + $B" 2>/dev/null || echo "$BASE_REF")"
  fi
done
exit $RC
