# Local Automation

Formula version: `automation-jobs-v1`. Implementation:
`src/rfinance/domain/automation/jobs.py`, `src/rfinance/application/automation.py`,
migration `0011_automation`, and the Automation Center desktop page.

## Job registry

Jobs are **code-defined** in `bootstrap.py`; no document, model output or UI
action can register a new job at runtime. Each `JobDefinition` carries a stable
ID, display name, description, enabled flag, maximum attempts (1–5) and a
timeout policy (1–3600 seconds). `register_jobs()` is idempotent and writes the
registry to the append-only `automation_jobs` table.

Current registered jobs:

- `BACKUP_CREATE` — writes a verified SQLite backup via `sqlite-backup-v1`.
- `PORTFOLIO_VALUATION` — recomputes the simulated valuation from locally
  stored evidence.

Both are local operations against the existing application services. No
network request, shell command, browser action or external URL is available to
a job.

## Run ledger and retry

Every attempt writes an append-only `automation_runs` row with a deterministic
run ID derived from job ID, UTC start time and attempt number. A successful
operation adds a `SUCCEEDED` completion row; a failure adds a `FAILED` row with
the exception type and message. `RUNNING` start rows are never rewritten, so
the sequence of events remains auditable. A failed attempt is retried only up
to `max_attempts`; the final `JobRun` reports the last status and attempt.

`can_transition()` and `is_terminal()` encode the run state machine in the
domain layer. `PENDING`, `CANCELLED` and cooperative cancellation are defined
in policy but automatic scheduling is not implemented in this slice.

## Boundaries and deferred work

- Jobs never run implicitly; the desktop page starts them explicitly.
- A failed data source is reported as a failed run and does not stop the
  application.
- Timeout and cancellation are recorded policy fields, not a hard preemption
  of a blocking operation. True timeout enforcement and cancellation of an
  in-flight job require worker-level control and remain deferred.
- Windows Task Scheduler integration, recurring schedules, notification
  delivery and externally supplied job definitions are not implemented.
