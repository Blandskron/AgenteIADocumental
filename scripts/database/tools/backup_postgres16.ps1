# Offline logical backup for Blandskron Documental PostgreSQL 16 (EVO-013).
# Produces roles.sql + documents.dump + SHA256SUMS.txt compatible with restore_postgres16.sh.
param(
    [string]$OutDir = "",
    [string]$Container = "rag-documents-postgres",
    [string]$Database = "documents_db"
)

$ErrorActionPreference = "Stop"

if (-not $OutDir) {
    $ts = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $OutDir = Join-Path "." "backups/blandskron-pg-$ts"
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$rolesPath = Join-Path $OutDir "roles.sql"
$dumpPath = Join-Path $OutDir "documents.dump"
$sumsPath = Join-Path $OutDir "SHA256SUMS.txt"

Write-Host "Backing up roles from container '$Container'..."
docker exec $Container pg_dumpall -U postgres --roles-only | Out-File -FilePath $rolesPath -Encoding utf8

Write-Host "Backing up database '$Database' in custom format..."
cmd /c "docker exec $Container pg_dump -U postgres -d $Database -Fc > `"$dumpPath`""
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump failed with exit code $LASTEXITCODE"
}

$hRoles = (Get-FileHash -Algorithm SHA256 $rolesPath).Hash.ToLower()
$hDump = (Get-FileHash -Algorithm SHA256 $dumpPath).Hash.ToLower()
@(
    "$hRoles  roles.sql",
    "$hDump  documents.dump"
) | Set-Content -Path $sumsPath -Encoding ascii

Write-Host "Backup complete: $OutDir"
