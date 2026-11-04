# Backend Documental

Este directorio contiene los servicios backend que quedan activos para el producto documental.

## Servicios

| Servicio | Puerto local | Responsabilidad |
| --- | ---: | --- |
| `AuthServices` | 8001 | Login, refresh/logout, usuarios, grupos y firma JWT RS256. |
| `RagDocumentChatServices` | 8002 | Chat RAG con recuperacion de chunks y proveedor LLM. |
| `RagDocumentEmbeddingServices` | 8003 | Upload, extraccion, chunking, embeddings y reindexacion. |
| `DocumentSearchServices` | 8004 | Busqueda documental, detalle, chunks y seleccion para chat. |
| `DocumentAccessServices` | 8005 | Preview, descarga, contenido y borrado de documentos. |
| `DocumentLibraryServices` | 8006 | Carpetas, favoritos, recientes y organizacion documental. |
| `DocumentTransferServices` | 8007 | Registro y seguimiento de transferencias documentales. |
| `ConversationServices` | 8008 | Historial de conversaciones documentales. |
| `ProfileServices` | 8015 | Perfil de usuario y carga de avatar. |
| `DocumentExportServices` | 8016 | Exportacion de respuestas y artefactos a PDF. |
| `GoogleDriveImportServices` | 8017 | Importacion de archivos desde Google Drive al pipeline documental. |

## Base de datos

El bootstrap de esquema esta centralizado en `scripts/database/run_all.sql` e incluye solo:

- extensiones `pgcrypto` y `vector`
- tablas documentales
- conversaciones
- perfiles
- exportaciones
- importaciones de Google Drive
- constraints, indices y triggers del dominio documental

## Ejecucion

Desde la raiz del repositorio:

```powershell
docker compose -f docker/docker-compose.yml up --build
```

Para levantar solo infraestructura y servicios documentales:

```powershell
cd docker
docker compose -f compose/infra.yml -f compose/auth.yml -f compose/documents.yml -f compose/collaboration.yml -f compose/profile.yml up --build
```

Los modulos de CRM, WhatsApp, BI, agentes, actividad y notificaciones fueron retirados para mantener el foco en documentos.
