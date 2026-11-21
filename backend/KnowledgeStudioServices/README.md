# KnowledgeStudioServices (P0)

Servicio modular de **Knowledge Studio** (Fase 4 del [roadmap](../../roadmap.md)), acotado tras feature flag `STUDIO_ENABLED=false` por defecto para mantener intacto el despliegue base de Docker Compose.

## Componentes implementados

- `app/domain/artifacts.py`: Envelope Pydantic v2 (`ArtifactContent`, `FactualClaim`, `InferenceItem`, `EvidenceRow`, `ProposedTask`), catálogo de las 4 familias P0 (12 plantillas), validador estricto de groundedness (`validate_groundedness`), huella de caché (`compute_cache_fingerprint`) y exportador CSV seguro contra formula-injection con columna de procedencia (`render_evidence_table_csv`).
- `app/application/studio_runner.py`: Ejecutor de jobs con revalidación de acceso previa y en vuelo (`ACCESS_REVOKED`), soporte de cancelación y máximo 1 reparación automática acotada.
- `tests/test_studio_engine.py`: Suite unitaria de groundedness, CSV seguro, revocación en vuelo y reparación acotada.

