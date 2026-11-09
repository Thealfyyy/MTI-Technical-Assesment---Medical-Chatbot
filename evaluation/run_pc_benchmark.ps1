# Phase 1 One-Command Benchmark Runner for the RTX 3090 PC (or any Windows host)
# Usage from PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\evaluation\run_pc_benchmark.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " MTI Medical Chatbot - Phase 1 Hardware & Model Benchmark" -ForegroundColor Cyan
Write-Host " Project Root: $ProjectRoot" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PyVenvCfg  = Join-Path $ProjectRoot ".venv\pyvenv.cfg"

# Verify whether .venv\Scripts\python.exe works on this machine (in case Windows username/Python path differs)
$venvWorks = $false
if (Test-Path $VenvPython) {
    try {
        $verOut = & $VenvPython --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $venvWorks = $true
            Write-Host "[OK] Using existing portable virtualenv Python: $verOut" -ForegroundColor Green
        }
    } catch {
        $venvWorks = $false
    }
}

if (-not $venvWorks) {
    Write-Host "[INFO] Adapting .venv\pyvenv.cfg to this machine's Python installation..." -ForegroundColor Yellow
    $sysPy = $null
    try {
        $sysPy = (& py -3.12 -c "import sys; print(sys.executable)" 2>$null).Trim()
    } catch {}
    if (-not $sysPy) {
        try {
            $sysPy = (& python -c "import sys; print(sys.executable)" 2>$null).Trim()
        } catch {}
    }
    if (-not $sysPy -or -not (Test-Path $sysPy)) {
        throw "Could not locate Python 3.12 on this machine. Please ensure Python 3.12 is installed and on PATH."
    }
    $sysPyDir = Split-Path -Parent $sysPy
    $cfgLines = @(
        "home = $sysPyDir",
        "include-system-site-packages = false",
        "version = 3.12.1",
        "executable = $sysPy"
    )
    Set-Content -Path $PyVenvCfg -Value ($cfgLines -join "`r`n") -Encoding UTF8
    Write-Host "[OK] Updated .venv\pyvenv.cfg home -> $sysPyDir" -ForegroundColor Green
}

# Run the Phase 1 benchmark (auto-detects NVIDIA RTX 3090 + Vulkan GPU offload -ngl 99)
if ($args.Count -eq 0) {
    & $VenvPython (Join-Path $ProjectRoot "evaluation\phase1_benchmark.py") --stage all
} else {
    & $VenvPython (Join-Path $ProjectRoot "evaluation\phase1_benchmark.py") @args
}
