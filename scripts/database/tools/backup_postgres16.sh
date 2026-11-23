#!/usr/bin/env sh
# Offline logical backup for Blandskron Documental PostgreSQL 16 (EVO-013).
# Produces a backup directory compatible with scripts/database/tools/restore_postgres16.sh:
#   - roles.sql
#   - documents.dump (custom format)
#   - SHA256SUMS.txt
set -eu

CONTAINER="${POSTGRES_CONTAINER:-rag-documents-postgres}"
DB_NAME="${POSTGRES_DB:-documents_db}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${1:-./backups/blandskron-pg-${TIMESTAMP}}"

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"

echo "Backing up roles from container '$CONTAINER'..."
docker exec "$CONTAINER" pg_dumpall -U postgres --roles-only > "$OUT_DIR/roles.sql"

echo "Backing up database '$DB_NAME' in custom format..."
docker exec "$CONTAINER" pg_dump -U postgres -d "$DB_NAME" -Fc > "$OUT_DIR/documents.dump"

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$OUT_DIR" && sha256sum roles.sql documents.dump > SHA256SUMS.txt)
elif command -v shasum >/dev/null 2>&1; then
  (cd "$OUT_DIR" && shasum -a 256 roles.sql documents.dump > SHA256SUMS.txt)
fi

chmod 600 "$OUT_DIR/roles.sql" "$OUT_DIR/documents.dump"
echo "Backup complete: $OUT_DIR"
