#!/bin/sh
set -e

if [ "$(id -u)" -eq 0 ]; then
    chown auth:auth /app/signing_keys /app/verification_keys
    for key in /app/signing_keys/private.pem /app/verification_keys/public.pem; do
        if [ -L "$key" ]; then
            printf '%s\n' "JWT key must not be a symbolic link: $key" >&2
            exit 1
        fi
        if [ -f "$key" ]; then
            chown -h auth:auth "$key"
        fi
    done
    exec gosu auth "$@"
fi

exec "$@"
