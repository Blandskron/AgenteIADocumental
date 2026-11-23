# 04 — Oportunidades de Inteligencia Documental Proactiva

- **Objetivo:** Definir cómo llevar Blandskron Documental desde un buscador/chat reactivo hacia el recorrido estratégico:
  **Documento → conocimiento estructurado → hallazgo verificable → revisión humana → acción autorizada.**
- **Restricción clave:** Separar de forma estricta la **detección automática** (solo lectura, trazable y auditable) de la **ejecución de acciones** (siempre condicionada a revisión y aprobación humana explícita).

---

## 1. Estado real actual (auditoría de código)

Hoy ya existen piezas iniciales en `backend/AgentOrchestratorServices`:

- `app/application/templates/agent_templates.py`: `extract_deterministic_facts()` extrae fechas ISO/LATAM, montos (`USD|US$|EUR|CLP|MXN|ARS|COP|$`) y porcentajes por regex.
- `app/application/analysis/contract_comparator.py`: `compare_contract_clauses()` agrupa citas por documento y clasifica 5 categorías (`penalizacion`, `vigencia_vencimiento`, `monto_pago`, `rescision`, `confidencialidad`) comparando ausencias entre `>= 2` documentos.
- `app/application/analysis/expiration_detector.py`: `detect_expirations()` clasifica fechas en `EXPIRED`, `URGENT_30D`, `UPCOMING_90D`, `FUTURE`.
- `app/application/analysis/risk_assessor.py`: `assess_document_risks()` calcula score heurístico (`LOW`, `MEDIUM`, `HIGH`).
- Endpoint: `POST /api/v1/agents/runs/{run_id}/analyze`.

### Limitaciones comprobadas del enfoque actual
1. **Opera sobre snippets truncados:** `/analyze` procesa `run["sources"]`, cuyos fragmentos están recortados a 300 caracteres, perdiendo cláusulas, fechas y montos que no aparecieron en esos fragmentos.
2. **Efímero y sin persistencia:** Los hallazgos se calculan al vuelo sobre un run y se pierden; no alimentan un calendario de vencimientos, un panel de hallazgos pendientes ni alertas.
3. **Sin procedencia granular:** No asocia cada dato extraído a `page`, `section`, `chunk_index` y `quote_exact` verificable.
4. **Sin comparación de versiones:** Al no existir `document_versions`, no puede comparar `v1` vs `v2` de un mismo documento para detectar cambios de cláusulas o montos.
5. **Desconectado del flujo de acción existente:** `DocumentAccessServices` ya tiene `document_assignments` y `notifications`, pero los hallazgos del analizador no pueden promoverse (tras aprobación humana) a una asignación o recordatorio.

---

## 2. Arquitectura de extracción estructurada con procedencia

### 2.1 Estrategia híbrida en dos capas (compatible con modelos locales pequeños)
1. **Capa 1 — Extracción determinista rápida (CPU, 0 tokens LLM, 100 % offline):**
   - Ejecutable sobre el texto completo estructurado del documento (obtenido vía `DocumentAccessServices /content` o durante post-procesamiento controlado).
   - Detecta fechas (incluyendo expresiones en español como *"15 de marzo de 2027"* y plazos relativos como *"30 días hábiles"*), importes monetarios con divisa normalizada, porcentajes, identificadores fiscales/referencias y palabras clave de cláusulas.
   - Ventaja: funciona incluso en equipos de 4–8 GB RAM sin LLM activo y sirve como validador objetivo frente a posibles alucinaciones del modelo.
2. **Capa 2 — Extracción semántica estructurada (LLM local/opcional + Pydantic v2):**
   - Activable bajo demanda (p. ej. botón *"Extraer ficha estructurada"* o plantilla de agente) sobre documentos específicos.
   - Usa esquemas Pydantic estrictos (`StructuredExtractionResult`) solicitando salida JSON validada por esquema (`response_format` / Ollama `format` JSON schema).
   - **Regla de verificación obligatoria:** Cada campo extraído debe incluir `provenance: {document_id, version_id, page, chunk_index, quote}`. Si `quote` no aparece normalizado en el chunk referenciado, el campo se marca `verification_status = "UNVERIFIED"` y nunca se presenta como dato confirmado.

### 2.2 Contratos Pydantic reutilizables (sin microservicios nuevos)
```text
ExtractedField:
  field_name: str
  value_raw: str
  value_normalized: str | float | date | null
  confidence: "DETERMINISTIC" | "VERIFIED_LLM" | "UNVERIFIED_LLM"
  provenance: { document_id, chunk_index, page, section, quote }

DocumentFinding:
  finding_id: UUID
  tenant_id: UUID
  document_id: UUID
  category: "EXPIRATION" | "OBLIGATION" | "MONETARY_TERM" | "PENALTY" | "CONTRADICTION" | "MISSING_CLAUSE"
  severity: "LOW" | "MEDIUM" | "HIGH"
  title: str
  summary: str
  due_date: date | null
  status: "DETECTED" | "CONFIRMED" | "DISMISSED" | "ACTIONED"
  provenance: list[ProvenanceRef]
  reviewed_by_user_id: str | null
  reviewed_at: datetime | null
```

---

## 3. Oportunidades funcionales de alto valor

### 3.1 Comparación documental real (multi-documento y entre versiones)
- **Caso de uso:** Comparar dos ofertas de proveedores, dos contratos marco o la versión `v1` frente a `v2` de una política interna.
- **Evolución sobre lo existente:**
  - Mantener `compare_contract_clauses()` en `AgentOrchestratorServices` y ampliarlo para leer todos los chunks relevantes (no solo snippets de 300 chars).
  - Incorporar un **diff determinista por sección/párrafo** para comparación de versiones (`v1` vs `v2`) antes de invocar al LLM, reduciendo consumo de tokens y eliminando falsos positivos.
  - Detectar **contradicciones explícitas** (p. ej. plazo de 30 días en cláusula 4 vs 60 días en anexo B) con cita doble `[Doc A, p. 4]` vs `[Doc B, p. 11]`.
  - Exportar la matriz resultante directamente a `KnowledgeStudioServices` (`evidence_table`) o CSV/PDF.

### 3.2 Detección y seguimiento de vencimientos, renovaciones y obligaciones
- **Caso de uso:** Pymes y áreas legales/administrativas que necesitan saber qué contratos vencen en 30/60/90 días, cuáles tienen renovación automática y qué obligaciones periódicas existen.
- **Evolución sobre lo existente:**
  - Reutilizar `expiration_detector.py` sobre el texto completo de documentos marcados o analizados, persistiendo hallazgos en `agents.document_findings` (o `public.document_findings` si se decide exponer sin activar el perfil completo de agentes).
  - Clasificación temporal automática (`EXPIRED`, `URGENT_30D`, `UPCOMING_90D`, `FUTURE`) recalculada determinísticamente por SQL/Python (nunca inventada por el LLM).

### 3.3 Separación estricta: detección → revisión humana → acción autorizada
Para garantizar seguridad y evitar automatizaciones descontroladas:

| Fase | Naturaleza | Responsable | Efecto en el sistema |
|---|---|---|---|
| **1. Detección** | Solo lectura (determinista + LLM opcional) | `AgentOrchestratorServices` | Crea `DocumentFinding` en estado `DETECTED` con citas verificables. |
| **2. Revisión humana** | Decisión explícita del usuario autorizado | Usuario en UI (`Confirmar` / `Descartar` / `Editar`) | Cambia estado a `CONFIRMED` o `DISMISSED` y registra `audit_logs`. |
| **3. Acción autorizada** | Escritura controlada tras aprobación HITL | `DocumentAccessServices` / `KnowledgeStudioServices` | Crea una `document_assignment` con `due_at`, genera `notification` interna o guarda informe en `studio.artifacts`. |

> **Regla de seguridad:** Ningún agente ni analizador puede crear asignaciones, enviar correos, modificar documentos ni disparar webhooks sin que un humano autorizado apruebe la propuesta (reutilizando `agents.agent_approvals` y el patrón `status="proposed"` ya presente en `ProposedTask`).

### 3.4 Esquemas de extracción configurables por empresa (P2)
- Permitir que un `TENANT_ADMIN` defina plantillas ligeras de campos a extraer (p. ej. *"Factura"*: proveedor, RUT/NIF, fecha emisión, fecha vencimiento, monto total; *"Contrato laboral"*: cargo, salario, fecha inicio, periodo de prueba) guardadas en JSONB dentro del tenant, validadas contra un esquema acotado (máx. 20 campos, tipos primitivos `string|number|date|currency|boolean`).

---

## 4. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Falsos positivos en fechas (confundir fecha de firma con vencimiento) | Clasificación contextual (ventana de ±150 chars alrededor de la fecha) + etiqueta de confianza + confirmación humana obligatoria. |
| Coste excesivo de LLM si se analiza toda la biblioteca automáticamente | Análisis **bajo demanda** o solo por carpetas/etiquetas seleccionadas; capa determinista por defecto. |
| Alucinación de montos o penalizaciones en modelos 3B | Verificación estricta de substring (`quote` presente en chunk) y cruce con extractor regex determinista. |
| Fuga de datos entre empresas | Todo hallazgo hereda `tenant_id` y visibilidad del documento fuente; si se revoca acceso o borra el documento, el hallazgo se oculta o elimina en cascada (`ON DELETE CASCADE`). |
