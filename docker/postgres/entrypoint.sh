#!/bin/sh
set -eu

case "${1:-}" in
  postgres|-*)
    if [ -s /var/lib/postgresql/data/PG_VERSION ]; then
      echo "Legacy PostgreSQL volume detected. Follow docs/operations.md to restore into a new volume." >&2
      exit 1
    fi
    ;;
esac

exec docker-entrypoint.sh "$@"
