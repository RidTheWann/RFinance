# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
param(
    [string]$Python = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Test-SupportedPython {
    param([string]$Command)
    $parts = $Command -split '\s+'
    $exe = $parts[0]
    $args = @()
    if ($parts.Count -gt 1) { $args = $parts[1..($parts.Count - 1)] }
    try {
        $output = & $exe @args -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $output) { return $false }
        $version = [version]::Parse($output.Trim())
        return ($version -ge [version]"3.12" -and $version -lt [version]"3.16")
    }
    catch {
        return $false
    }
}

if ($Python) {
    if (-not (Test-SupportedPython $Python)) {
        throw "The specified Python is not a supported 3.12-3.15 runtime: $Python"
    }
    $selected = $Python
}
else {
    $candidates = @("py -3.13", "py -3.12", "py -3.14", "py -3.15", "python", "py -3")
    $selected = $null
    foreach ($candidate in $candidates) {
        if (Test-SupportedPython $candidate) {
            $selected = $candidate
            break
        }
    }
    if (-not $selected) {
        throw "No supported Python 3.12-3.15 runtime found. Install Python 3.13 or pass -Python explicitly."
    }
}

Write-Host "Selected Python: $selected"
if ($DryRun) {
    Write-Host "Dry run: no environment was created."
    exit 0
}

Invoke-Expression "$selected -m venv .venv"
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"

Write-Host "RFinance development environment is ready."
Write-Host "Activate with: .\.venv\Scripts\Activate.ps1"
