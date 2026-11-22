# Confirmed Dividend Receipts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Post explicitly confirmed net dividend receipts into the simulated ledger with duplicate protection and an auditable 50/30/20 split.

**Architecture:** Add one ledger event type and rebuild its SQLite table to extend the CHECK constraint; add an application service that gates on verified dividend evidence and appends a receipt plus withdrawal leg; expose it in the existing Dividend Center page.

**Tech Stack:** Python 3.12, Decimal, SQLAlchemy 2.1, Alembic, PySide6, pytest/Hypothesis.

**Spec:** `docs/superpowers/specs/2026-11-22-confirmed-dividend-receipts-design.md`

## Global Constraints

- All money is `Decimal`; SQLite stores exact fixed-point text.
- Base currency is IDR; no conversion and no inferred withholding.
- Ledger is append-only; balances are reconstructable by replay.
- `AGENTS.md` is canonical; no broker, real money, AI posting, or simulated receipt labelled actual.
- Weights are exactly `0.50` reinvest, `0.30` money market, `0.20` withdrawal.
- `source_reference` keys: `DIVIDEND_RECEIPT:<event_id>` and `DIVIDEND_WITHDRAWAL:<event_id>`.

## Review Focus

- A verified-but-`ESTIMATED` dividend event must be rejected — test in Task 3.
- A second post for the same dividend event must be rejected by replay, DB constraint and service — Task 3.
- Withdrawal leg must leave cash so replay reconciles — Task 1 and Task 3.
- Missing/unverified instrument identity must block posting — Task 3.
- Legacy ledger rows must survive the SQLite table rebuild — Task 2.

---

### Task 1: Ledger event type and replay accounting

**Files:** `src/rfinance/domain/portfolio/ledger.py`, `tests/unit/test_portfolio_ledger.py`

**Interfaces:**
- Produces: `LedgerEventType.CONFIRMED_DIVIDEND`; `LedgerReplayResult.confirmed_dividend_income: Decimal`.

- [ ] **Step 1: Write failing tests** for event validation (positive net amount, source_reference required, no trade fields) and replay (cash credited, income accumulated, duplicate `(instrument, source_reference)` rejected).
- [ ] **Step 2:** Run `pytest tests/unit/test_portfolio_ledger.py -q`, observe FAIL.
- [ ] **Step 3:** Add the enum member, `_validate_confirmed_dividend`, and replay branch with a dedicated seen-key set.
- [ ] **Step 4:** Run the test file, observe PASS.
- [ ] **Step 5:** Commit `feat(ledger): add confirmed dividend event type and replay`.

### Task 2: Persistence migration and model

**Files:** `src/rfinance/storage/migrations/versions/0008_confirmed_dividend_receipts.py`, `src/rfinance/storage/models/dividend.py`, `src/rfinance/storage/models/__init__.py`, `tests/integration/test_dividend_receipts.py`

**Interfaces:**
- Produces: `DividendReceiptRecord` with unique `dividend_event_id`, exact Decimal text columns and append-only triggers.

- [ ] **Step 1: Write failing integration test** that upgrades a fresh database, inserts a legacy `CAPITAL_INJECTION` row, then asserts the extended CHECK accepts `CONFIRMED_DIVIDEND` and the receipt table rejects duplicate event IDs and updates/deletes.
- [ ] **Step 2:** Run it, observe FAIL (unknown table / constraint).
- [ ] **Step 3:** Implement the table rebuild (create `_new`, copy rows, drop old indexes/triggers/table, rename, recreate indexes/triggers) and the new table. Register the model and add SPDX header.
- [ ] **Step 4:** Run integration tests, observe PASS.
- [ ] **Step 5:** Commit `feat(storage): persist confirmed dividend receipts`.

### Task 3: Posting service

**Files:** `src/rfinance/application/dividend_receipts.py`, `tests/integration/test_dividend_receipts.py`, `src/rfinance/bootstrap.py`

**Interfaces:**
- Consumes: `DividendEventService`, `PortfolioLedgerService`, `allocate_confirmed_dividend`.
- Produces: `DividendReceiptResult` with receipt id, net amount, allocation parts, ledger event ids.

- [ ] **Step 1: Write failing tests** for: verified cash event posts and splits exactly; unverified/estimated/cancelled events rejected; duplicate event rejected; withdrawal leg booked; cash reconciles with replay.
- [ ] **Step 2:** Run them, observe FAIL.
- [ ] **Step 3:** Implement service using the design's gates and two append calls; wire into bootstrap.
- [ ] **Step 4:** Run tests, observe PASS.
- [ ] **Step 5:** Commit `feat(application): post confirmed dividend receipts`.

### Task 4: Desktop workflow

**Files:** `src/rfinance/ui/dividend_page.py`, `src/rfinance/ui/main_window.py`, `src/rfinance/main.py`, `tests/ui/test_dividend_page.py`

- [ ] **Step 1:** Write a failing Qt test for the receipt form rendering a verified event's allocation result from a stubbed service.
- [ ] **Step 2:** Run it, observe FAIL.
- [ ] **Step 3:** Add the form, worker-backed post action, result labels and busy handling.
- [ ] **Step 4:** Run UI tests, observe PASS.
- [ ] **Step 5:** Commit `feat(ui): connect confirmed dividend receipt workflow`.

### Task 5: Verification and handoff

- [ ] **Step 1:** Run Ruff lint/format, Mypy, full pytest.
- [ ] **Step 2:** Update `docs/DIVIDEND_EVENTS.md`, `docs/PORTFOLIO_ACCOUNTING.md`, status/roadmap/test report/changelog.
- [ ] **Step 3:** Push and verify Windows + Ubuntu CI green before merging.
- [ ] **Step 4:** Commit documentation handoff.
