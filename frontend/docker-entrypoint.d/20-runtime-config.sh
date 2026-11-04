#!/bin/sh
set -eu

js_string() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

auth_base_url=$(js_string "${VITE_AUTH_BASE_URL:-http://localhost:8001}")
google_client_id=$(js_string "${VITE_GOOGLE_CLIENT_ID:-}")
google_picker_api_key=$(js_string "${VITE_GOOGLE_PICKER_API_KEY:-}")
google_picker_app_id=$(js_string "${VITE_GOOGLE_PICKER_APP_ID:-}")
rag_chat_base_url=$(js_string "${VITE_RAG_CHAT_BASE_URL:-http://localhost:8002}")
rag_document_base_url=$(js_string "${VITE_RAG_DOCUMENT_BASE_URL:-http://localhost:8003}")
document_search_base_url=$(js_string "${VITE_DOCUMENT_SEARCH_BASE_URL:-http://localhost:8004}")
document_access_base_url=$(js_string "${VITE_DOCUMENT_ACCESS_BASE_URL:-http://localhost:8005}")
document_library_base_url=$(js_string "${VITE_DOCUMENT_LIBRARY_BASE_URL:-http://localhost:8006}")
document_transfer_base_url=$(js_string "${VITE_DOCUMENT_TRANSFER_BASE_URL:-http://localhost:8007}")
document_export_base_url=$(js_string "${VITE_DOCUMENT_EXPORT_BASE_URL:-http://localhost:8016}")
google_drive_import_base_url=$(js_string "${VITE_GOOGLE_DRIVE_IMPORT_BASE_URL:-http://localhost:8017}")
conversation_base_url=$(js_string "${VITE_CONVERSATION_BASE_URL:-http://localhost:8008}")
profile_base_url=$(js_string "${VITE_PROFILE_BASE_URL:-http://localhost:8015}")

cat > /usr/share/nginx/html/runtime-config.js <<EOF
window.__BLANDSKRON_CONFIG__ = {
  VITE_GOOGLE_CLIENT_ID: "${google_client_id}",
  VITE_GOOGLE_PICKER_API_KEY: "${google_picker_api_key}",
  VITE_GOOGLE_PICKER_APP_ID: "${google_picker_app_id}",
  VITE_AUTH_BASE_URL: "${auth_base_url}",
  VITE_RAG_CHAT_BASE_URL: "${rag_chat_base_url}",
  VITE_RAG_DOCUMENT_BASE_URL: "${rag_document_base_url}",
  VITE_DOCUMENT_SEARCH_BASE_URL: "${document_search_base_url}",
  VITE_DOCUMENT_ACCESS_BASE_URL: "${document_access_base_url}",
  VITE_DOCUMENT_LIBRARY_BASE_URL: "${document_library_base_url}",
  VITE_DOCUMENT_TRANSFER_BASE_URL: "${document_transfer_base_url}",
  VITE_DOCUMENT_EXPORT_BASE_URL: "${document_export_base_url}",
  VITE_GOOGLE_DRIVE_IMPORT_BASE_URL: "${google_drive_import_base_url}",
  VITE_CONVERSATION_BASE_URL: "${conversation_base_url}",
  VITE_PROFILE_BASE_URL: "${profile_base_url}"
};
EOF
