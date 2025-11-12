# Port sr-extract-orchestrator files to another repository
# Usage (from source repo): .\scripts\port-to-repo.ps1 -DestinationPath "C:\path\to\target\repo"
# Usage (from destination repo): .\scripts\port-to-repo.ps1 -SourcePath "C:\path\to\source\repo" -DestinationPath "."

param(
    [Parameter(Mandatory=$false)]
    [string]$SourcePath,
    [Parameter(Mandatory=$true)]
    [string]$DestinationPath
)

$ErrorActionPreference = "Stop"

# Get the source repository root
if ($SourcePath) {
    # If SourcePath is provided, use it (running from destination repo)
    $sourceRepoRoot = (Resolve-Path $SourcePath).Path
} else {
    # Otherwise, assume script is in source repo (original behavior)
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $sourceRepoRoot = Split-Path -Parent $scriptDir
    $sourceRepoRoot = (Resolve-Path $sourceRepoRoot).Path
}

Write-Host "Source repository: $sourceRepoRoot" -ForegroundColor Cyan
Write-Host "Destination repository: $DestinationPath" -ForegroundColor Cyan
Write-Host ""

# Validate destination exists
if (-not (Test-Path $DestinationPath)) {
    throw "Destination path does not exist: $DestinationPath"
}

$DestinationPath = (Resolve-Path $DestinationPath).Path

# Define files to copy with full source paths and relative destination paths
$filesToCopy = @(
    # Source code - Il2CppMetadataDump
    @{
        Source = Join-Path $sourceRepoRoot "src\Il2CppMetadataDump\Il2CppMetadataDump.csproj"
        Destination = "src\Il2CppMetadataDump\Il2CppMetadataDump.csproj"
        Description = "Il2CppMetadataDump project file"
    },
    @{
        Source = Join-Path $sourceRepoRoot "src\Il2CppMetadataDump\Program.cs"
        Destination = "src\Il2CppMetadataDump\Program.cs"
        Description = "Il2CppMetadataDump source code"
    },
    # Source code - Orchestrator.Cli
    @{
        Source = Join-Path $sourceRepoRoot "src\Orchestrator.Cli\Orchestrator.Cli.csproj"
        Destination = "src\Orchestrator.Cli\Orchestrator.Cli.csproj"
        Description = "Orchestrator.Cli project file"
    },
    @{
        Source = Join-Path $sourceRepoRoot "src\Orchestrator.Cli\Program.cs"
        Destination = "src\Orchestrator.Cli\Program.cs"
        Description = "Orchestrator.Cli source code"
    },
    # PowerShell scripts
    @{
        Source = Join-Path $sourceRepoRoot "scripts\dump.ps1"
        Destination = "scripts\dump.ps1"
        Description = "Metadata dump script"
    },
    @{
        Source = Join-Path $sourceRepoRoot "scripts\extract.ps1"
        Destination = "scripts\extract.ps1"
        Description = "PKG extraction script"
    },
    @{
        Source = Join-Path $sourceRepoRoot "scripts\import-dotenv.ps1"
        Destination = "scripts\import-dotenv.ps1"
        Description = "Environment variable loader script"
    },
    @{
        Source = Join-Path $sourceRepoRoot "scripts\setup.ps1"
        Destination = "scripts\setup.ps1"
        Description = "Setup script for vendor tools"
    },
    # Configuration files
    @{
        Source = Join-Path $sourceRepoRoot ".env.example"
        Destination = ".env.example"
        Description = "Environment configuration template"
    },
    @{
        Source = Join-Path $sourceRepoRoot "Directory.Build.props"
        Destination = "Directory.Build.props"
        Description = "Build configuration (check if target repo has one)"
    }
)

# Optional files (user can choose)
$optionalFiles = @(
    @{
        Source = Join-Path $sourceRepoRoot "sr-extract-orchestrator.sln"
        Destination = "sr-extract-orchestrator.sln"
        Description = "Solution file (only if you want a separate solution)"
    },
    @{
        Source = Join-Path $sourceRepoRoot ".gitmodules"
        Destination = ".gitmodules"
        Description = "Git submodules config (only if using submodules)"
    }
)

Write-Host "=== Files to Copy ===" -ForegroundColor Yellow
Write-Host ""

$missingFiles = @()
foreach ($file in $filesToCopy) {
    if (Test-Path $file.Source) {
        Write-Host "[✓] $($file.Description)" -ForegroundColor Green
        Write-Host "    Source: $($file.Source)" -ForegroundColor Gray
        Write-Host "    Dest:   $($file.Destination)" -ForegroundColor Gray
    } else {
        Write-Host "[✗] MISSING: $($file.Description)" -ForegroundColor Red
        Write-Host "    Source: $($file.Source)" -ForegroundColor Gray
        $missingFiles += $file
    }
    Write-Host ""
}

if ($missingFiles.Count -gt 0) {
    Write-Host "Warning: $($missingFiles.Count) file(s) are missing. Continue anyway? (y/N)" -ForegroundColor Yellow
    $response = Read-Host
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Host "Aborted." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "=== Optional Files ===" -ForegroundColor Yellow
Write-Host ""
foreach ($file in $optionalFiles) {
    if (Test-Path $file.Source) {
        Write-Host "[?] $($file.Description)" -ForegroundColor Cyan
        Write-Host "    Source: $($file.Source)" -ForegroundColor Gray
        Write-Host "    Dest:   $($file.Destination)" -ForegroundColor Gray
        $copy = Read-Host "    Copy this file? (y/N)"
        if ($copy -eq 'y' -or $copy -eq 'Y') {
            $filesToCopy += $file
        }
    }
}

Write-Host ""
Write-Host "=== Copying Files ===" -ForegroundColor Yellow
Write-Host ""

$copiedCount = 0
$skippedCount = 0
$errorCount = 0

foreach ($file in $filesToCopy) {
    if (-not (Test-Path $file.Source)) {
        Write-Host "[SKIP] $($file.Description) - source not found" -ForegroundColor Yellow
        $skippedCount++
        continue
    }

    $destFullPath = Join-Path $DestinationPath $file.Destination
    $destDir = Split-Path -Parent $destFullPath

    try {
        # Create destination directory if it doesn't exist
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            Write-Host "[DIR]  Created: $destDir" -ForegroundColor Cyan
        }

        # Check if destination file exists
        if (Test-Path $destFullPath) {
            Write-Host "[WARN] File exists: $($file.Destination)" -ForegroundColor Yellow
            $overwrite = Read-Host "         Overwrite? (y/N)"
            if ($overwrite -ne 'y' -and $overwrite -ne 'Y') {
                Write-Host "[SKIP] $($file.Description)" -ForegroundColor Yellow
                $skippedCount++
                continue
            }
        }

        # Copy file
        Copy-Item -Path $file.Source -Destination $destFullPath -Force
        Write-Host "[OK]   $($file.Description)" -ForegroundColor Green
        Write-Host "       $($file.Destination)" -ForegroundColor Gray
        $copiedCount++
    }
    catch {
        Write-Host "[ERROR] Failed to copy: $($file.Description)" -ForegroundColor Red
        Write-Host "        $($_.Exception.Message)" -ForegroundColor Red
        $errorCount++
    }
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Yellow
Write-Host "Copied:   $copiedCount" -ForegroundColor Green
Write-Host "Skipped:  $skippedCount" -ForegroundColor Yellow
Write-Host "Errors:   $errorCount" -ForegroundColor $(if ($errorCount -gt 0) { "Red" } else { "Green" })
Write-Host ""

# Generate a summary document
$summaryPath = Join-Path $DestinationPath "PORTING_NOTES.md"
$summaryContent = @"
# Porting Notes - sr-extract-orchestrator

Files ported from: $sourceRepoRoot
Ported on: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## Files Copied

$($filesToCopy | ForEach-Object { "- $($_.Destination) - $($_.Description)" } | Out-String)

## Next Steps

1. **Add NuGet Package**: Ensure `DotNetEnv` version 3.1.1 is referenced in both projects
   - `src/Il2CppMetadataDump/Il2CppMetadataDump.csproj`
   - `src/Orchestrator.Cli/Orchestrator.Cli.csproj`

2. **Update .gitignore**: Add these patterns if not present:
   \`\`\`
   tools/
   output/
   DummyDll/
   \`\`\`

3. **Handle Directory.Build.props**: 
   - If target repo already has one, merge the settings
   - Ensure `TargetFramework` is `net8.0` and `LangVersion` is `latest`

4. **Vendor Tools**: The `setup.ps1` script handles fetching Il2CppDumper and StarResonanceTool.
   - If target repo uses different dependency management, adapt accordingly
   - Or keep the script as-is if it fits your workflow

5. **Documentation**: Extract relevant sections from the original README.md:
   - Features section
   - Usage examples
   - Current Status
   - Future Ideas/Roadmap (if applicable)

6. **Solution File**: 
   - If you copied `sr-extract-orchestrator.sln`, add the projects to your main solution
   - Or integrate the projects into an existing solution

7. **Environment Variables**: Users will need to create `.env` from `.env.example`:
   - GAME_DIR
   - GAME_ASSEMBLY
   - OUTPUT_DIR
   - DUMMY_DLL

## Dependencies

- .NET 8 SDK
- PowerShell 5.1+ or PowerShell 7+
- Git (for setup script to fetch vendor tools)

## External Tools (handled by setup.ps1)

- Il2CppDumper: https://github.com/Perfare/Il2CppDumper
- StarResonanceTool: https://github.com/PotRooms/StarResonanceTool
"@

try {
    Set-Content -Path $summaryPath -Value $summaryContent -Encoding UTF8
    Write-Host "[INFO] Porting notes saved to: PORTING_NOTES.md" -ForegroundColor Cyan
}
catch {
    Write-Host "[WARN] Could not create PORTING_NOTES.md: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Porting complete!" -ForegroundColor Green
Write-Host "Review PORTING_NOTES.md in the destination repository for next steps." -ForegroundColor Cyan

