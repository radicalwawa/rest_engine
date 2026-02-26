$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot | Out-Null
try {
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        & py -X faulthandler python/validate.py
        exit $LASTEXITCODE
    }
    $versionFile = Join-Path $repoRoot ".python-version"
    if (-not (Test-Path $versionFile)) {
        Write-Error "Python not found. Install py launcher or add Python to PATH."
        exit 1
    }
    $ver = (Get-Content $versionFile -Raw).Trim()
    $majorMinor = $ver -replace '^(\d+\.\d+).*', '$1'
    $folder = "Python$($majorMinor -replace '\.', '')"
    $pythonPath = Join-Path $env:LOCALAPPDATA "Programs\Python\$folder\python.exe"
    if (Test-Path $pythonPath) {
        & $pythonPath -X faulthandler python/validate.py
        exit $LASTEXITCODE
    }
    Write-Error "Python not found. Install py launcher or Python for version in .python-version ($ver)."
    exit 1
} finally {
    Pop-Location | Out-Null
}
