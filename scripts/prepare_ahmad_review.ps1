# Generates LOCAL ONLY .env.ahmad.local to isolate Ahmad's review from existing MedFlux.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot=Split-Path -Parent $PSScriptRoot
$envPath=Join-Path $repoRoot '.env.ahmad.local'
if(Test-Path -LiteralPath $envPath){
 Write-Output 'Existing .env.ahmad.local kept unchanged. Review it before use.'
 exit 0
}
$pg=[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
$key=[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
[IO.File]::WriteAllText($envPath, "AHMAD_PG_PASSWORD=$pg`nAHMAD_APP_SECRET_KEY=$key`n")
Write-Output 'Unique random credentials generated locally in .env.ahmad.local.'
Write-Output 'KEEP THIS FILE PRIVATE. Never push it to GitHub or share with Ahmad.'
Write-Output 'Separate preview binds only to localhost:13000 and localhost:18000.'
Write-Output 'Once the isolated Docker pilot is validated: docker compose --env-file .env.ahmad.local -f docker-compose.ahmad-review.yml up --build -d'
