# Claude Code — RFinance Operating Instructions

1. Read `AGENTS.md` completely before inspecting or editing code. It is the canonical policy.
2. Read `IMPLEMENTATION_STATUS.md`, `ROADMAP.md`, and `TEST_REPORT.md`; verify their claims against the current Git state and source.
3. Work autonomously in continuous implementation loops. Do not stop after planning, one task, or a progress report.
4. Inspect the current worktree and preserve all uncommitted/user work. Never force-push or destructively rewrite Git history.
5. Research uncertain technical, financial, data-provider, licensing, and Windows behavior from official current sources. Cite URLs in the relevant research/ADR documentation.
6. Prefer small functional vertical slices. Add tests and run them, Ruff, Mypy, and relevant security checks. Report only observed results.
7. Keep deterministic financial calculations and accounting authoritative. Use Decimal for monetary values; AI and retrieved documents are untrusted.
8. Update implementation tracking, roadmap, test report, and changelog as work progresses.
9. Commit coherent changes on focused branches, open reviewable PRs, verify CI, then continue with the next unfinished objective.
10. Stop only for a genuine authorization boundary, missing indispensable access, or a critical unresolved safety/correctness issue. Record the exact blocker and continue with independent work.
