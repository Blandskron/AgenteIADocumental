# KnowledgeStudioServices

Servicio modular opcional de **Knowledge Studio**, acotado tras la bandera `STUDIO_ENABLED=false` por defecto para mantener intacto el despliegue base de Docker Compose. Se levanta con el overlay `docker/compose/studio.yml` (`--profile studio`) y el rol de mínimos privilegios `studio_runtime`.

## Componentes implementados

- `app/domain/artifacts.py`: Envelope Pydantic v2 (`ArtifactContent`, `FactualClaim`, `InferenceItem`, `EvidenceRow`, `ProposedTask`), catálogo de las 4 familias P0 (12 plantillas), validador estricto de groundedness (`validate_groundedness`), huella de caché (`compute_cache_fingerprint`) y exportador CSV seguro contra *formula-injection* con columna de procedencia (`render_evidence_table_csv`).
- `app/domain/visuals_and_learning.py`: Sanitizador Mermaid (`sanitize_mermaid_diagram`), grafo conceptual determinista desde `[[wikilinks]]` (`build_concept_graph_from_wikilinks`), series de gráficos desde celdas verificadas (`extract_verified_chart_series`), validador de quizzes citados (`filter_valid_quiz_questions`) y motor SM-2 offline sin telemetría (`sm2_review`).
- `app/application/studio_runner.py` y `app/application/quota_guard.py`: Ejecutor de jobs con revalidación de acceso previa y en vuelo (`ACCESS_REVOKED`), soporte de cancelación, máximo 1 reparación automática acotada y control de cuota diaria de tokens y concurrencia por empresa (`StudioQuotaGuard`).
- `app/infrastructure/studio_repository_pg.py`: Persistencia sobre el esquema aislado `studio.*` con cola atómica `FOR UPDATE SKIP LOCKED` e idempotencia por `(tenant_id, operation_key)`.
- `app/interfaces/worker.py`, `app/interfaces/mcp_readonly.py` y `app/main.py`: Worker de cola, router MCP de solo lectura con auditoría `mcp.*` y API FastAPI acotada por `STUDIO_ENABLED`.
- `tests/`: Suites unitarias y HTTP (`test_studio_engine.py`, `test_visuals_and_learning.py`, `test_mcp_readonly.py`, `test_quota_guard.py`, `test_studio_worker.py`, `test_studio_api.py`), ejecutables mediante `make test-studio` y `make eval-studio`.
