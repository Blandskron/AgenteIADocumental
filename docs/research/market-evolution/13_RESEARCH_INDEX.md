# 13 — Índice Maestro de la Investigación de Evolución

- **Proyecto:** Blandskron Documental (`AgenteIADocumental`)
- **Rama auditada:** `develop`
- **Commit SHA auditado:** `5a4fac256199f5418fcd5d1de749bdf422d2e407` (`5a4fac2`)
- **Fecha de auditoría:** 22 de noviembre de 2026
- **Alcance:** Investigación, auditoría técnica sobre código real y planificación de evolución (sin modificaciones de código, dependencias ni esquemas).

---

## 1. Catálogo de entregables y referencias cruzadas

| # | Documento | Contenido principal | Estado |
|---|---|---|---|
| 01 | [01_CURRENT_STATE_AUDIT.md](./01_CURRENT_STATE_AUDIT.md) | Inventario real de los 14 servicios backend, base de datos, frontend, Docker, CI/CD, resultados de pruebas locales y clasificación oficial. | Verificado |
| 02 | [02_FUNCTIONAL_CAPABILITIES_RESEARCH.md](./02_FUNCTIONAL_CAPABILITIES_RESEARCH.md) | Investigación de capacidades del ecosistema por problema/valor/enfoque local-first y capacidades descartadas. | Verificado |
| 03 | [03_FEATURE_GAP_MATRIX.md](./03_FEATURE_GAP_MATRIX.md) | Matriz de 16 columnas con brechas, fortalezas, prioridades P0–P3 y clasificación estratégica de decisiones. | Verificado |
| 04 | [04_DOCUMENT_INTELLIGENCE_OPPORTUNITIES.md](./04_DOCUMENT_INTELLIGENCE_OPPORTUNITIES.md) | Extracción estructurada híbrida, comparación documental, vencimientos, obligaciones y separación detección → revisión → acción. | Verificado |
| 05 | [05_RAG_QUALITY_RESEARCH.md](./05_RAG_QUALITY_RESEARCH.md) | Diagnóstico del pipeline RAG/OCR, estrategia de mejora escalonada y metodología de evaluación reproducible. | Verificado |
| 06 | [06_LOCAL_AI_RESEARCH.md](./06_LOCAL_AI_RESEARCH.md) | Modelos y motores open source gratuitos, licencias y matriz honesta para 4, 8, 16 y 32 GB RAM. | Verificado |
| 07 | [07_AGENT_AND_MCP_AUDIT.md](./07_AGENT_AND_MCP_AUDIT.md) | Revalidación exhaustiva de `KnowledgeStudioServices`, `AgentOrchestratorServices`, `CodeSandboxRunner` y MCP. | Verificado |
| 08 | [08_FRONTEND_PRODUCT_EXPERIENCE.md](./08_FRONTEND_PRODUCT_EXPERIENCE.md) | Auditoría vista por vista del frontend, consistencia *Floating Glass*, UX, accesibilidad y patrones React 19. | Verificado |
| 09 | [09_ARCHITECTURE_EVOLUTION.md](./09_ARCHITECTURE_EVOLUTION.md) | 5 propuestas arquitectónicas (`ARQ-01` a `ARQ-05`) evaluadas contra las 16 preguntas de la Etapa X. | Verificado |
| 10 | [10_LOCAL_FIRST_COMPLIANCE.md](./10_LOCAL_FIRST_COMPLIANCE.md) | Matriz de autonomía offline de 14 recorridos, clasificación de dependencias y mitigación de fricciones. | Verificado |
| 11 | [11_PRODUCT_EVOLUTION_ROADMAP.md](./11_PRODUCT_EVOLUTION_ROADMAP.md) | Roadmap priorizado (`EVO-001` a `EVO-019`) en P0/P1/P2/P3 con dependencias, criterios y reversión. | Verificado |
| 12 | [12_EXECUTIVE_SUMMARY.md](./12_EXECUTIVE_SUMMARY.md) | Resumen ejecutivo, posicionamiento para 4 segmentos de usuario y dirección estratégica. | Verificado |
| 13 | [13_RESEARCH_INDEX.md](./13_RESEARCH_INDEX.md) | Este índice maestro con trazabilidad y lista de validación final. | Verificado |

---

## 2. Documentación base del repositorio contrastada

- [README raíz](../../../README.md) y [Reglas de colaboración (`AGENTS.md`)](../../../AGENTS.md)
- [Arquitectura del sistema](../../architecture.md) y [Operaciones](../../operations.md)
- [Verificación de entrega](../../release/README.md) y [Índice de mantenimiento](../../maintainers.md)
- [ADR-005: Extensibilidad LLM y MCP](../../ADR_EXTENSIBILITY_LLM_MCP.md)
- [ADR-006: Orquestador de Agentes](../../ADR_AGENT_ORCHESTRATOR.md)
- [ADR-007: Code Mode Sandbox](../../ADR_CODE_MODE_SANDBOX.md)

---

## 3. Verificación de cumplimiento de las 20 reglas de validación final

| # | Regla de validación | Estado |
|---|---|---|
| 1 | Toda funcionalidad existente contrastada directamente con el código | Cumplido (`01`, `07`, `08`) |
| 2 | Sin duplicación de módulos ni capacidades actuales | Cumplido (amplía Studio, Agents, Library y RAG existentes) |
| 3 | `KnowledgeStudioServices` auditado en código y SQL | Cumplido (`01`, `07`) |
| 4 | `AgentOrchestratorServices` auditado en código, SQL y ADR | Cumplido (`01`, `07`) |
| 5 | `CodeSandboxRunner` auditado en Deno, Compose y tests | Cumplido (`01`, `07`) |
| 6 | MCP auditado en protocolo, JWT, tenant y auditoría | Cumplido (`07`) |
| 7 | Todas las propuestas respetan el modo local-first | Cumplido (`09`, `10`, `11`) |
| 8 | Dependencias propuestas son gratuitas (MIT/Apache-2.0) u opcionales | Cumplido (`02`, `06`; AGPL descartado) |
| 9 | Cero dependencias cloud obligatorias nuevas | Cumplido (`10`) |
| 10 | Cambios compatibles con la arquitectura actual | Cumplido (`09`) |
| 11 | Cero microservicios injustificados propuestos | Cumplido (`09`, `11`) |
| 12 | Resultados de pruebas 100 % reales (ninguno inventado) | Cumplido (`01`, `05`, `07`, `08`) |
| 13 | Cada propuesta justificada con beneficio verificable | Cumplido (`03`, `09`, `11`) |
| 14 | Nomenclatura original y descriptiva propia de Blandskron Documental | Cumplido (`01`–`13`) |
| 15 | Cero menciones a nombres comerciales de productos competidores | Cumplido (verificado por búsqueda en los 13 archivos) |
| 16 | Licencias y atribuciones open source preservadas | Cumplido (`06`, `02`) |
| 17 | Roadmap basado en brechas reales demostradas | Cumplido (`11`) |
| 18 | Mejoras ordenadas por dependencias técnicas | Cumplido (`11`) |
| 19 | Experiencia de instalación sencilla preservada | Cumplido (`10`, `11`: `EVO-002`, `EVO-013`) |
| 20 | Capacidades principales viables con IA local gratuita según hardware explícito | Cumplido (`06`: 4/8/16/32 GB RAM) |
