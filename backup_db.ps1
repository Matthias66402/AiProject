# Erstellt einen pg_dump-Backup der laufenden Postgres-Datenbank (aiproject_postgres).
#
# Aufruf:      .\backup_db.ps1
# Restore:     Get-Content backups\aiproject_20260910_083000.sql -Raw | docker exec -i aiproject_postgres sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
#
# Empfehlung: regelmässig laufen lassen (z.B. per Windows Task Scheduler taeglich),
# damit ein Datenverlust durch Docker/WSL2-Resets, "down -v" o.ae. nicht die
# einzige Kopie der Daten trifft.

$ErrorActionPreference = "Stop"

$container = "aiproject_postgres"
$backupDir = Join-Path $PSScriptRoot "backups"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path $backupDir "aiproject_$timestamp.sql"
$keepLast = 14

$running = docker ps --filter "name=^$container`$" --format "{{.Names}}"
if (-not $running) {
    Write-Error "Container '$container' laeuft nicht. Erst 'docker compose up -d' ausfuehren."
    exit 1
}

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

$dump = docker exec $container sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"'
if ($LASTEXITCODE -ne 0 -or -not $dump) {
    Write-Error "pg_dump fehlgeschlagen."
    exit 1
}

$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllLines($backupFile, $dump, $utf8NoBom)

Write-Host "Backup erstellt: $backupFile"

# Nur die letzten $keepLast Backups behalten
Get-ChildItem $backupDir -Filter "aiproject_*.sql" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip $keepLast |
    Remove-Item -Force
