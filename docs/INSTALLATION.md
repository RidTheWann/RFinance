# Windows Installation

RFinance is a native Windows 11 x64 desktop application. The distributable is
built as a PyInstaller one-folder application and wrapped in a per-user Inno
Setup installer. End users do not need Python, pip, Qt, or a terminal.

## Install from a packaged release

1. Download `RFinance-Setup-<version>-win-x64.exe` from the
   [GitHub Releases](https://github.com/RidTheWann/RFinance/releases) page.
2. Run the installer. It installs RFinance under
   `%LOCALAPPDATA%\Programs\RFinance` and creates a Start Menu shortcut.
3. Optionally select the desktop shortcut in the installer.
4. Launch **RFinance** from the Start Menu.

The installer is per-user and does not require administrator privileges.
Uninstall removes the application files and shortcuts. It deliberately does
**not** delete user data under `%LOCALAPPDATA%\RFinance`.

A portable ZIP (`RFinance-Portable-<version>-win-x64.zip`) is also attached
to each tagged release. Extract the complete folder and launch
`RFinance.exe`; do not move only the executable out of its bundled folder.

## Building

From a clean checkout on Windows:

```powershell
.\scripts\setup_windows.ps1
.\.venv\Scripts\Activate.ps1
.\scripts\build_windows.ps1
```

The commands above create and smoke-test the portable one-folder build. To also
compile the installable setup executable, install Inno Setup 6 and run:

```powershell
choco install innosetup --yes --no-progress
.\scripts\build_windows.ps1 -CreateInstaller
```

The installer compiler can also be selected explicitly through
`$env:ISCC_PATH`. PyInstaller and application dependencies are pinned through
the project dev extra and `requirements.lock`.

## Automated build and release

The **Windows Package** GitHub Actions workflow builds on packaging-related PRs,
can be started manually, and publishes release assets for a version tag
(`v<project-version>`). It runs the frozen executable with the private
`--smoke-test` switch against an isolated temporary data directory, proving
that SQLite startup and the bundled Alembic migrations work before uploading
the installer and portable ZIP. Pull-request builds are available as a
14-day Actions artifact; tagged builds are attached to GitHub Releases.

For a tag to publish, its version must match `src/rfinance/__init__.py` and
`pyproject.toml`. The build script rejects a mismatch.

## Running and data location

Application data is **never** stored inside the program folder. It defaults to
`%LOCALAPPDATA%\RFinance` and can be redirected with the `RFINANCE_HOME`
environment variable. The folders created are `Database`, `Documents`,
`Cache`, `Reports`, `Backups` and `Logs`.

Because data lives outside the installation directory, replacing or upgrading
the program preserves the portfolio database and evidence archives. Before
upgrading, create a verified backup from Settings (see
`docs/BACKUP_RESTORE.md`); migrations are applied automatically on startup.
The installer never asks for broker credentials and does not install a service,
driver, browser extension, or background updater.

## Licensing and trust

RFinance is GPL-3.0-only. The distributable contains the verbatim `LICENSE`
and `THIRD_PARTY_NOTICES.md`; the installer also displays the GPL license
before installation. Corresponding source, build scripts and packaging
configuration are published in the repository. See ADR 0003 for the Qt/PySide6
distribution obligations.

The installer is currently **unsigned** because the project has no code-signing
certificate. Windows SmartScreen or antivirus reputation warnings may appear.
Do not disable security software to install it; verify the download source and
published release checksums when available.

## Acceptance still required before a production claim

- Test the installer on a clean Windows 11 x64 machine that has no Python or Qt
  development environment.
- Verify first launch, Start Menu/desktop shortcuts and uninstallation.
- Verify in-place upgrade with an existing database and confirm that uninstall
  leaves user data untouched.
- Add a trusted Authenticode signature before broad public distribution.
