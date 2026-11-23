# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
$ErrorActionPreference = "Stop"

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    throw "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
}

$spec = Resolve-Path .\installer\windows\rfinance.spec
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --distpath .\dist --workpath .\build $spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$output = Resolve-Path .\dist\RFinance
Copy-Item -Force .\LICENSE (Join-Path $output "LICENSE")
if (Test-Path .\docs\THIRD_PARTY_NOTICES.md) {
    Copy-Item -Force .\docs\THIRD_PARTY_NOTICES.md (Join-Path $output "THIRD_PARTY_NOTICES.md")
}

Write-Host "Windows build ready: $output"
Write-Host "Run: & (Join-Path '$output' 'RFinance.exe')"
