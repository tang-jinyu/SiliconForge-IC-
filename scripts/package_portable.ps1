[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DistRoot = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $OutputDirectory))
if (-not $DistRoot.StartsWith($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDirectory must stay inside the project root."
}
New-Item -ItemType Directory -Path $DistRoot -Force | Out-Null

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Archive = Join-Path $DistRoot "siliconforge-portable-$Stamp.zip"
$Tar = Get-Command tar.exe -ErrorAction Stop

$Arguments = @(
    "-a", "-c", "-f", $Archive,
    "--exclude=__pycache__", "--exclude=*.pyc", "--exclude=*.log", "--exclude=*.pb",
    "Dockerfile", "compose.yaml", "compose.h100.yaml", "compose.tunnel.yaml", ".dockerignore",
    ".gitignore", ".env.example", ".env.server.example", "pyproject.toml", "README.md",
    "LICENSE", "CONTRIBUTING.md", "CONTRIBUTORS.md", "ROADMAP.md", "CHANGELOG.md", "BRAND.md", "CITATION.cff",
    "digital_ic_agent", "project_prompt", "prompt", "skills", "benchmarks", "picture",
    "examples", "docs", "scripts", "tests", "打开数字IC-Agent网页.cmd"
)
Push-Location $ProjectRoot
try {
    & $Tar.Source @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "tar failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$H