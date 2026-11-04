# Agente IA Documental

Plataforma documental con autenticacion, carga de archivos, procesamiento RAG, busqueda, biblioteca, chat sobre documentos, exportacion e importacion desde Google Drive.

Los modulos de CRM, WhatsApp, Business Intelligence, agentes empresariales, actividad transversal y notificaciones fueron retirados para dejar el proyecto enfocado en documentos.

## Servicios activos

- `backend/AuthServices`: autenticacion Django, usuarios y JWT.
- `backend/RagDocumentChatServices`: chat RAG sobre documentos.
- `backend/RagDocumentEmbeddingServices`: carga, extraccion, chunks y embeddings.
- `backend/DocumentSearchServices`: busqueda, detalle y seleccion documental.
- `backend/DocumentAccessServices`: preview, descarga, contenido y borrado.
- `backend/DocumentLibraryServices`: carpetas, favoritos y recientes.
- `backend/DocumentTransferServices`: historial de cargas/descargas.
- `backend/ConversationServices`: historial del chat documental.
- `backend/ProfileServices`: perfil y avatar.
- `backend/DocumentExportServices`: exportacion de respuestas a PDF.
- `backend/GoogleDriveImportServices`: importacion desde Google Drive.
- `frontend`: interfaz React simple para chat y documentos.

## Ejecucion con Docker

```bash
cd docker
docker compose up --build
```

El agregador `docker/docker-compose.yml` carga:

- `compose/infra.yml`
- `compose/auth.yml`
- `compose/documents.yml`
- `compose/collaboration.yml`
- `compose/profile.yml`
- `compose/frontend.yml`

URLs principales:

- Frontend: `http://localhost:3000`
- Auth: `http://localhost:8001`
- Chat RAG: `http://localhost:8002`
- Ingestion/embeddings: `http://localhost:8003`
- Busqueda documental: `http://localhost:8004`
- Acceso documental: `http://localhost:8005`
- Biblioteca: `http://localhost:8006`
- Transferencias: `http://localhost:8007`
- Conversaciones: `http://localhost:8008`
- Perfil: `http://localhost:8015`
- Exportaciones: `http://localhost:8016`
- Google Drive import: `http://localhost:8017`

## Ejecucion local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/RagDocumentChatServices/requirements.txt
pip install -r backend/RagDocumentEmbeddingServices/requirements.txt
pip install -r backend/DocumentSearchServices/requirements.txt
pip install -r backend/DocumentAccessServices/requirements.txt
copy .env.example .env
```

Servicios documentales principales:

```bash
make run-chat
make run-embedding
make run-search
make run-access
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Base de datos

El esquema SQL vive en `scripts/database/run_all.sql` y ahora carga solo dominios documentales:

- documentos y embeddings
- conversaciones
- perfiles
- exportaciones
- importaciones de Google Drive
- constraints, indices, funciones, triggers y seeds necesarios

## Credenciales locales

El entrypoint de `AuthServices` crea el usuario inicial si no existe:

```text
Username: blandskronadmin
Password: admin1234
```

## Scripts utiles

Procesar documentos pendientes:

```bash
python scripts/process_pending_documents.py --limit 10
```

Reindexar documentos:

```bash
python scripts/reindex_documents.py --all --limit 100
```

### Embeddings locales

La ingesta y el chat usan `intfloat/multilingual-e5-small` en CPU. El primer uso descarga el modelo. Las instalaciones nuevas crean el índice con vectores de 384 dimensiones.

Para actualizar una instalación existente, detén la ingesta y el chat, respalda la base y ejecuta `scripts/database/migrations/001_local_embeddings.sql` con `psql` conectado a la base documental. La migración elimina los vectores de 1536 dimensiones y marca sus documentos para reindexar. Los archivos originales se conservan. Con el almacenamiento documental disponible, ejecuta el script de reindexación por lotes antes de volver a habilitar el chat.
