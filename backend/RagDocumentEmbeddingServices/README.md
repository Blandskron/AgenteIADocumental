# RagDocumentEmbeddingServices

Recibe archivos, conserva el original y genera fragmentos y embeddings locales para su recuperación.

## Recorrido

```mermaid
flowchart LR
    client["Web o importador Drive"] --> ingest["Ingesta y autorización"]
    ingest --> originals[("Volumen de originales")]
    ingest --> extract["Extracción, OCR y fragmentación"]
    extract --> model["E5 en CPU"] --> db[("PostgreSQL y pgvector")]
```

## Arranque local

Configura el entorno según el [README del proyecto](../../README.md#probar-en-local) y ejecuta desde la raíz.

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up -d --build --wait rag-document-embedding-service
```

Puerto local **8003**.

## Guías

- [Contrato HTTP y autorización](docs/REFERENCE.md#api-endpoints).
- [Operación y configuración](docs/REFERENCE.md#running-the-service).
- [Instrucciones del componente](AGENTS.md) y [skill documental-ingest](../../.agents/skills/documental-ingest/SKILL.md).
- [Mapa del backend](../README.md) y [verificación de entrega](../../docs/release/README.md).
