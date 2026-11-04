# GoogleDriveImportServices

Microservicio responsable de conectar Google Drive con la biblioteca documental de Blandskron Documental.

## Responsabilidad

- Generar la URL OAuth para conectar una cuenta Google.
- Guardar tokens OAuth cifrados por usuario.
- Refrescar access tokens cuando expiran.
- Descargar archivos seleccionados desde Google Drive.
- Exportar archivos nativos de Google Workspace a formatos procesables.
- Enviar los archivos importados a `RagDocumentEmbeddingServices` para que entren al flujo normal de documentos, procesamiento y embeddings.
- Registrar el historial de importaciones y el estado por archivo.

## Puerto

```text
8017 -> 8000
```

## Variables principales

```text
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_DRIVE_REDIRECT_URI=http://localhost:3000/documents
GOOGLE_TOKEN_ENCRYPTION_KEY=change-me-with-a-long-random-secret
RAG_DOCUMENT_BASE_URL=http://localhost:8003
```

En Docker, `RAG_DOCUMENT_BASE_URL` apunta a:

```text
http://rag-document-embedding-service:8000
```

## Endpoints

```text
GET  /api/v1/health
GET  /api/v1/google-drive/auth-url
POST /api/v1/google-drive/oauth/callback
GET  /api/v1/google-drive/connection
POST /api/v1/google-drive/imports
GET  /api/v1/google-drive/imports
GET  /api/v1/google-drive/imports/{import_id}
GET  /api/v1/google-drive/imports/{import_id}/files
```

## Flujo recomendado

1. El frontend obtiene `authorization_url`.
2. El usuario conecta Google Drive.
3. El frontend recibe un `code` OAuth y lo envía al callback del microservicio.
4. El frontend abre Google Picker con la misma aplicación OAuth.
5. El frontend envía los `file_id` seleccionados a `/google-drive/imports`.
6. El microservicio descarga o exporta cada archivo.
7. El microservicio sube cada archivo a `RagDocumentEmbeddingServices`.
8. Los documentos quedan disponibles en la biblioteca documental de Blandskron Documental.

## Formatos nativos de Google

```text
Google Docs   -> DOCX
Google Sheets -> XLSX
Google Slides -> PPTX
Google Drawing -> PDF
```

## Seguridad

- Requiere JWT de Blandskron Documental en todos los endpoints de usuario.
- Usa `drive.file` como scope recomendado.
- Cifra access token y refresh token antes de persistirlos.
- No expone archivos públicamente; todo entra al pipeline documental interno.
