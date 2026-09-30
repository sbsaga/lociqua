param(
  [Parameter(Mandatory = $true)] [string] $Backup,
  [string] $Database = 'lociqua_restore_test',
  [switch] $AllowActiveDatabaseOverwrite
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Backup)) { throw "Backup not found: $Backup" }
if ($Database -notmatch '^[a-z][a-z0-9_]{0,62}$') { throw 'Database name must contain lowercase letters, digits, and underscores only.' }
if ($Database -eq 'lociqua' -and -not $AllowActiveDatabaseOverwrite) {
  throw 'Refusing to overwrite the active lociqua database. Restore to a disposable database, or explicitly pass -AllowActiveDatabaseOverwrite.'
}

$container = docker compose -f docker-compose.production.yml ps -q postgres
if (-not $container) { throw 'Postgres container is not running.' }
$remoteBackup = '/tmp/lociqua-restore.dump'
docker cp $Backup "${container}:$remoteBackup"
try {
  if ($Database -ne 'lociqua') {
    docker compose -f docker-compose.production.yml exec -T postgres dropdb -U lociqua --if-exists $Database
    docker compose -f docker-compose.production.yml exec -T postgres createdb -U lociqua $Database
  }
  docker compose -f docker-compose.production.yml exec -T postgres pg_restore -U lociqua -d $Database --clean --if-exists --no-owner $remoteBackup
  Write-Host "Restored backup into database: $Database"
} finally {
  docker compose -f docker-compose.production.yml exec -T postgres rm -f $remoteBackup
}
