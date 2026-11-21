# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
param(
    [string]$Python = "py -3.12"
)

$ErrorActionPreference = "Stop"

Invoke-Expression "$Python -m venv .venv"
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"

Write-Host "RFinance development environment is ready."
Write-Host "Activate with: .\.venv\Scripts\Activate.ps1"
