param(
  [Parameter(Mandatory=$true)][string]$PostgresBin,
  [int]$Port = 55440,
  [Parameter(Mandatory=$true)][SecureString]$AdminPassword,
  [string]$InstanceDir = ""
)
# Ahmed ONLY: initializes a NEW user-owned cluster; never discovers or changes existing clusters.
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $InstanceDir) { $InstanceDir = Join-Path $root ".ahmed-local-pg" }
$InstanceDir = [IO.Path]::GetFullPath($InstanceDir)
$initdb = Join-Path $PostgresBin "initdb.exe"
$pgctl = Join-Path $PostgresBin "pg_ctl.exe"
$ready = Join-Path $PostgresBin "pg_isready.exe"
foreach ($p in @($initdb,$pgctl,$ready)) { if (-not (Test-Path -LiteralPath $p)) { throw "Missing PostgreSQL executable: $p" } }
if ($Port -lt 1024 -or $Port -gt 65535) { throw "Choose an unprivileged valid TCP port" }
if (Test-Path -LiteralPath $InstanceDir) { throw "Refusing existing directory. Use a NEW empty location: $InstanceDir" }
$tcp = [Net.Sockets.TcpClient]::new()
try {
  $task = $tcp.ConnectAsync("127.0.0.1",$Port)
  if ($task.Wait(1000) -and $tcp.Connected) { throw "Port $Port is occupied; choose another" }
} finally { $tcp.Dispose() }
New-Item -ItemType Directory -Path $InstanceDir -ErrorAction Stop | Out-Null
$data = Join-Path $InstanceDir "data"
$log = Join-Path $InstanceDir "postgres.log"
$pwfile = Join-Path $InstanceDir "bootstrap-password.txt"
try {
  # Generate per-install secret; store in owner-readable directory. Remove after role setup.
  $password = [System.Net.NetworkCredential]::new("",$AdminPassword).Password
  if ($password.Length -lt 16) { throw "Use a password of at least 16 characters" }
  [IO.File]::WriteAllText($pwfile,$password,[Text.Encoding]::ASCII)
  & $initdb -D $data -U medflux_local -A scram-sha-256 --pwfile=$pwfile --encoding=UTF8 --no-instructions
  if ($LASTEXITCODE -ne 0) { throw "initdb failed; inspect ONLY this newly created directory" }
  Remove-Item -LiteralPath $pwfile -Force
  Add-Content -LiteralPath (Join-Path $data "postgresql.conf") -Value "`nlisten_addresses = '127.0.0.1'`nport = $Port`n"
  & $pgctl -D $data -l $log -o "-h 127.0.0.1 -p $Port" start -w
  if ($LASTEXITCODE -ne 0) { throw "New cluster did not start; see $log" }
  & $ready -h 127.0.0.1 -p $Port
  if ($LASTEXITCODE -ne 0) { throw "PostgreSQL not ready" }
  Write-Host "NEW isolated local PostgreSQL cluster ready on 127.0.0.1:$Port"
  Write-Warning "Provisioning only: DB creation and .env setup are separate. Keep the password you supplied securely; this script does not store it after initdb."
} catch {
  if (Test-Path $pwfile) { Remove-Item $pwfile -Force }
  throw
}
