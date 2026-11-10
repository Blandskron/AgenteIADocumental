#!/bin/sh
set -eu
case "$DOCUMENT_UID:$DOCUMENT_GID" in
    *[!0-9:]*|:*|*:) echo "Document UID/GID must be numeric." >&2; exit 1 ;;
esac
if [ "$DOCUMENT_UID" -eq 0 ] || [ "$DOCUMENT_GID" -eq 0 ]; then
    echo "Document storage requires a non-root owner." >&2
    exit 1
fi
# Only initialize an empty root-owned directory created by Docker. Never change
# ownership recursively or modify an existing installation's files.
if [ "$(stat -c %u /documents)" = 0 ] && [ -z "$(find /documents -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    chown "$DOCUMENT_UID:$DOCUMENT_GID" /documents
fi
if ! gosu "$DOCUMENT_UID:$DOCUMENT_GID" sh -c 'test -r /documents && test -w /documents && test -x /documents'; then
    echo "Document storage is not writable. Preserve existing files and set EMBEDDING_UID/GID and ACCESS_UID/GID to its owner." >&2
    exit 1
fi
echo "Document storage ready; existing files preserved."
