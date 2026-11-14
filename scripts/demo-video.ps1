param([switch]$Auto)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Check-Exit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE" }
}

function Chapter([string]$Title) {
    Write-Output "`n===== $Title ====="
    if (-not $Auto) { Read-Host 'Press Enter when your recording is ready' | Out-Null }
}

function Ready-Code {
    $code = curl.exe -s -k -o NUL -w '%{http_code}' https://localhost:8443/health/ready
    Check-Exit 'readiness request'
    return $code
}

Chapter '1  Repository and pipeline'
Write-Output 'Open the public repository and latest green Actions run in your browser:'
Write-Output 'https://github.com/Hari-haran-22/hospital-appointment-devops-assessment'
Write-Output 'https://github.com/Hari-haran-22/hospital-appointment-devops-assessment/actions'
Write-Output "Current commit: $(git rev-parse HEAD)"

Chapter '2  Running deployment and HTTPS health'
docker compose ps
Check-Exit 'compose status'
$live = Invoke-RestMethod -Uri 'https://localhost:8443/health/live' -SkipCertificateCheck
$ready = Invoke-RestMethod -Uri 'https://localhost:8443/health/ready' -SkipCertificateCheck
Write-Output "Liveness=$($live.status) version=$($live.version); readiness=$($ready.status)"
Invoke-RestMethod -Uri 'https://localhost:8443/v1/doctors' -SkipCertificateCheck |
    Format-Table id, name, specialty -AutoSize

Chapter '3  Simultaneous booking rule'
docker compose --profile test run --rm tests pytest -q -s `
    tests/test_api.py::test_concurrent_conflict_is_blocked_by_database
Check-Exit 'concurrent booking test'

Chapter '4  Structured application logs'
docker compose logs --tail=10 app
Check-Exit 'application logs'

Chapter '5  Failure detection and recovery'
$databaseStopped = $false
try {
    docker compose stop db
    Check-Exit 'stop database'
    $databaseStopped = $true
    Start-Sleep -Seconds 2
    $down = Ready-Code
    Write-Output "Database stopped: readiness HTTP $down"
    if ($down -eq '200') { throw 'Readiness did not detect the database outage' }
    if (-not $Auto) { Read-Host 'Press Enter to restart PostgreSQL' | Out-Null }
    docker compose start db
    Check-Exit 'start database'
    $databaseStopped = $false
    $recovered = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if ((Ready-Code) -eq '200') { $recovered = $true; break }
    }
    if (-not $recovered) { throw 'Readiness did not recover within 30 seconds' }
    Write-Output "Database restarted: readiness HTTP $(Ready-Code)"
}
finally {
    if ($databaseStopped) { docker compose start db | Out-Null }
}

Chapter '6  Backup and rollback evidence'
New-Item -ItemType Directory -Force (Join-Path $root 'backups') | Out-Null
$backup = 'backups/demo-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.dump'
docker compose exec -T db pg_dump -U postgres -d appointments -Fc -f /tmp/demo.dump
Check-Exit 'database backup'
docker compose cp db:/tmp/demo.dump $backup
Check-Exit 'copy backup to host'
docker compose exec -T db rm -f /tmp/demo.dump
Check-Exit 'remove temporary dump'
$checksum = (Get-FileHash $backup -Algorithm SHA256).Hash
Write-Output "Backup created: $backup"
Write-Output "SHA-256: $checksum"
Write-Output 'Restore and rollback procedure: docs/runbook.md'
Write-Output 'Previous restore drill: evidence/verification.md'
Write-Output "Final readiness HTTP $(Ready-Code)"
