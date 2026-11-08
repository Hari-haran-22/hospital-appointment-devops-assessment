$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$secretDir = Join-Path $root 'secrets'
New-Item -ItemType Directory -Path $secretDir -Force | Out-Null

function New-Secret([string]$Name) {
    $path = Join-Path $secretDir $Name
    if (-not (Test-Path -LiteralPath $path)) {
        $bytes = [byte[]]::new(32)
        [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
        $value = [Convert]::ToHexString($bytes).ToLowerInvariant()
        [System.IO.File]::WriteAllText($path, $value, [System.Text.Encoding]::ASCII)
    }
}

@('db_admin_password', 'db_app_password', 'patient_one_token', 'patient_two_token', 'staff_token') |
    ForEach-Object { New-Secret $_ }

if (-not (Test-Path -LiteralPath (Join-Path $root '.env'))) {
    Copy-Item -LiteralPath (Join-Path $root '.env.example') -Destination (Join-Path $root '.env')
}
Write-Output 'Created missing local secrets and .env. Existing values were preserved.'
