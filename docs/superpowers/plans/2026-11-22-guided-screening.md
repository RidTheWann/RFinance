# Guided Screening Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate one instrument from persisted evidence and operator-supplied fundamentals, persisting the recommendation.

**Architecture:** New application service assembles evidence and delegates to `RecommendationService`; a Research Center form triggers it off the UI thread.

**Tech Stack:** Python 3.12, Decimal, SQLAlchemy, PySide6, pytest/Hypothesis.

**Spec:** `docs/superpowers/specs/2026-11-22-guided-screening-design.md`

## Global Constraints

- All money/ratios are `Decimal`; no fabricated values; no AI authority.
- `AGENTS.md` canonical. BUY_CANDIDATE blocked on stale/unverified/incomplete evidence.
- Fundamental inputs are operator-supplied and labelled, not filed facts.
- Every recommendation must carry evidence IDs, risk flags and invalidation conditions.

## Review Focus

- Unverified or stale price must block BUY_CANDIDATE — Task 1.
- Missing fundamentals must yield INSUFFICIENT_DATA, not zero — Task 1.
- Verified dividend evidence must appear in evidence IDs — Task 1.
- Duplicate/unknown instrument must fail clearly — Task 1.
- UI must not perform domain assembly — Task 2.

---

### Task 1: Screening evaluation service

**Files:** `src/rfinance/application/screening_evaluation.py`, `tests/integration/test_screening_evaluation.py`

**Interfaces:**
- Consumes: `ScreeningInput`, `compute_fundamental_metrics`, `RecommendationService`, `DividendEventService`, `ObservationReviewService`.
- Produces: `ScreeningEvaluationService.evaluate(...) -> Recommendation`.

- [ ] **Step 1:** Write failing tests for a healthy eligible candidate (BUY_CANDIDATE, evidence includes price/dividend), unverified price (WATCH + STALE/UNVERIFIED flag), missing fundamentals (INSUFFICIENT_DATA), unknown instrument.
- [ ] **Step 2:** Run tests, observe FAIL.
- [ ] **Step 3:** Implement service reading instrument/source/observation/dividend records and delegating to `RecommendationService.evaluate`.
- [ ] **Step 4:** Run tests and full unit/integration suite, observe PASS.
- [ ] **Step 5:** Commit `feat(application): assemble guided screening evidence`.

### Task 2: Research Center form

**Files:** `src/rfinance/ui/research_page.py`, `src/rfinance/bootstrap.py`, `src/rfinance/main.py`, `tests/ui/test_research_page.py`

- [ ] **Step 1:** Write a failing Qt test that fills the evaluation form and sees the returned action/evidence.
- [ ] **Step 2:** Run it, observe FAIL.
- [ ] **Step 3:** Add form, worker-backed evaluate action, and result display; wire service.
- [ ] **Step 4:** Run UI tests, observe PASS.
- [ ] **Step 5:** Commit `feat(ui): connect guided screening evaluation`.

### Task 3: Verification, docs, PR

- [ ] **Step 1:** Run Ruff/Mypy/full pytest.
- [ ] **Step 2:** Update status/roadmap/test report/changelog and `docs/SCREENING.md`.
- [ ] **Step 3:** Push branch, open PR, wait for both CI jobs, merge with 0 approvals.
- [ ] **Step 4:** Verify main CI green.
