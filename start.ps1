$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$frontendPath = Join-Path $projectRoot 'frontend'
if (-not (Test-Path -LiteralPath (Join-Path $backendPath 'vendor/sqlalchemy/__init__.py')) -or -not (Test-Path -LiteralPath (Join-Path $backendPath 'vendor/pypdf/__init__.py'))) {
    python -m pip install --target (Join-Path $backendPath 'vendor') -r (Join-Path $backendPath 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendPath 'node_modules/next/package.json'))) {
    npm.cmd ci --prefix $frontendPath
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
}
function Test-Service([string]$url) {
    try { $null = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2; return $true }
    catch { return $false }
}
function Assert-PortAvailable([int]$port, [string]$serviceName) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw "$serviceName is unhealthy and port $port is occupied by PID $($listener.OwningProcess). Inspect its error log and restart that identified service. No unknown process was stopped." }
}
function Wait-Service([string]$url, [string]$serviceName) {
    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        if (Test-Service $url) { return }
        Start-Sleep -Milliseconds 300
    }
    throw "$serviceName did not become reachable. Inspect its error log, then retry start.ps1."
}
if (-not (Test-Service 'http://127.0.0.1:8000/api/health')) {
    Assert-PortAvailable 8000 'Backend'
    Start-Process -FilePath 'python' -ArgumentList 'run.py' -WorkingDirectory $backendPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot 'backend.log') -RedirectStandardError (Join-Path $projectRoot 'backend-error.log')
}
if (-not (Test-Service 'http://127.0.0.1:3000/dashboard')) {
    Assert-PortAvailable 3000 'Frontend'
    Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev' -WorkingDirectory $frontendPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot 'frontend.log') -RedirectStandardError (Join-Path $projectRoot 'frontend-error.log')
}
Wait-Service 'http://127.0.0.1:8000/api/health' 'Backend'
Wait-Service 'http://127.0.0.1:3000/dashboard' 'Frontend'
Write-Host 'ClaimGuard AI: http://127.0.0.1:3000/dashboard'
Write-Host 'API: http://127.0.0.1:8000/docs'
Write-Host 'Logs: backend.log / backend-error.log / frontend.log / frontend-error.log'
