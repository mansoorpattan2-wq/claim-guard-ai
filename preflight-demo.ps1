param(
    [string]$FrontendUrl = 'http://127.0.0.1:3000',
    [string]$BackendUrl = 'http://127.0.0.1:8000'
)
$ErrorActionPreference = 'Stop'
$failures = [System.Collections.Generic.List[string]]::new()
try {
    $frontendResponse = Invoke-WebRequest -UseBasicParsing -Uri "$FrontendUrl/dashboard" -TimeoutSec 10
    if ($frontendResponse.StatusCode -ne 200) { $failures.Add('Frontend did not return HTTP 200.') }
} catch { $failures.Add('Frontend unreachable: start.ps1; inspect frontend-error.log.') }
try {
    $null = Invoke-RestMethod -Uri "$BackendUrl/ready" -TimeoutSec 7
    $preflightSession = Invoke-RestMethod -Method Post -Uri "$BackendUrl/api/session" -ContentType 'application/json' -Body '{"role":"Claims Executive"}' -TimeoutSec 5
    $headers = @{ Authorization = 'Bearer ' + $preflightSession.token }
    $check = Invoke-RestMethod -Uri "$BackendUrl/api/demo/preflight" -Headers $headers -TimeoutSec 10
    foreach ($failure in $check.failures) { $failures.Add($failure) }
    Write-Host ('Persistence: ' + $check.database + ' / schema v' + $check.schema_version)
    Write-Host ('Visible claims: ' + $check.visible_claims)
    Write-Host $check.reset_check
} catch { $failures.Add('Backend/database preflight unavailable: start.ps1; inspect backend-error.log. No reset was performed.') }
if ($failures.Count -gt 0) {
    Write-Host 'DEMO NOT READY' -ForegroundColor Red
    foreach ($failure in $failures) { Write-Host ('- ' + $failure) }
    exit 1
}
Write-Host 'DEMO READY' -ForegroundColor Green
Write-Host "$FrontendUrl/dashboard"
# Read-only with respect to persistent demo data. Only an ephemeral session token is created.
