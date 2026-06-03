#!/usr/bin/env pwsh
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Update-PathFromEnvironment {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machine, $user, $env:Path) -join ";")
}

function Find-Bash {
    $candidates = @(
        "bash",
        "C:\Program Files\Git\bin\bash.exe",
        "C:\Program Files\Git\usr\bin\bash.exe"
    )
    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command -and $command.Source -and ($command.Source -notlike "*\WindowsApps\bash.exe")) {
            return $command.Source
        }
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return $null
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,
        [Parameter(Mandatory = $true)]
        [scriptblock] $Script
    )

    Write-Host ""
    Write-Host "==> $Name"
    $global:LASTEXITCODE = 0
    & $Script
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Update-PathFromEnvironment

$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repo

Write-Host "Running no-hardware USB2BLE validation on Windows..."

Invoke-Step "Rust format" {
    cargo fmt --all -- --check
}

Invoke-Step "Rust clippy" {
    cargo clippy --workspace --all-targets --locked -- -D warnings
}

Invoke-Step "Rust build" {
    cargo build --workspace --locked
}

Invoke-Step "Rust tests" {
    cargo test --workspace --locked
}

Invoke-Step "Shell syntax" {
    $bash = Find-Bash
    if (-not $bash) {
        Write-Warning "Git Bash was not found; skipping shell syntax checks on Windows. CI/Linux Bash checks remain authoritative."
        return
    }
    & $bash -lc "cd '$($repo.Path -replace '\\', '/')' && bash -n scripts/*.sh"
}

Invoke-Step "Python compile" {
    $files = @()
    $files += Get-ChildItem tools -Filter "*.py" -File | ForEach-Object { $_.FullName }
    $files += Get-ChildItem tools\gamepad_witness -Filter "*.py" -File | ForEach-Object { $_.FullName }
    python -m py_compile @files
}

Invoke-Step "Evidence docs" {
    python tools/check_evidence_docs.py
}

Invoke-Step "Launch readiness" {
    python tools/check_launch_readiness.py
}

Invoke-Step "Release candidate" {
    python tools/check_release_candidate.py
}

Invoke-Step "BLE HID profile" {
    python tools/check_ble_hid_profile.py --variant generic_default --variant generic_hogp_strict --quiet
}

Invoke-Step "Xbox BLE profile" {
    python tools/check_xbox_ble_profile.py --quiet
}

Invoke-Step "Persona acceptance" {
    python tools/check_persona_acceptance.py --quiet
}

if (Test-Path tools\tests) {
    Invoke-Step "Python unit tests" {
        python -m unittest discover -s tools/tests -p "test_*.py"
    }
}

if (Test-Path web) {
    Invoke-Step "Web checks" {
        Push-Location web
        try {
            npm ci
            npm test
            npm run build
        } finally {
            Pop-Location
        }
    }
}

Write-Host ""
Write-Host "No-hardware validation complete."
