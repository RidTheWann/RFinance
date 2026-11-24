# Windows Installation

RFinance is distributed as a self-contained Windows 11 x64 folder produced by
PyInstaller. No Python installation, broker account or application login is
required to run it.

## Building

From a clean checkout on Windows:

```powershell
.\scripts\setup_windows.ps1
.\scripts\build_windows.ps1
```

`setup_windows.ps1` auto-detects a supported Python 3.12–3.15 runtime (it uses
`py -3.13` first and falls back to 3.12, 3.14 and 3.15). Earlier versions hard-coded
`py -3.12`, which failed on machines without Python 3.12. Pass `-Python "py -3.13"`
to override, or `-DryRun` to see which interpreter would be selected without
creating a virtual environment. If PowerShell blocks local scripts, run with
`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1`.

PyInstaller is pinned in the `dev` extra and in `requirements.lock`. The build
uses `installer/windows/rfinance.spec`, which bundles the Alembic migration
directory, the GPLv3 `LICENSE` and `docs/THIRD_PARTY_NOTICES.md`. The output is
`dist\RFinance\RFinance.exe`.

## Running and data location

Run `RFinance.exe` from the output folder. Application data is **never** stored
inside the program folder. It defaults to `%LOCALAPPDATA%\RFinance` and can be
redirected with the `RFINANCE_HOME` environment variable. The folders created
are `Database`, `Documents`, `Cache`, `Reports`, `Backups` and `Logs`.

Because data lives outside the installation directory, replacing or upgrading
the program folder preserves the portfolio database and evidence archives.
Before upgrading, create a verified backup from Settings (see
`docs/BACKUP_RESTORE.md`); migrations are applied automatically on startup and
are append-only with respect to recorded financial events.

## Verified smoke test (2026-11-23)

The frozen executable was launched with a fresh `RFINANCE_HOME` on Windows 11
x64. It stayed alive, created the SQLite database with WAL/SHM files and a log,
and reached Alembic head `0012_instrument_category` with 22 tables. No Python
interpreter from the development virtualenv was used by the executable.

## Licensing notices

RFinance is GPL-3.0-only. The frozen distribution includes the verbatim
`LICENSE` and `THIRD_PARTY_NOTICES.md` at the top level of the output folder.
Qt/PySide6 modules used by RFinance are available under LGPLv3/GPLv3; see ADR
0003 for the distribution obligations. Do not strip these files when
redistributing the folder.

## Limitations

- This is a built and locally smoke-tested Windows folder, not a signed MSI or
  installer executable; there is no code-signing certificate in this project.
- A clean-install-on-a-different-machine test, an in-place upgrade test and a
  data-preservation test after upgrade are still required before a production
  release claim.
- Antivirus or SmartScreen warnings on an unsigned executable are expected and
  must be handled by the distributor.
