param([string]$BackendUrl = 'http://127.0.0.1:8000')
$ErrorActionPreference = 'Stop'
$apiReady = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $null = Invoke-RestMethod -Uri "$BackendUrl/ready" -TimeoutSec 7
        $apiReady = $true
        break
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $apiReady) { throw 'Backend is unavailable. Run start.ps1, then retry the reset.' }
$sessionBody = @{ role = 'Claims Executive' } | ConvertTo-Json
$demoSession = Invoke-RestMethod -Method Post -Uri "$BackendUrl/api/session" -ContentType 'application/json' -Body $sessionBody
$headers = @{ Authorization = "Bearer $($demoSession.token)" }
if ($env:DEMO_RESET_KEY) { $headers['X-Demo-Reset-Key'] = $env:DEMO_RESET_KEY }
$result = Invoke-RestMethod -Method Post -Uri "$BackendUrl/api/demo/reset-all" -Headers $headers -ContentType 'application/json' -Body '{}'
Write-Host $result.message
Write-Host 'Judge scenarios: CG001 READY / CG021 63% / CG030 review / CG048 investigation lead.'
