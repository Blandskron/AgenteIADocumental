#!/bin/sh
set -eu

SECRETS_DIR="/run/blandskron-secrets"
mkdir -p "$SECRETS_DIR"
umask 022

gen_hex() {
    bytes="$1"
    od -An -tx1 -N "$bytes" /dev/urandom | tr -d ' \n'
}

write_secret() {
    name="$1"
    env_value="$2"
    bytes="$3"
    target="$SECRETS_DIR/$name"

    if [ -n "$env_value" ]; then
        printf '%s' "$env_value" > "$target.tmp"
        chmod 0444 "$target.tmp"
        mv -f "$target.tmp" "$target"
        return 0
    fi

    if [ -s "$target" ]; then
        chmod 0444 "$target"
        return 0
    fi

    gen_hex "$bytes" > "$target.tmp"
    chmod 0444 "$target.tmp"
    mv -f "$target.tmp" "$target"
}

write_secret "postgres_password" "${POSTGRES_PASSWORD:-}" 24
write_secret "django_secret_key" "${DJANGO_SECRET_KEY:-}" 32
write_secret "secrets_encryption_key" "${SECRETS_ENCRYPTION_KEY:-}" 24

echo "Blandskron runtime secrets initialized."

