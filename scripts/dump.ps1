# Dump IL2CPP metadata from running game process

$ErrorActionPreference = "Stop"

# Import dotenv
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
. "$scriptDir\import-dotenv.ps1" -Path "$repoRoot\.env"

# Validate environment
if (-not $env:OUTPUT_DIR) {
    throw "OUTPUT_DIR not set in .env"
}

# Build path to dumper exe
$dumperExe = Join-Path $repoRoot "src\Il2CppMetadataDump\bin\Release\net8.0\Il2CppMetadataDump.exe"

if (-not (Test-Path $dumperExe)) {
    Write-Host "Il2CppMetadataDump.exe not found. Building..." -ForegroundColor Yellow
    Push-Location $repoRoot
    try {
        & dotnet build src/Il2CppMetadataDump/Il2CppMetadataDump.csproj -c Release
        if ($LASTEXITCODE -ne 0) {
            throw "Build failed"
        }
    }
    finally {
        Pop-Location
    }
}

# Run dumper
Write-Host "Running IL2CPP metadata dumper..." -ForegroundColor Cyan
Write-Host "Auto-detecting process with GameAssembly.dll..." -ForegroundColor Gray

$outputPath = Join-Path $env:OUTPUT_DIR "global-metadata.dat"
& $dumperExe -- $outputPath

if ($LASTEXITCODE -ne 0) {
    throw "Dump failed with exit code: $LASTEXITCODE"
}

# Print file info
if (Test-Path $outputPath) {
    $fileInfo = Get-Item $outputPath
    $sizeMB = [math]::Round($fileInfo.Length / 1MB, 2)
    Write-Host "`nDump complete:" -ForegroundColor Green
    Write-Host "  Path: $outputPath"
    Write-Host "  Size: $sizeMB MB"
    
    # Try to read version from output (if available)
    Write-Host "`nMetadata version should be visible in the output above."
}
else {
    throw "Dump file not found: $outputPath"
}

