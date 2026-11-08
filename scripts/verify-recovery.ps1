$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Check-Exit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE" }
}

function Health-Code {
    $code = curl.exe -s -k -o NUL -w '%{http_code}' https://localhost:8443/health/ready
    Check-Exit 'health request'
    return $code
}

$token = [System.IO.File]::ReadAllText((Join-Path $root 'secrets/patient_two_token')).Trim()
$day = (Get-Date).AddDays(1)
while ($day.DayOfWeek -in @('Saturday', 'Sunday')) { $day = $day.AddDays(1) }
$start = '{0}T11:00:00+05:30' -f $day.ToString('yyyy-MM-dd')
$headers = @{ Authorization = "Bearer $token" }
$body = @{ patient_id = 'P002'; doctor_id = 'D002'; start_at = $start } | ConvertTo-Json

$created = Invoke-RestMethod -Uri 'https://localhost:8443/v1/appointments' -Method Post `
    -SkipCertificateCheck -Headers $headers -ContentType 'application/json' -Body $body
Write-Output "CREATE status=$($created.status) id=$($created.id)"

New-Item -ItemType Directory -Force (Join-Path $root 'backups') | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = "backups/appointments-$stamp.dump"
docker compose exec -T db pg_dump -U postgres -d appointments -Fc -f /tmp/appointments.dump
Check-Exit 'pg_dump'
docker compose cp db:/tmp/appointments.dump $backup
Check-Exit 'copy backup'
docker compose exec -T db rm -f /tmp/appointments.dump
Check-Exit 'remove temporary dump'
$hash = (Get-FileHash $backup -Algorithm SHA256).Hash
Write-Output "BACKUP file=$backup sha256=$hash"

$cancelled = Invoke-RestMethod -Uri "https://localhost:8443/v1/appointments/$($created.id)/cancel" `
    -Method Post -SkipCertificateCheck -Headers $headers
Write-Output "MUTATION status=$($cancelled.status)"

docker compose stop app proxy | Out-Null
Check-Exit 'stop app and proxy'
docker compose cp $backup db:/tmp/restore.dump
Check-Exit 'copy restore dump'
docker compose exec -T db pg_restore -U postgres -d appointments --clean --if-exists /tmp/restore.dump
Check-Exit 'pg_restore'
docker compose exec -T db rm -f /tmp/restore.dump
Check-Exit 'remove restore dump'
docker compose start app proxy | Out-Null
Check-Exit 'restart app and proxy'
Start-Sleep -Seconds 3
$restored = Invoke-RestMethod -Uri "https://localhost:8443/v1/appointments/$($created.id)" `
    -SkipCertificateCheck -Headers $headers
Write-Output "RESTORE status=$($restored.status) health=$(Health-Code)"
if ($restored.status -ne 'confirmed') { throw 'Restored booking is not confirmed' }

docker compose stop db | Out-Null
Check-Exit 'stop database'
Start-Sleep -Seconds 2
$downCode = Health-Code
Write-Output "FAILURE readiness_http=$downCode"
if ($downCode -eq '200') { throw 'Readiness failed to detect database outage' }
docker compose start db | Out-Null
Check-Exit 'restart database'
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if ((Health-Code) -eq '200') { $ready = $true; break }
}
if (-not $ready) { throw 'Readiness did not recover within 30 seconds' }
Write-Output "RECOVERY readiness_http=$(Health-Code)"
docker compose ps
