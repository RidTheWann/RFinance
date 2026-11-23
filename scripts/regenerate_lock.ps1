# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
$ErrorActionPreference = "Stop"

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    throw "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
}

$header = @(
    "# Generated dependency lock for RFinance.",
    "# Source: pip freeze --exclude-editable in the active development environment.",
    "# Regenerate with: .\scripts\regenerate_lock.ps1",
    "# The rfinance package itself is installed editable and is intentionally excluded.",
    ""
)

$pinned = & .\.venv\Scripts\python.exe -m pip freeze --exclude-editable |
    Where-Object { $_ -and $_ -notmatch '^rfinance' }

Set-Content -Path .\requirements.lock -Value ($header + $pinned) -Encoding utf8
Write-Host "Regenerated requirements.lock from the active virtual environment."
