# ADR 0003 — GPL-3.0-only license

Status: Accepted (2026-11-22). Supersedes the "all rights reserved" placeholder in the initial README.

## Context

RFinance is a local-first desktop application that redistributes Python source and will eventually be shipped as a Windows binary containing PySide6/Qt. A license must be selected before distribution, and the choice must be compatible with the application's runtime dependencies and with the project's `AGENTS.md` requirement to review Qt/PySide licensing obligations.

Requirements considered:

1. The user selected "GPL-3" as the product license.
2. PySide6 6.12 on PyPI is published as `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` (verified from the installed wheel metadata and the official Qt for Python documentation). GPL-3.0 code may therefore be used in a GPL-3.0 application; LGPLv3 is also GPLv3-compatible.
3. Packaging metadata must express the license as a standard SPDX identifier, not a free-text string.
4. Some Qt modules are GPLv3-only even in the Community distribution. RFinance currently uses only Qt Core, Gui, Widgets, Test and `QtCore.QUrl`/`QDesktopServices`, which are available under LGPLv3; no GPL-only Qt module is imported.

## Decision

- License the entire RFinance codebase under **GPL-3.0-only** (SPDX: `GPL-3.0-only`, "GNU General Public License v3.0 only"). The plain request "GPL-3" is interpreted literally as version 3 only, not "or any later version"; changing to `GPL-3.0-or-later` later is a one-line metadata change plus notice update.
- Ship the verbatim official GPLv3 text as `LICENSE` (FSF text, 674 lines; SHA-256 `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`).
- Declare `license = "GPL-3.0-only"` and `license-files = ["LICENSE"]` in `pyproject.toml` using PEP 639, and require `setuptools>=77.0.0` because that is the first setuptools version supporting PEP 639 (verified from the official setuptools documentation).
- Add `SPDX-License-Identifier: GPL-3.0-only` and a copyright/pointer notice to every Python and PowerShell source file.
- Document dependency licenses in `docs/THIRD_PARTY_NOTICES.md` using metadata read from the actually installed packages, rather than guessing.

## Alternatives rejected

- **GPL-3.0-or-later** — not what was requested; changes the permission to upgrade to future GPL versions without consent.
- **GPL-2.0-only / LGPL-3.0-only** — weaker copyleft than requested; LGPL is designed for libraries, while RFinance is an application.
- **MIT / Apache-2.0** — explicitly not chosen by the user.
- **Legacy `license = { text = ... }` plus license classifiers** — deprecated by PEP 639 and produces ambiguous machine-readable metadata.

## Consequences

### Obligations when distributing source

Recipients must receive the GPLv3 text, keep copyright and license notices intact, and receive the corresponding source of any modified version under the same license. Interactive UI should expose an Appropriate Legal Notice (GPL §0/§5d); the Settings/About area is the intended place to surface the license pointer.

### Obligations when distributing a Windows binary

If RFinance is frozen with PyInstaller/Nuitka, the resulting object-code distribution must comply with GPLv3 §6 (provide Corresponding Source or a valid written offer, preserve notices, include the license). PySide6's LGPLv3/GPLv3 notices and Qt's third-party notices must be retained; see `docs/THIRD_PARTY_NOTICES.md`. Qt modules are dynamically loaded from the bundled runtime, so relinking remains possible. No GPL-only Qt module may be added without re-checking this ADR.

### Frozen Windows build (2026-11-23)

`scripts/build_windows.ps1` plus `installer/windows/rfinance.spec` produce a
PyInstaller folder build. The spec bundles the verbatim `LICENSE`,
`docs/THIRD_PARTY_NOTICES.md` and the Alembic migration directory at the top
level of `dist\RFinance`, satisfying the notice-retention requirement above.
The build is windowed (`console=False`) and retains the PySide6 runtime hooks.
Redistributors must keep these files and provide Corresponding Source under
GPLv3 §6; see `docs/INSTALLATION.md`.

### Development impact

- Every new source file must carry the SPDX header; a unit test checks this invariant.
- Contributors' commits remain under the repository's existing GitHub identity; no personal email is embedded in source files.
- `pip install -e .` and CI packaging now require setuptools ≥ 77, which pip resolves from the build-system requirement.

## References

- SPDX license list: https://spdx.org/licenses/GPL-3.0-only.html
- GNU GPLv3 text: https://www.gnu.org/licenses/gpl-3.0.html
- Qt licensing: https://doc.qt.io/qt-6/licensing.html
- Qt for Python licensing: https://doc.qt.io/qtforpython-6/commercial/index.html
- PySide6 PyPI metadata: https://pypi.org/project/PySide6/
- setuptools PEP 639 support: https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html
