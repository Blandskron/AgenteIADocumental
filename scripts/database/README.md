# Base de datos documental

PostgreSQL 16 con pgvector almacena identidad, relaciones multiempresa, documentos, vectores y datos de colaboración. Django migra sus tablas de identidad y SQL mantiene los dominios documentales y los roles de ejecución.

```mermaid
flowchart LR
    postgres["PostgreSQL saludable"] --> schema["Esquema documental"]
    schema --> roles["Roles Auth"]
    roles --> django["Migraciones Django"]
    django --> integrity["Integridad de identidades y membresías"]
    schema --> domains["Roles de dominio según dependencias Compose"]
```

## Guías

- [Arranque y aplicación del esquema](docs/OPERATIONS.md#activación-vigente).
- [Preflight multiempresa](docs/OPERATIONS.md#preflight-multiempresa--plat-001a) y [mapa de escritores](docs/OPERATIONS.md#escritores-y-decisiones-antes-de-imponer-restricciones).
- [Validación SQL sintética y concurrencia](docs/OPERATIONS.md#validación-sintética).
- [Instrucciones del esquema](AGENTS.md) y [skill de migraciones](../../.agents/skills/documental-database/SKILL.md).
