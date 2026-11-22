---
name: RFinance Status Documentation
description: Keep RFinance handoff documents accurate after each substantial work unit: IMPLEMENTATION_STATUS.md, ROADMAP.md, TEST_REPORT.md, CHANGELOG.md and ADRs. Use when finishing a feature or before ending a session.
---

# Status documentation policy

## Files and their roles

- `IMPLEMENTATION_STATUS.md` — repository/branch state, verified commit hashes, implemented slices, CI and local verification, known defects, exact next objective.
- `ROADMAP.md` — milestone statuses reflecting implemented behaviour and test evidence, not folder names.
- `TEST_REPORT.md` — observed check results, environment, coverage by area, known boundaries, remaining validation.
- `CHANGELOG.md` — coherent, user-visible entries under `Unreleased`.
- `docs/ADR/` — significant architectural or licensing decisions with context, decision, alternatives and consequences.

## Required at the end of every substantial work unit

1. Current commit and branch (verify with Git, never assume).
2. Completed work, described as behaviour, not file names.
3. Important discoveries, including data-access or licensing constraints.
4. Observed test/lint/type results with the environment used.
5. Known defects and flaky-environment caveats.
6. Remaining tasks and the exact next implementation objective.

## Accuracy rules

- Never claim a push, PR, merge, release or build succeeded without verifying the remote response.
- Never present CI results as local results, or local results as production/Windows evidence.
- Replace stale commit hashes after history rewrites.
- Do not mark a milestone complete because a UI exists; require domain, data flow, persistence, service connection, error handling and tests.
- Keep README's current-development slice consistent with the status documents.

## Session continuity

Before resuming after context loss, read the status files and verify their claims against the actual repository. If a claim disagrees with Git state or source, correct the document first.
