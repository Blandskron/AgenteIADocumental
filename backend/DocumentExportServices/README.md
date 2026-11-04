# DocumentExportServices

`DocumentExportServices` es el microservicio responsable de convertir respuestas y artefactos del ecosistema Blandskron Documental en documentos exportables. El primer caso soportado es exportar respuestas del chat documental a PDF.

## Responsabilidades

- Generar PDFs desde respuestas de chat, pregunta original y fuentes.
- Persistir metadatos de exportacion por usuario autenticado.
- Guardar archivos exportados en storage configurable.
- Exponer estado y descarga segura del PDF.
- Mantener la responsabilidad de renderizado fuera de los servicios RAG/chat.

## Endpoints

Todos los endpoints funcionales requieren `Authorization: Bearer <access_token>`.

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| GET | `/api/v1/health` | Estado del servicio |
| GET | `/api/v1/health/db` | Estado de PostgreSQL |
| POST | `/api/v1/exports/chat-message/pdf` | Crea un PDF desde una respuesta de chat |
| GET | `/api/v1/exports` | Lista exportaciones del usuario |
| GET | `/api/v1/exports/{export_id}` | Obtiene metadatos de una exportacion |
| GET | `/api/v1/exports/{export_id}/status` | Consulta estado de una exportacion |
| GET | `/api/v1/exports/{export_id}/download` | Descarga el archivo PDF |

## Ejemplo de request

```json
{
  "conversation_id": "conv_123",
  "message_id": "msg_456",
  "title": "Resumen contractual",
  "question": "Resume las obligaciones principales del contrato",
  "answer": "El contrato establece obligaciones de confidencialidad, pago y soporte...",
  "sources": [
    {
      "document_id": "doc_1",
      "filename": "contrato.pdf",
      "page": 4,
      "snippet": "La parte compradora debera..."
    }
  ],
  "metadata": {
    "module": "chat"
  }
}
```

## Configuracion

Variables relevantes:

- `DATABASE_URL`
- `AUTH_JWT_PUBLIC_KEY_PATH`
- `AUTH_JWT_ALGORITHM`
- `CORS_ORIGINS`
- `EXPORT_STORAGE_BASE_PATH`

En Docker Compose, `EXPORT_STORAGE_BASE_PATH` apunta a `/app/exports` y se monta sobre `documents/exports`.

## Persistencia

Usa la tabla `document_exports`, definida en `scripts/database/schemas/009_exports.sql`.

Campos principales:

- `export_id`
- `owner_user_id`
- `source_type`
- `conversation_id`
- `message_id`
- `title`
- `format`
- `status`
- `filename`
- `storage_path`
- `file_size_bytes`
- `metadata`

## Criterios de diseno

- El servicio no llama al LLM ni a embeddings.
- El servicio no modifica conversaciones.
- El servicio solo renderiza, almacena y expone exportaciones.
- La descarga valida ownership usando el JWT.

Esto evita mezclar RAG con generacion documental y deja abierta la puerta para exportar mas adelante conversaciones completas o resultados de busqueda documental.

## Ejecucion local

```powershell
cd backend/DocumentExportServices
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Con Docker Compose desde la raiz:

```powershell
docker compose -f docker/docker-compose.yml up document-export-service
```
