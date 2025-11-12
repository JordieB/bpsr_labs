# Load .env file into current PowerShell session
# Supports multiline regex, trims quotes, supports ${VAR} → %VAR%, expands %VAR%

param(
    [string]$Path = ".\.env"
)

if (-not (Test-Path $Path)) {
    throw "Not found: $Path"
}

$raw = Get-Content -Raw $Path -Encoding UTF8 -ErrorAction Stop
$pattern = '(?m)^\s*([^#][^=]+?)\s*=\s*(.*)\s*$'

foreach ($m in [regex]::Matches($raw, $pattern)) {
    $name = $m.Groups[1].Value.Trim()
    $val = $m.Groups[2].Value.Trim().Trim("'`"")
    
    # Convert ${VAR} → %VAR%
    $val = $val -replace '\$\{([^}]+)\}', '%$1%'
    
    # Expand environment variables
    $val = [Environment]::ExpandEnvironmentVariables($val)
    
    Set-Item -Path Env:$name -Value $val
}

