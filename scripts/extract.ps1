# Extract PKG files using Il2CppDumper and StarResonanceTool

$ErrorActionPreference = "Stop"

# Import dotenv
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
. "$scriptDir\import-dotenv.ps1" -Path "$repoRoot\.env"

# Validate environment
if (-not $env:GAME_ASSEMBLY) {
    throw "GAME_ASSEMBLY not set in .env"
}
if (-not $env:OUTPUT_DIR) {
    throw "OUTPUT_DIR not set in .env"
}
if (-not $env:DUMMY_DLL) {
    throw "DUMMY_DLL not set in .env"
}
if (-not $env:GAME_DIR) {
    throw "GAME_DIR not set in .env"
}

# Check tools exist (using subdirectory structure)
$il2CppDumper = Join-Path $repoRoot "tools\Il2CppDumper\Il2CppDumper.exe"
$starResonanceTool = Join-Path $repoRoot "tools\StarResonanceTool\StarResonanceTool.exe"

if (-not (Test-Path $il2CppDumper)) {
    throw "Il2CppDumper.exe not found. Run setup first: scripts/setup.ps1"
}

if (-not (Test-Path $starResonanceTool)) {
    throw "StarResonanceTool.exe not found. Run setup first: scripts/setup.ps1"
}

# Check metadata exists
$metadataPath = Join-Path $env:OUTPUT_DIR "global-metadata.dat"
if (-not (Test-Path $metadataPath)) {
    throw "Metadata file not found: $metadataPath. Run dump first: scripts/dump.ps1"
}

# Step 1: Generate DummyDll
Write-Host "=== Step 1: Generating DummyDll ===" -ForegroundColor Cyan
Write-Host "Running Il2CppDumper..." -ForegroundColor Gray

$dummyArgs = "`"$env:GAME_ASSEMBLY`" `"$metadataPath`" `"$env:DUMMY_DLL`""
& $il2CppDumper $dummyArgs.Split(' ')

if ($LASTEXITCODE -ne 0) {
    throw "Il2CppDumper failed with exit code: $LASTEXITCODE"
}

if (-not (Test-Path $env:DUMMY_DLL)) {
    throw "DummyDll directory not created: $env:DUMMY_DLL"
}

$dllCount = (Get-ChildItem -Path $env:DUMMY_DLL -Filter "*.dll" -ErrorAction SilentlyContinue).Count
if ($dllCount -eq 0) {
    throw "No DLL files found in DummyDll directory: $env:DUMMY_DLL"
}

Write-Host "Generated $dllCount DLL files in: $env:DUMMY_DLL" -ForegroundColor Green

# Step 2: Extract PKG
Write-Host "`n=== Step 2: Extracting PKG files ===" -ForegroundColor Cyan

$pkgPath = Join-Path $env:GAME_DIR "meta.pkg"
if (-not (Test-Path $pkgPath)) {
    throw "PKG file not found: $pkgPath"
}

Write-Host "Running StarResonanceTool..." -ForegroundColor Gray
Write-Host "  PKG: $pkgPath"
Write-Host "  DummyDll: $env:DUMMY_DLL"
Write-Host "  Output: $env:OUTPUT_DIR"

& $starResonanceTool --pkg $pkgPath --dll $env:DUMMY_DLL --output $env:OUTPUT_DIR

if ($LASTEXITCODE -ne 0) {
    throw "StarResonanceTool failed with exit code: $LASTEXITCODE"
}

# Check Excels directory
$excelsDir = Join-Path $env:OUTPUT_DIR "Excels"
if (Test-Path $excelsDir) {
    $excelCount = (Get-ChildItem -Path $excelsDir -Filter "*.json" -Recurse -ErrorAction SilentlyContinue).Count
    Write-Host "`nExtraction complete:" -ForegroundColor Green
    Write-Host "  Excels directory: $excelsDir"
    Write-Host "  JSON files: $excelCount"
}
else {
    Write-Warning "Excels directory not found: $excelsDir"
    Write-Host "Extraction may have completed, but Excels directory was not created."
}

