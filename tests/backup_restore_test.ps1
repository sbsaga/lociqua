param([Parameter(Mandatory = $true)] [string] $BackupDirectory = 'backups')

# Creates a disposable restore database. It never targets the live lociqua DB.
$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $BackupDirectory "lociqua-restore-drill-$stamp.dump"
& "$PSScriptRoot\..\infra\postgres\backup.ps1" -Destination $backup
& "$PSScriptRoot\..\infra\postgres\restore.ps1" -Backup $backup -Database 'lociqua_restore_test'
$count = docker compose -f docker-compose.production.yml exec -T postgres psql -U lociqua -d lociqua_restore_test -tAc 'SELECT count(*) FROM companies'
if ($count -notmatch '^\s*\d+\s*$') { throw 'Restored database could not be queried.' }
Write-Host "backup/restore drill passed; restored company count: $($count.Trim())"
