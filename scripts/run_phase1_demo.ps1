param(
    [string]$OutputDir = "runs/phase1_demo",
    [switch]$Serve,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Validator = $env:DIGITAL_IC_AGENT_SKILL_VALIDATOR
$SkillDir = Join-Path $ProjectRoot "skills\digital-ic-verified-design"
$SuiteDir = Join-Path $ProjectRoot "benchmarks\phase1"
$ResolvedOutput = Join-Path $ProjectRoot $OutputDir

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python virtual environment was not found at $Python"
}

Push-Location $ProjectRoot
try {
    if ($Validator -and (Test-Path -LiteralPath $Validator)) {
        & $Python $Validator $SkillDir
        if ($LASTEXITCODE -ne 0) { throw "Skill validation failed." }
    }

    & $Python -m digital_ic_agent benchmark-run --suite-dir $SuiteDir --output-dir $ResolvedOutput
    if ($LASTEXITCODE -ne 0) { throw "Phase 1 benchmark process failed." }

    $ReportPath = Join-Path $ResolvedOutput "benchmark_report.json"
    $Report = Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json
    if ($Report.passed_cases -ne $Report.case_count) {
        throw "Phase 1 acceptance failed: $($Report.passed_cases)/$($Report.case_count) cases passed. See $ReportPath"
    }

    Write-Host "Phase 1 acceptance passed: $($Report.passed_cases)/$($Report.case_count), average score $($Report.average_score)."
    Write-Host "Report: $ReportPath"

    if ($Serve) {
        Write-Host "Opening the product at http://127.0.0.1:$Port"
        Start-Process "http://127.0.0.1:$Port"
        & $Python -m digital_ic_agent serve --host 127.0.0.1 --port $Port
    } else {
        Write-Host "To open the web product, run: .\scripts\run_phase1_demo.ps1 -Serve"
    }
} finally {
    Pop-Location
}
