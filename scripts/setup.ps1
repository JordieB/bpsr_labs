# Setup script: initialize submodules and extract vendor tools
# Uses git submodules for vendor repos, then extracts executables to tools/

$ErrorActionPreference = "Stop"

# Import dotenv
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
. "$scriptDir\import-dotenv.ps1" -Path "$repoRoot\.env"

# Create tools directory
$toolsDir = Join-Path $repoRoot "tools"
if (-not (Test-Path $toolsDir)) {
    New-Item -ItemType Directory -Path $toolsDir | Out-Null
    Write-Host "Created tools directory: $toolsDir"
}

# Function to check if .NET 8 SDK is available
function Test-DotNet8Sdk {
    try {
        $sdks = dotnet --list-sdks 2>&1
        if ($sdks -match '8\.') {
            return $true
        }
        # Also check default version
        $version = dotnet --version 2>&1
        if ($version -match '^8\.') {
            return $true
        }
        return $false
    }
    catch {
        return $false
    }
}

# Function to extract Il2CppDumper from submodule
function Extract-Il2CppDumper {
    Write-Host "`n=== Extracting Il2CppDumper ===" -ForegroundColor Cyan

    $vendorDir = Join-Path $repoRoot "vendor"
    $submoduleDir = Join-Path $vendorDir "Il2CppDumper"
    $outputDir = Join-Path $toolsDir "Il2CppDumper"

    if (-not (Test-Path $submoduleDir)) {
        throw "Il2CppDumper submodule not found. Run: git submodule update --init --recursive"
    }

    # Fetch latest release from GitHub API
    $apiUrl = "https://api.github.com/repos/Perfare/Il2CppDumper/releases/latest"
    Write-Host "Checking for latest release: $apiUrl" -ForegroundColor Gray
    
    $headers = @{}
    if ($env:GITHUB_TOKEN) {
        $headers["Authorization"] = "token $env:GITHUB_TOKEN"
    }

    try {
        $release = Invoke-RestMethod -Uri $apiUrl -Headers $headers -ErrorAction Stop
        
        # Find zip asset
        $asset = $release.assets | Where-Object { 
            $_.name -match '\.zip$' -and $_.name -notmatch '\.(pdb|symbols)' 
        } | Select-Object -First 1

        if ($asset) {
            Write-Host "Found release: $($release.tag_name)" -ForegroundColor Green
            Write-Host "Downloading: $($asset.name)" -ForegroundColor Gray

            $tempFile = Join-Path $env:TEMP "Il2CppDumper-$($asset.id).zip"
            Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tempFile -Headers $headers

            # Create output directory
            if (Test-Path $outputDir) {
                Remove-Item -Recurse -Force $outputDir
            }
            New-Item -ItemType Directory -Path $outputDir | Out-Null

            # Extract zip to temp location
            $tempExtract = Join-Path $env:TEMP "Il2CppDumper-extract"
            if (Test-Path $tempExtract) {
                Remove-Item -Recurse -Force $tempExtract
            }
            Expand-Archive -Path $tempFile -DestinationPath $tempExtract -Force

            # Find the directory containing the exe
            $exe = Get-ChildItem -Path $tempExtract -Recurse -Filter "Il2CppDumper.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
            
            if ($exe) {
                # Copy entire directory containing the exe
                $exeDir = $exe.DirectoryName
                Write-Host "Copying all files from: $exeDir" -ForegroundColor Gray
                
                # Copy all files from exe directory to output directory
                Get-ChildItem -Path $exeDir -File | ForEach-Object {
                    Copy-Item -Path $_.FullName -Destination $outputDir -Force
                }
                
                Write-Host "Extracted to: $outputDir" -ForegroundColor Green
                Write-Host "Release tag: $($release.tag_name)" -ForegroundColor Cyan
                
                # Get version info from submodule
                Push-Location $submoduleDir
                try {
                    $sha = (git rev-parse --short HEAD).Trim()
                    Write-Host "Submodule SHA: $sha" -ForegroundColor Cyan
                }
                catch {
                    Write-Warning "Could not get SHA: $_"
                }
                finally {
                    Pop-Location
                }
                
                Remove-Item -Recurse -Force $tempExtract
                Remove-Item -Path $tempFile -ErrorAction SilentlyContinue
                return
            }
            else {
                Remove-Item -Recurse -Force $tempExtract
                Remove-Item -Path $tempFile -ErrorAction SilentlyContinue
                throw "No Il2CppDumper.exe found in release zip"
            }
        }
        else {
            throw "No zip asset found in latest release"
        }
    }
    catch {
        Write-Warning "Failed to fetch release: $_"
        throw "Failed to extract Il2CppDumper: $_"
    }
}

# Function to build and extract StarResonanceTool from submodule
function Build-StarResonanceTool {
    Write-Host "`n=== Building StarResonanceTool ===" -ForegroundColor Cyan

    $vendorDir = Join-Path $repoRoot "vendor"
    $submoduleDir = Join-Path $vendorDir "StarResonanceTool"
    $outputDir = Join-Path $toolsDir "StarResonanceTool"

    if (-not (Test-Path $submoduleDir)) {
        throw "StarResonanceTool submodule not found. Run: git submodule update --init --recursive"
    }

    # Check for existing exe in submodule (from releases)
    $exe = Get-ChildItem -Path $submoduleDir -Recurse -Filter "StarResonanceTool.exe" -ErrorAction SilentlyContinue | 
        Where-Object { $_.DirectoryName -notmatch 'bin|obj' } | Select-Object -First 1

    if ($exe) {
        Write-Host "Found existing executable in submodule" -ForegroundColor Green
        
        if (Test-Path $outputDir) {
            Remove-Item -Recurse -Force $outputDir
        }
        New-Item -ItemType Directory -Path $outputDir | Out-Null
        
        Copy-Item -Path $exe.FullName -Destination $outputDir -Force
        Write-Host "Copied to: $outputDir" -ForegroundColor Green
        return
    }

    # Build from source
    if (-not (Test-DotNet8Sdk)) {
        throw ".NET 8 SDK is required to build StarResonanceTool. Install .NET 8 SDK: https://dotnet.microsoft.com/download/dotnet/8.0"
    }

    $csproj = Get-ChildItem -Path $submoduleDir -Recurse -Filter "StarResonanceTool.csproj" | Select-Object -First 1
    if (-not $csproj) {
        throw "StarResonanceTool.csproj not found in submodule"
    }

    Write-Host "Building from source (requires .NET 8 SDK)..." -ForegroundColor Yellow
    Push-Location $csproj.DirectoryName
    try {
        & dotnet build -c Release -p:Nullable=disable -p:TreatWarningsAsErrors=false 2>&1 | Out-String | Write-Host
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Build failed (exit code: $LASTEXITCODE)"
            throw "Build failed for StarResonanceTool"
        }
        
        # Find built exe and all dependencies
        $buildOutput = Get-ChildItem -Path (Join-Path $csproj.DirectoryName "bin\Release\net*") -Recurse -ErrorAction SilentlyContinue | 
            Where-Object { $_.PSIsContainer -eq $false } | 
            Where-Object { $_.Extension -match '\.(exe|dll|json|config)$' }
        
        if ($buildOutput) {
            if (Test-Path $outputDir) {
                Remove-Item -Recurse -Force $outputDir
            }
            New-Item -ItemType Directory -Path $outputDir | Out-Null
            
            # Copy all build outputs
            foreach ($file in $buildOutput) {
                Copy-Item -Path $file.FullName -Destination $outputDir -Force
            }
            
            Write-Host "Built and copied to: $outputDir" -ForegroundColor Green
        }
        else {
            throw "Build succeeded but no output files found"
        }
    }
    finally {
        Pop-Location
    }

    # Get SHA for provenance
    Push-Location $submoduleDir
    try {
        $sha = (git rev-parse --short HEAD).Trim()
        Write-Host "Submodule SHA: $sha" -ForegroundColor Cyan
    }
    catch {
        Write-Warning "Could not get SHA: $_"
    }
    finally {
        Pop-Location
    }
}

# Initialize and update submodules
Write-Host "=== Initializing git submodules ===" -ForegroundColor Cyan
Push-Location $repoRoot
try {
    & git submodule update --init --recursive
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to initialize submodules"
    }
    Write-Host "Submodules initialized successfully" -ForegroundColor Green
}
finally {
    Pop-Location
}

# Check .NET 8 SDK before proceeding (needed for StarResonanceTool)
if (-not (Test-DotNet8Sdk)) {
    Write-Host "`n.NET 8 SDK is required but not found." -ForegroundColor Red
    Write-Host "Installed SDKs:" -ForegroundColor Yellow
    dotnet --list-sdks | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    Write-Host "`nPlease install .NET 8 SDK from: https://dotnet.microsoft.com/download/dotnet/8.0" -ForegroundColor Yellow
    Write-Host "After installation, run this script again.`n" -ForegroundColor Yellow
    throw ".NET 8 SDK is required"
}

# Extract Il2CppDumper
try {
    Extract-Il2CppDumper
}
catch {
    Write-Error "Failed to extract Il2CppDumper: $_"
    throw
}

# Build StarResonanceTool
try {
    Build-StarResonanceTool
}
catch {
    Write-Error "Failed to build StarResonanceTool: $_"
    throw
}

# Build projects
Write-Host "`n=== Building projects ===" -ForegroundColor Cyan

Push-Location $repoRoot
try {
    Write-Host "Building Il2CppMetadataDump..."
    & dotnet build src/Il2CppMetadataDump/Il2CppMetadataDump.csproj -c Release
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Build failed for Il2CppMetadataDump (exit code: $LASTEXITCODE)"
        Write-Error "Ensure .NET 8 SDK is installed: https://dotnet.microsoft.com/download/dotnet/8.0"
        throw "Build failed for Il2CppMetadataDump"
    }

    Write-Host "Building Orchestrator.Cli..."
    & dotnet build src/Orchestrator.Cli/Orchestrator.Cli.csproj -c Release
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Build failed for Orchestrator.Cli (exit code: $LASTEXITCODE)"
        Write-Error "Ensure .NET 8 SDK is installed: https://dotnet.microsoft.com/download/dotnet/8.0"
        throw "Build failed for Orchestrator.Cli"
    }

    Write-Host "`n=== Setup Complete ===" -ForegroundColor Green
    Write-Host "Tools available in: $toolsDir"
    Write-Host "Projects built successfully"
}
finally {
    Pop-Location
}
