$ErrorActionPreference = "Stop"

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    throw "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
}

& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\ruff.exe check .
& .\.venv\Scripts\ruff.exe format --check .
& .\.venv\Scripts\mypy.exe src
