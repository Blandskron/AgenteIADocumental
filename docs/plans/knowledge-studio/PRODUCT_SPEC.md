# PRODUCT_SPEC — Knowledge Studio

> Estado: especificación de planificación (2026-11-21). Alcance adoptado en [roadmap.md](../../../roadmap.md): **P0** en Fase 4 (`R4-01`–`R4-06`), **P1** evaluable en Fase 5 (`R5-03`–`R5-04`) y elementos multimedia descartados.

Depende de la configuración de IA por tenant (Fase 1, implementada en `AuthServices` y `RagDocumentChatServices`) para credenciales LLM y de **DocumentSearch/Library/Access** para permisos. No introduce dependencias de NotebookLM, Obsidian ni servicios externos obligatorios.

## 1. Problema del usuario

Hoy la plataforma responde preguntas sobre documentos (chat RAG) y exporta esa conversación a PDF. Lo que no puede hacer: convertir un conjunto autorizado de documentos en **artefactos reutilizables** (informe, tabla comparativa, quiz, mapa, lista de tareas) con evidencia verificable, guardados, versionados y exportables. El usuario actual repite trabajo manual después del chat.

## 2. Alcance / no alcance

### Alcance (por fases)
- **P0**: Colecciones; resúmenes (ejecutivo, por secciones, comparativo); informes plantillados (técnico, memo, guía de estudio, glosario, FAQ, minuta, riesgos); tabla de evidencia con export CSV; tareas propuestas con revisión humana. Todos los artefactos con citas a fragmentos o marcado explícito de inferencia/laguna.
- **P1**: Mapas mentales/conceptuales (datos estructurados + render determinista), cronologías y diagramas Mermaid sanitizados, gráficos desde cifras verificadas, quizzes y flashcards con modo práctica/evaluación, diapositivas editables → PPTX/PDF.
- **P2 (experimental, feature flags)**: guion de audio + TTS local opcional; agente de investigación multi-paso con presupuesto y alcance cerrado; DOCX/XLSX si la demanda lo justifica.

### No alcance (explícito)
- Video-resúmenes, infografías generadas por IA de imágenes, búsqueda web como requisito base, clonado de voz, sharing público anónimo, ejecución automática de acciones sobre sistemas terceros, paridad con NotebookLM.

## 3. Conceptos y UX textual

### 3.1 Flujo maestro
`Fuente(s) → Selección autorizada → Tipo de artefacto → Opciones → Previsualización → Validación de evidencia → Guardar → Exportar/Compartir`

Recorrido verificable (ruta UI propuesta dentro del frontend Feature-Sliced existente):
1. **Biblioteca → "Nueva colección"**: el usuario agrupa documentos existentes (multi-selección). La colección guarda `document_id + content_version/sha`, nunca copia binarios. Visibilidad: privada / empresa / área (mismos ejes que `DocumentLibraryServices`).
2. **Studio (`/studio`)**: página nueva con dos pestañas — *Generar* y *Mis artefactos*. Vacío inicial con CTA "elige una colección".
3. **Generar**: elegir plantilla (resumen ejecutivo…) → opciones (longitud, idioma salida, audiencia, incluir/no incluir tareas) → botón "Vista previa" crea un **job**; progreso con pasos (`retrieving → drafting → citing → validating → done`) paginado por polling (mismo patrón que el estado de importaciones Drive).
4. **Previsualización**: Markdown renderizado; cada afirmación con `[n]` clicable abre panel lateral con el chunk original, documento, página/índice y score. Los enunciados sin cita se muestran con badge ámbar "inferencia" y los huecos con badge gris "sin fuente".
5. **Guardar** → versión 1 del artefacto en la biblioteca de artefactos. **Regenerar** crea v2 conservando v1. **Exportar** (MD/PDF/CSV según tipo) materializa un export inmutable con sha256 y caducidad (patrón `manage_exports.py`).
6. **Compartir**: solo lectura para usuarios que ya tienen acceso a TODAS las fuentes citadas; si alguien pierde acceso a una fuente, el artefacto deja de listarse para esa persona (no se filtran títulos ni recuentos).

### 3.2 Estados de pantalla (obligatorios en todas las vistas)
- **Vacío**: explicación + acción única ("Crear colección", "Generar primer artefacto").
- **Loading**: job con progreso por pasos y ETA estimada; cancelable.
- **Fallo**: causa legible (p. ej. "Groq no configurado", "Las fuentes superan el presupuesto de contexto: reduce la selección o usa resumen por secciones"), acciones reintentar/ajustar/cancelar. Sin clave en mensajes.
- **Degradado honesto**: sin Groq configurado → las funciones de generación muestran banner "Configura un proveedor de IA en Configuración > IA"; las funciones NO-LLM (ver tabla de evidencia guardada, mapas manuales, práctica de quizzes guardados) siguen operativas. Embeddings locales y búsqueda nunca dependen de Groq (invariante de Fase 1).

### 3.3 Editor ligero
Artefactos guardados son editables en Markdown con editor simple (textarea + preview, sin WYSIWYG completo). Reglas:
- Editar **no** borra citas originales; los segmentos editados conservan sus `[n]` salvo que el usuario los elimine.
- Si el texto editado elimina el anclaje de una cita, esa cita pasa a estado `detached` y se muestra advertencia al exportar ("N afirmaciones sin verificación de fuente").
- Versionado: cada guardado = versión inmutable; diff entre versiones en P1.

### 3.4 Métricas de utilidad (instrumentación desde P0)
Tiempo hasta primer artefacto; tasa de finalización de jobs (done/failed/cancelled); nº exportaciones por artefacto; % de sugerencias de tarea aceptadas; errores de cita detectados en validación (groundedness fail rate); p50/p95 latencia por plantilla; tokens y coste estimado Groq por artefacto; CPU/RAM del worker; feedback 👍/👎 por artefacto (tabla nueva, sin telemetría externa).

## 4. Funcionalidades priorizadas (tabla de decisión)

| # | Funcionalidad | Equivalente conceptual ref. | Valor usuario | Dificultad | Coste extra | Dep. externa | Reutilización actual | ¿Necesita citas? | Riesgo alucinación | Propuesta |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Resúmenes inteligentes (ejecutivo/secciones/comparativo) | NotebookLM summaries | Alto (todos los perfiles) | Baja-media | Tokens Groq | Ninguna (Groq ya es provider del chat) | Context builder de `RagDocumentChatServices`, búsqueda de `DocumentSearchServices` | Sí, obligatorias | Medio → validado con groundedness | **P0** |
| 2 | Reportes estructurados plantillados (informe, memo, guía, glosario, FAQ, minuta, riesgos) | Study guide / report | Alto | Media (plantillas+schemas) | Tokens | Ninguna | Ídem + `DocumentExportServices` (patrón) | Sí | Medio | **P0** |
| 3 | Tabla de evidencia y comparación + CSV | Data table | Alto (analista/abogado) | Media | Bajo | Ninguna | Chunks existentes | Sí (celda→fragmento) | Bajo-medio (validación schema) | **P0** |
| 4 | Tareas propuestas con revisión humana | (no existe en NLM; valor propio) | Alto equipos | Media | Bajo | Ninguna; gestores externos solo vía ADR MCP futuro (`R5-05`) | Conversaciones como fuente | Sí | Medio; mitigado por aprob. humana | **P0** |
| 5 | Quizzes + flashcards | Flashcards/quiz | Alto educativo+legal | Media | Tokens | Ninguna | Plantillas + almacenamiento local | Sí (explicación citada) | Medio (respuesta única verificada por schema) | **P1** |
| 6 | Mapas mentales/conceptuales | Mind map | Medio | Media-alta | Bajo | Ninguna | Nuevo slice frontend reactflow/Mermaid | Enlaces a docs | Bajo (estructura, no hechos nuevos) | **P1** |
| 7 | Diagramas, cronologías, charts | – | Medio | Media | Bajo | Ninguna | Render cliente determinista | Procedencia por dato |charts: bajo si datos citados | **P1** |
| 8 | Diapositivas MD→PPTX/PDF | Slide deck | Medio | Alta | python-pptx | Ninguna | Renderer nuevo; PDF vía patrón exports | Sí | Alto → edición obligatoria pre-export | **P1 tardío** |
| 9 | Audio resumen (guion + TTS) | Audio Overview | Medio | Alta | Motor TTS local/voces | Opcional (proveedor TTS) | Guion = plantilla texto | Guion citado | Medio | **P2 flag** |
| 10 | Video-resumen / infografía neuronal | – | Bajo-medio | Muy alta | GPU/modelos | Obligatoria de calidad | Ninguna | N/A | Alto | **Descartar** |
| 11 | Deep research multi-paso | Deep Research | Medio | Alta | Coste LLM alto | Ninguna obligatoria | Búsqueda + jobs | Sí | Alto | **P2 experimental** |
| 12 | DOCX export | – | Bajo por mercado objetivo | Media | python-docx | Ninguna | Renderer nuevo | – | Bajo | **P2 (demanda)** |

**Máximo 5 para la primera entrega**: (1) Resúmenes, (2) Reportes plantillados, (3) Tabla de evidencia+CSV, (4) Tareas propuestas, (5) Colecciones+infraestructura de jobs/export (habilitadora de las cuatro anteriores). **NO implementaría en la próxima versión**: diapositivas PPTX y audio TTS — coste alto de calidad/licencias frente a demanda incierta, y ambos pueden ofrecerse después sobre los mismos artefactos de texto sin rediseñar nada.

## 5. Permisos y seguridad funcional

- Autorización **antes** de recuperar fragmentos: toda generación empieza validando acceso (empresa/área/usuario vía `DocumentAccessServices`) a cada fuente seleccionada; el resultado de búsqueda ya filtra por permisos (`search_documents.py`).
- Un artefacto pertenece a tenant+owner; compartirlo exige revalidar acceso total a las fuentes en cada lectura (no se cachean permisos).
- Prompt injection documental: los chunks viajan siempre como *data* en el bloque de contexto con instrucciones del sistema separadas (extiende `_system_prompt` de Groq provider); las plantillas prohiben ejecutar instrucciones contenidas en fuentes; los artefactos se renderizan en frontend con sanitización (Markdown→DOM con rehype-sanitize; SVG solo tras saneado; Mermaid `securityLevel: 'strict'`).
- Exportaciones seguras: sin macros (OOXML generado programáticamente, nunca plantillas con VBA), nombres de archivo slugificados (patrón `_slug` en exports), límites MAX_PDF y capacidad heredados del módulo de exports.
- Auditoría: eventos `artifact.created/exported/deleted`, `job.finished` con ids, nunca contenido ni secretos.
- Nada de Studio escribe en sistemas externos; las tareas propuestas son datos locales hasta que un humano las aprueba; cualquier acción externa futura (MCP, `R5-05`) requiere confirmación interactiva auditada.

## 6. Historias de uso (fixtures sintéticos, sin sesgo educativo exclusivo)

1. **Estudiante**: sube apuntes PDF → colección "Tema 4" → guía de estudio + quiz de 10 preguntas con explicación citada → practica offline; exporta la guía a PDF antes del examen.
2. **Investigador**: 30 artículos Markdown (vía importación Markdown/ZIP de Fase 3) → tabla de evidencia (método, muestra, resultado, año) filtrable → mapa conceptual de autores→hallazgos → informe comparativo con `[n]` por afirmación.
3. **Abogado**: contrato + anexos + correos → minutas con cláusulas citadas por página → tabla de plazos/obligaciones → lista de tareas propuestas ("solicitar anexo 3") que **solo** se convierte en acción externa si el usuario la confirma vía MCP.
4. **Analista**: informes trimestrales → extracción de métricas a tabla con unidad y procedencia por celda → gráfico de líneas generado **desde la tabla verificada** (nunca desde texto libre) → memo ejecutivo.
5. **Equipo de empresa**: actas de reuniones → FAQ interna + glosario compartido por área → tareas con responsable explícito vs inferido (badges distintos) → export CSV al gestor que ya usan.

## 7. Integraciones futuras sin acoplamiento

- **MCP (`R5-05` en [roadmap.md](../../../roadmap.md))**: herramientas de solo lectura propuestas (`studio.list_artifacts`, `studio.get_artifact`, `studio.generate_draft`) derivan permisos del **token del usuario autenticado en la plataforma**, jamás del cliente MCP; las herramientas de escritura (crear tarea en gestor externo) quedan fuera hasta tener confirmación interactiva auditada.
- **Grafos / enlaces explícitos (`R3-02` / `R5-03`)**: los mapas conceptuales P1 usan enlaces explícitos/`[[wikilinks]]` y tablas de evidencia; una eventual expansión multi-hop futura no cambia los esquemas de artefacto (la procedencia ya está diseñada en [ARTIFACT_SCHEMAS.md](ARTIFACT_SCHEMAS.md)).
