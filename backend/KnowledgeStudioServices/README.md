# KnowledgeStudioServices

Servicio modular opcional de **Knowledge Studio** y servidor **MCP JSON-RPC 2.0 de solo lectura**, acotado tras `STUDIO_ENABLED=false` por defecto para mantener intacto el despliegue base. Se habilita con el overlay `docker/compose/studio.yml` (`--profile studio`) y el rol mínimo `studio_runtime`.

## Arranque opcional

```bash
STUDIO_ENABLED=true docker compose -f compose.yaml -f docker/compose/studio.yml --profile studio up -d --build
```

Puerto local **8018**.

## Componentes implementados

- `app/config/security.py`: verificación JWT RS256 usando la clave pública de `AuthServices`.
- `app/domain/artifacts.py`: envelope Pydantic v2 (`ArtifactContent`, `FactualClaim`, `EvidenceRow`, `ProposedTask`), 4 familias P0 (12 plantillas), validador de groundedness (`validate_groundedness`) y exportador CSV anti *formula-injection* con procedencia.
- `app/domain/visuals_and_learning.py`: sanitizador Mermaid, grafo conceptual desde `[[wikilinks]]`, series de gráficos desde celdas verificadas, validador de quizzes citados y SM-2 offline sin telemetría.
- `app/application/studio_runner.py` y `app/application/quota_guard.py`: ejecución con revalidación de acceso (`ACCESS_REVOKED`), cancelación, máximo 1 reparación acotada y cuotas diarias/concurrencia por empresa.
- `app/infrastructure/studio_repository_pg.py`: persistencia en `studio.*` con cola `FOR UPDATE SKIP LOCKED`, colecciones, jobs, artefactos versionados y consultas autorizadas.
- `app/interfaces/mcp_server.py` y `app/interfaces/mcp_readonly.py`: servidor MCP JSON-RPC 2.0 en `POST /api/v1/mcp` (`initialize`, `ping`, `tools/list`, `tools/call`) limitado a 4 herramientas de solo lectura (`search_documents`, `get_document_chunks`, `list_studio_artifacts`, `get_studio_artifact`) con auditoría `mcp.*`.
- `app/main.py`: API FastAPI con CORS, endpoints autenticados (`/collections`, `/jobs`, `/artifacts`, `/mcp`) y utilidades de validación/exportación.
- `tests/`: suites unitarias y HTTP ejecutables mediante `make test-studio` y `make eval-studio`.
