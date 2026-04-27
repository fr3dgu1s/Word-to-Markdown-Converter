# scripts/setup-windows.ps1
# One-shot Windows setup for the Word-to-Markdown Converter.
#
# - Creates portable runtime folders under C:\temp\W2MD
# - Copies .env.example to .env if missing
# - Publishes the C# MipHelper project (net8.0, win-x64, framework-dependent)
# - Copies MipHelper.exe to C:\temp\W2MD\MipHelper\MipHelper.exe
# - Validates the final layout

[CmdletBinding()]
param(
    [string]$AppDataRoot = 'C:\temp\W2MD',
    [switch]$SkipPublish
)

$ErrorActionPreference = 'Stop'

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

# Resolve repo root (this script lives in /scripts).
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')

$Folders = @(
    $AppDataRoot,
    (Join-Path $AppDataRoot 'Outputs'),
    (Join-Path $AppDataRoot 'Outputs\Single'),
    (Join-Path $AppDataRoot 'Outputs\Batch'),
    (Join-Path $AppDataRoot 'Outputs\Images'),
    (Join-Path $AppDataRoot 'Temp'),
    (Join-Path $AppDataRoot 'Temp\Cloud'),
    (Join-Path $AppDataRoot 'Temp\Protected'),
    (Join-Path $AppDataRoot 'Logs'),
    (Join-Path $AppDataRoot 'MipHelper')
)

Write-Step "Creating runtime folders under $AppDataRoot"
foreach ($f in $Folders) {
    New-Item -ItemType Directory -Path $f -Force | Out-Null
    Write-Host "  $f"
}

Write-Step "Bootstrapping .env"
$envPath = Join-Path $RepoRoot '.env'
$envExamplePath = Join-Path $RepoRoot '.env.example'
if (-not (Test-Path $envPath)) {
    if (Test-Path $envExamplePath) {
        Copy-Item $envExamplePath $envPath
        Write-Host "  Created $envPath from .env.example"
    } else {
        Write-Warning ".env.example not found. Skipping .env creation."
    }
} else {
    Write-Host "  $envPath already exists"
}

if (-not $SkipPublish) {
    Write-Step "Publishing MipHelper (net8.0 / win-x64, framework-dependent)"
    $csproj = Join-Path $RepoRoot 'MipHelper\MipHelper.csproj'
    if (-not (Test-Path $csproj)) {
        throw "MipHelper.csproj not found at $csproj"
    }

    & dotnet publish $csproj -c Release -r win-x64 --self-contained false `
        "-p:W2MDHelperRoot=$((Join-Path $AppDataRoot 'MipHelper'))"
    if ($LASTEXITCODE -ne 0) {
        throw "dotnet publish failed (exit code $LASTEXITCODE)."
    }

    $publishDir = Join-Path $RepoRoot 'MipHelper\bin\Release\net8.0\win-x64\publish'
    $destDir = Join-Path $AppDataRoot 'MipHelper'

    if (Test-Path $publishDir) {
        # The helper is framework-dependent: it needs MipHelper.dll,
        # MipHelper.deps.json, MipHelper.runtimeconfig.json, and every
        # dependency DLL alongside MipHelper.exe. Copy the WHOLE publish
        # folder, not just the .exe.
        Copy-Item "$publishDir\*" $destDir -Recurse -Force
        Write-Host "  Copied publish payload -> $destDir"
    } else {
        Write-Warning "Publish directory not found at $publishDir."
    }
} else {
    Write-Step "Skipping MipHelper publish (--SkipPublish)"
}

Write-Step "Validating final layout"
$destExe = Join-Path $AppDataRoot 'MipHelper\MipHelper.exe'
$destDll = Join-Path $AppDataRoot 'MipHelper\MipHelper.dll'
foreach ($f in $Folders) {
    if (-not (Test-Path $f)) { Write-Warning "Missing: $f" }
}
if ((Test-Path $destExe) -and (Test-Path $destDll)) {
    Write-Host "  MipHelper.exe : $destExe"
    Write-Host "  MipHelper.dll : $destDll"
} else {
    Write-Warning "  MipHelper publish payload missing in $((Join-Path $AppDataRoot 'MipHelper'))"
    Write-Warning "  Run: dotnet publish .\MipHelper\MipHelper.csproj -c Release -r win-x64 --self-contained false"
}

Write-Step "Done"
Write-Host "App data root  : $AppDataRoot"
Write-Host "Outputs        : $((Join-Path $AppDataRoot 'Outputs'))"
Write-Host "Temp           : $((Join-Path $AppDataRoot 'Temp'))"
Write-Host "Logs           : $((Join-Path $AppDataRoot 'Logs'))"
Write-Host "MIP helper     : $destExe"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "  python -m pip install -r requirements.txt"
Write-Host "  python -m uvicorn server:app"
