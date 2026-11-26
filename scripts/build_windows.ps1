# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
[CmdletBinding()]
param(
    [switch]$CreateInstaller
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root

try {
    $python = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        $command = Get-Command python -ErrorAction SilentlyContinue
        if ($null -eq $command) {
            throw "Python was not found. Run .\scripts\setup_windows.ps1 or activate a supported Python environment."
        }
        $python = $command.Source
    }

    & $python -m pip show pyinstaller *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is not installed in the selected Python environment. Install the project dev extra first."
    }

    $version = (& $python -c "from rfinance import __version__; print(__version__)").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $version) {
        throw "Could not read the application version from rfinance.__version__."
    }

    if ($env:GITHUB_REF_TYPE -eq "tag") {
        $tagVersion = $env:GITHUB_REF_NAME -replace '^v', ''
        if ($tagVersion -ne $version) {
            throw "Release tag v$tagVersion does not match package version $version. Update pyproject.toml and src/rfinance/__init__.py first."
        }
    }

    $spec = Join-Path $root "installer\windows\rfinance.spec"
    $dist = Join-Path $root "dist"
    $work = Join-Path $root "build"
    & $python -m PyInstaller --noconfirm --clean --distpath $dist --workpath $work $spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }

    $output = Join-Path $dist "RFinance"
    $executable = Join-Path $output "RFinance.exe"
    if (-not (Test-Path $executable)) {
        throw "PyInstaller completed without producing dist\RFinance\RFinance.exe."
    }

    Copy-Item -Force (Join-Path $root "LICENSE") (Join-Path $output "LICENSE")
    $notices = Join-Path $root "docs\THIRD_PARTY_NOTICES.md"
    if (Test-Path $notices) {
        Copy-Item -Force $notices (Join-Path $output "THIRD_PARTY_NOTICES.md")
    }

    # Exercise the frozen binary against a clean, disposable per-user data root.
    # This verifies bundled migrations and SQLite bootstrap without showing a UI.
    $smokeRoot = Join-Path $env:TEMP ("RFinance-Package-Smoke-" + [Guid]::NewGuid().ToString("N"))
    $previousHome = $env:RFINANCE_HOME
    try {
        New-Item -ItemType Directory -Path $smokeRoot -Force | Out-Null
        $env:RFINANCE_HOME = $smokeRoot
        & $executable --smoke-test
        if ($LASTEXITCODE -ne 0) {
            throw "The frozen executable failed its isolated startup/migration smoke test."
        }
        $database = Join-Path $smokeRoot "Database\rfinance.sqlite3"
        if (-not (Test-Path $database)) {
            throw "The frozen executable did not create the expected per-user SQLite database."
        }
        Write-Host "Frozen executable smoke test passed: $database"
    }
    finally {
        if ($null -eq $previousHome) {
            Remove-Item Env:RFINANCE_HOME -ErrorAction SilentlyContinue
        }
        else {
            $env:RFINANCE_HOME = $previousHome
        }
        if (Test-Path $smokeRoot) {
            Remove-Item $smokeRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    $portableArchive = Join-Path $dist "RFinance-Portable-$version-win-x64.zip"
    if (Test-Path $portableArchive) {
        Remove-Item $portableArchive -Force
    }
    Compress-Archive -Path (Join-Path $output "*") -DestinationPath $portableArchive -CompressionLevel Optimal
    Write-Host "Portable package ready: $portableArchive"

    if ($CreateInstaller) {
        $iscc = $env:ISCC_PATH
        if (-not $iscc -or -not (Test-Path $iscc)) {
            $candidate = Get-Command ISCC.exe -ErrorAction SilentlyContinue
            if ($null -ne $candidate) {
                $iscc = $candidate.Source
            }
        }
        if (-not $iscc -or -not (Test-Path $iscc)) {
            $programFilesX86 = [Environment]::GetFolderPath("ProgramFilesX86")
            $programFiles = [Environment]::GetFolderPath("ProgramFiles")
            $candidates = @(
                (Join-Path $programFilesX86 "Inno Setup 6\ISCC.exe"),
                (Join-Path $programFiles "Inno Setup 6\ISCC.exe")
            )
            $iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
        }
        if (-not $iscc -or -not (Test-Path $iscc)) {
            throw "Inno Setup 6 compiler (ISCC.exe) was not found. Install Inno Setup 6 or set ISCC_PATH."
        }

        $installerScript = Join-Path $root "installer\windows\rfinance.iss"
        & $iscc "/DAppVersion=$version" $installerScript
        if ($LASTEXITCODE -ne 0) {
            throw "Inno Setup failed to compile the RFinance installer."
        }
        $installer = Join-Path $dist "installer\RFinance-Setup-$version-win-x64.exe"
        if (-not (Test-Path $installer)) {
            throw "Inno Setup completed without producing $installer."
        }
        Write-Host "Windows installer ready: $installer"
    }
    else {
        Write-Host "Installer not requested. Pass -CreateInstaller after installing Inno Setup 6."
    }

    $artifactPaths = @($portableArchive)
    if ($CreateInstaller) {
        $artifactPaths += $installer
    }
    $checksumLines = foreach ($artifactPath in $artifactPaths) {
        $hash = Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256
        "$($hash.Hash.ToLowerInvariant())  $([IO.Path]::GetFileName($artifactPath))"
    }
    $checksumFile = Join-Path $dist "SHA256SUMS.txt"
    $checksumLines | Set-Content -LiteralPath $checksumFile -Encoding ascii
    Write-Host "Package checksums ready: $checksumFile"

    Write-Host "Windows x64 build complete for RFinance $version."
}
finally {
    Pop-Location
}
