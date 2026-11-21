# Acta de Reunión — Comité de Operaciones Sintético (ACTA-2026-014)

- **Fecha:** 2026-04-15
- **Código de referencia:** ACTA-2026-014
- **Proyecto:** Plataforma Documental Aurora (Entorno Sintético)
- **Asistentes:** Operador Uno (Líder Técnico), Analista Dos (Seguridad), Coordinadora Tres (Producto)

## 1. Resumen ejecutivo

El comité revisó la migración del índice vectorial de la plataforma documental sintética y aprobó el plan de transición de `IVFFlat` a `HNSW` para reducir la pérdida de recall en bases pequeñas y medianas. También se acordó fijar un plazo máximo de **45 días calendario** para completar la validación en entorno local antes del despliegue de la etapa 2.

## 2. Acuerdos y decisiones

1. **DEC-01 — Índice vectorial:** Migrar `document_embeddings` a índice `HNSW` con métrica coseno (`vector_cosine_ops`) y conservar la dimensión de 384 para `multilingual-e5-small`.
2. **DEC-02 — Retención de originales:** Mantener la retención de archivos originales durante **180 días** tras el archivado de un proyecto sintético, con verificación de integridad por `SHA-256`.
3. **DEC-03 — Tope de exportación:** Limitar la exportación PDF a **25 MB** por documento y registrar cada descarga en el historial privado del usuario.

## 3. Tareas asignadas

| ID | Tarea | Responsable | Fecha compromiso |
| --- | --- | --- | --- |
| T-101 | Preparar migración SQL idempotente para HNSW y FTS | Operador Uno | 2026-05-01 |
| T-102 | Definir suite adversarial contra inyección en documentos | Analista Dos | 2026-05-08 |
| T-103 | Validar accesibilidad WCAG AA de la vista de fuentes | Coordinadora Tres | 2026-05-15 |

## 4. Glosario operativo

- **Recall@K:** Proporción de fragmentos relevantes recuperados dentro de los primeros `K` resultados.
- **Groundedness:** Porcentaje de afirmaciones factuales respaldadas directamente por una cita verificable en los fragmentos autorizados.
- **STALE:** Estado de un artefacto derivado cuando uno o más documentos fuente han sido modificados o eliminados.

## 5. Riesgos y pendientes

- No se definió aún el presupuesto de tokens diarios por empresa; queda pendiente para la sesión del 2026-05-20.
