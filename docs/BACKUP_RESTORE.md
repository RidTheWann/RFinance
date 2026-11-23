# Backup and Restore

Formula version: `sqlite-backup-v1`. Implementation:
`src/rfinance/security/backup.py`, exposed through the Settings page.

## Why not copy the open database file

RFinance uses SQLite in WAL mode. Copying `rfinance.sqlite3` while the
application is running can capture an inconsistent mix of pages and WAL state.
`BackupService` therefore uses SQLite's online backup API through a read-only
source connection, which produces a coherent snapshot.

## Backup

`create_backup()` writes a timestamped `*.sqlite3` file under the per-user
`Backups` directory and a sibling `*.sqlite3.manifest.json` recording:

- methodology version and UTC creation time;
- source database path;
- SHA-256 digest of the backup file;
- Alembic schema version and ledger event count.

`verify_backup()` reopens the file read-only and measures `PRAGMA
integrity_check`, schema version, ledger event count and the actual SHA-256
digest. A manifest digest mismatch is reported explicitly and makes
`is_ok` false; no value is assumed correct merely because a manifest exists.

## Restore

`restore_to(backup_path, target_dir)` first verifies the source and refuses to
continue when verification fails. It then writes `rfinance.sqlite3` into the
chosen folder and refuses to overwrite an existing database. The restored file
is verified again and its digest compared with the source; on mismatch the new
file is removed.

This is deliberately **non-destructive**: the live database is never replaced
by a background action. To use a restored copy, point `RFINANCE_HOME` at the
folder containing it and confirm the schema version and ledger history before
use. A destructive in-place restore would require an explicit offline flow and
is not implemented in this slice.

## Boundaries

- Only local files selected by the operator are read; no network source is
  contacted.
- Backups contain local research and simulated portfolio records and must be
  treated as private data.
- A verified backup is evidence that the file is internally coherent, not proof
  that every recorded observation was truthful.
