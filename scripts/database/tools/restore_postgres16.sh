#!/bin/sh
set -eu

backup=${1:?Supply the private backup directory}
test -s "$backup/roles.sql"
test -s "$backup/documents.dump"

if [ "${PGDATA:-}" != /var/lib/postgresql/data/pgdata ]; then
    echo "Restore requires the new PostgreSQL container." >&2
    exit 1
fi

empty="$(psql -X -U postgres -d documents_db -At -v ON_ERROR_STOP=1 -c \
    "SELECT NOT EXISTS (SELECT 1 FROM pg_class WHERE relnamespace = 'public'::regnamespace)
        AND NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname NOT IN ('public', 'information_schema')
            AND nspname NOT LIKE 'pg\\_%');")"
if [ "$empty" != t ]; then
    echo "Restore requires an empty documents_db." >&2
    exit 1
fi

# Restore into the database created by the new cluster so its indexes use the
# destination collation. Keep roles, privileges and data in the same transaction.
work="$(mktemp -d)"
trap 'rm -f "$work/roles.sql" "$work/documents.sql"; rmdir "$work"' EXIT
sed '/^CREATE ROLE postgres;$/d' "$backup/roles.sql" >"$work/roles.sql"
pg_restore --file="$work/documents.sql" "$backup/documents.dump"
psql -X -q -U postgres -d documents_db -v ON_ERROR_STOP=1 --single-transaction \
    -f "$work/roles.sql" -f "$work/documents.sql"
