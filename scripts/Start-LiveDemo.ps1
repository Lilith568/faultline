param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Install the project first using the three setup commands in docs/LIVE_DEMO.md.'
}

# Changes stay within this PowerShell process and its server child.
$names = @('MODEL_API_KEY', 'FAULTLINE_MODEL_BACKEND', 'META_BASE_URL', 'META_MODEL', 'FAULTLINE_ALLOW_REMOTE')
$previous = @{}
foreach ($name in $names) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

Push-Location -LiteralPath $projectRoot
try {
    $env:FAULTLINE_MODEL_BACKEND = 'meta'
    $env:META_BASE_URL = 'https://api.meta.ai/v1'
    $env:META_MODEL = 'muse-spark-1.3'
    $env:FAULTLINE_ALLOW_REMOTE = '0'

    & $python -c "from faultline.config import get_settings; raise SystemExit(0 if get_settings().api_key else 1)"
    if ($LASTEXITCODE -ne 0) {
        $secureKey = Read-Host 'Meta Model API key (hidden input; not saved)' -AsSecureString
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        try {
            $env:MODEL_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        }
        finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
            $secureKey.Dispose()
        }
    }
    if (-not $env:MODEL_API_KEY) {
        # A configured local .env is loaded directly by the Python server.
        & $python -c "from faultline.config import get_settings; raise SystemExit(0 if get_settings().api_key else 1)"
        if ($LASTEXITCODE -ne 0) { throw 'No Meta API key was configured.' }
    }

    Write-Host "Open http://127.0.0.1:$Port and choose Live Muse API."
    Write-Host 'Real calls use your Meta credits. Press Ctrl+C to stop the server.'
    & $python -m faultline serve --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'The Faultline server exited with an error.' }
}
finally {
    foreach ($name in $names) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
    Pop-Location
}
