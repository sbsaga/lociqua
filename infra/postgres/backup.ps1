param([Parameter(Mandatory = $true)] [string] $Destination)

$ErrorActionPreference = 'Stop'
$target = [System.IO.Path]::GetFullPath($Destination)
$directory = Split-Path -Parent $target
if (-not (Test-Path -LiteralPath $directory)) { New-Item -ItemType Directory -Path $directory | Out-Null }
if (Test-Path -LiteralPath $target) { throw "Refusing to overwrite existing backup: $target" }

$container = docker compose -f docker-compose.production.yml ps -q postgres
if (-not $container) { throw 'Postgres container is not running.' }
$remoteBackup = '/tmp/lociqua-backup.dump'
try {
  # Generate binary output inside the container; piping pg_dump through Windows
  # PowerShell can corrupt custom-format archives.
  docker compose -f docker-compose.production.yml exec -T postgres pg_dump -U lociqua -Fc -f $remoteBackup lociqua
  docker cp "${container}:$remoteBackup" $target
  if (-not (Test-Path -LiteralPath $target) -or (Get-Item -LiteralPath $target).Length -lt 1) { throw 'Backup file was not created.' }
  Write-Host "Created PostgreSQL backup: $target"
} finally {
  docker compose -f docker-compose.production.yml exec -T postgres rm -f $remoteBackup
}
