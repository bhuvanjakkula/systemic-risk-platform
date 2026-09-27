$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonExe = Join-Path $PSScriptRoot '.venv312\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Python environment missing. Follow README setup instructions.' }
$url = 'http://127.0.0.1:8010'
try {
    $health = Invoke-RestMethod "$url/health" -TimeoutSec 2
    if (-not $health.ok) { throw 'Unexpected service on port 8010' }
} catch {
    Start-Process -FilePath $pythonExe -ArgumentList '-m','uvicorn','src.api.app:app','--host','127.0.0.1','--port','8010' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'server.log') -RedirectStandardError (Join-Path $PSScriptRoot 'server-error.log')
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        try { $health = Invoke-RestMethod "$url/health" -TimeoutSec 1; if ($health.ok) { $ready = $true; break } } catch {}
    }
    if (-not $ready) { throw 'Server did not start. See server-error.log.' }
}
Start-Process $url
