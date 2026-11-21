# Obsidian y fuentes Markdown — opciones y matriz de decision

> Estado: análisis de planificación (2026-11-21). Decisión consolidada en [roadmap.md](../../../roadmap.md): se adopta únicamente **O1 (Markdown/ZIP genérico)** en Fase 3 (`R3-01`–`R3-04`); O2 queda descartada.

## 1. Que es realmente una boveda Obsidian (investigacion)

Segun la documentacion oficial de Obsidian (https://help.obsidian.md, consultada 2026-11-21):

- Una vault es un **directorio local de archivos Markdown** (`text/markdown`, extension `.md`) con subcarpetas arbitrarias; no hay base de datos obligatoria. Metadatos locales de la app viven en `.obsidian/` (workspace, plugins, temas) y deben excluirse de la ingesta.
- **Frontmatter YAML** al inicio (`--- ... ---`): `tags`, `aliases`, `cssclasses`, propiedades personalizadas (Bases/Dataview).
- **Wikilinks** `[[Nota]]`, `[[Nota#Encabezado]]`, `[[Nota#^bloque-id]]`, `[[Nota|alias]]`; enlaces markdown equivalentes `[texto](nota.md)`; enlaces a adjuntos `![[imagen.png]]`; **transclusiones** `![[Nota#Seccion]]` que duplican contenido de otra nota en la vista (el archivo fuente sigue siendo uno solo).
- Tags `#etiqueta` anidados con `/`; backlinks calculados por la app; **Canvas** son archivos `.canvas` JSON con nodos/enlaces; bases `.base` (funcion reciente) en YAML.
- **No existe API remota oficial universal**: el servidor de sincronizacion de Obsidian es privativo y cerrado; las vias de acceso programaticas reales son (a) sistema de archivos local, (b) URI scheme `obsidian://` (abre la app local, no expone datos), (c) plugins comunitarios (Local REST API, etc.) de terceros sin garantia de estabilidad, (d) MCP servers comunitarios para Obsidian (no oficiales). Asumir "conector API Obsidian" como equivalente a Drive sera falso.
- Renombrar/mover dentro de Obsidian reescribe wikilinks entrantes; desde fuera (nuestra ingesta) un movimiento se ve como borrado + creacion → la sincronizacion incremental debe tolerar renombres por hash de contenido, no solo por ruta.

### Restricciones practicas del entorno
- **Navegador**: `<input type="file" webkitdirectory>` permite seleccionar carpetas pero sube todo (sin watch), y la File System Access API (Chrome/Edge) da lectura persistente con permiso por sesion/descarga; Safari/Firefox tienen soporte parcial. Ningun navegador puede "montar" ni vigilar una vault completa de forma fiable multiplataforma. Conclusión: la carga por navegador sirve para **importaciones puntuales (ZIP o carpeta)**, no para sincronizacion viva.
- **Docker**: montar la vault del host como volumen solo lectura funciona distinto por SO (bind mounts Linux directos; Docker Desktop macOS/Windows con File Sharing configurado y rendimiento inotify limitado; paths con espacios/unicode). Un conector "carpeta montada" acopla la instalacion al host y complica `docker compose up` portatil. Debe ser opcional y deshabilitable.
- Licencias: Obsidian es software **propietario gratuito para uso personal** (no open source); su formato .md es abierto. Interactuar con archivos .md no crea dependencia de licencia de Obsidian; los plugins/MCP comunitarios exigen revisar su propia licencia antes de empaquetar nada (no empaquetarlos en la imagen).

## 2. Opciones comparadas

Definiciones ajustadas al repo:

- **O1 — Markdown/ZIP generico**: mejorar ingesta existente: normalizar frontmatter (extraer a metadata del documento, no al texto vectorizado), conservar cuerpo, resolver `[[wikilinks]]` a nivel de enlace simple, aceptar `.zip` de una vault con limites duros (tamano descomprimido, ratio, nº entradas, rechazo de symlinks/rutas absolutas/`..`), y metadatos de origen (`source_kind: markdown_zip|upload`, `source_path_rel`, `content_sha256`). Todo dentro de `RagDocumentEmbeddingServices` + un endpoint "importar lote" idempotente.
- **O2 — Conector nativo Obsidian (solo lectura)**: concepto "Fuente documental" con sincronizacion incremental por manifiesto (lista de `(ruta_rel, sha256, mtime)`); transporte posible: subida manual del ZIP/breve folder-picker (mismo mecanismo O1) o montaje de carpeta RO. Incluye exclusion de `.obsidian/`, deteccion de renombres por hash, y politicas de borrado (archivos desaparecidos → desindexar conservando original hasta purga).
- **O3 — MCP externo de Obsidian**: usar un servidor MCP comunitario (por ejemplo "mcp-obsidian" contra el plugin Local REST API) a traves de un cliente MCP futuro (evaluación diferida a `R5-05` en [roadmap.md](../../../roadmap.md)). La plataforma no conoce Obsidian: conoce un tool `search/read vault`. Autenticacion/token del plugin vive en la config del servidor MCP externo, no en nuestra BD (o en `tenant_integrations` si un ADR futuro decide centralizar secretos de conectores).
- **O4 — Hibrída progresiva**: O1 ahora (generico, barato, util para cualquier app Markdown: Obsidian, Logseq, Joplin, repos Git con docs), O3 cuando el plan MCP este maduro para usuarios avanzados, y O2 **solo si** la demanda exige sincronizacion continua nativa.

## 3. Matriz de decision

Escala cualitativa: ● favorable / ◐ aceptable / ○ desfavorable. Coste estimado S/M/L = esfuerzo de ingenieria sobre este repo.

| Criterio | O1 Markdown/ZIP | O2 Nativo Obsidian | O3 via MCP | O4 Hibrida |
| --- | --- | --- | --- | --- |
| Esfuerzo inicial | S | L | M (depende de ADR MCP `R5-05`) | S inicial, crece por fases |
| UX primera vez | Subir ZIP/carpeta, entender hoy mismo | Alta pero con setup (montaje/exclusiones) | Requiere instalar plugin+servidor MCP | Igual O1, mejora despues |
| Autenticacion | Ninguna (archivo local) | Ninguna o credenciales montaje host | Token del plugin Local REST API (superficie nueva) | Minima |
| Instalacion/Compose | Sin cambios | Volúmenes RO por SO, UID/GID (precedente `EMBEDDING_UID`) | Servicio extra del usuario fuera de nuestro stack | Sin cambios |
| Licencias | Solo formato abierto | Formato abierto; Obsidian propietario (no se redistribuye) | Depende de licencias de terceros (revisar cada repo) | Limpiar |
| Mantenimiento | Bajo (extractor ya existe) | Alto (evoluciona el ecosistema, Canvas/.base, heurísticas de renombre) | Medio (contrato MCP futuro en `R5-05`) | Acotado por fases |
| Fiabilidad | Determinista (lote puntual) | Media (sync parcial, relojes, unicode) | Variable (plugin de terceros, vault cerrada) | La de O1 al inicio |
| Trazabilidad | `source_*` + hash por archivo | Idem + estado de sync | Resultado del tool remoto; procedencia mas difusa | Idem |
| Portabilidad (otra app md) | Total | Baja (concepto vault-specific casi inexistente en realidad) | Media (MCP genérico sí) | Total |
| Compatibilidad Docker | Excelente | Aceptable con advertencias | Buena (red) pero SSRF/allowlist | Excelente |
| Sincronizacion incremental | No (v1; re-import por hash) | Si (manifiesto) | Segun tool remoto | Despues de O1 |
| Borrado/coherencia | Manual por documento | Reglas de desindexar/purgar | Riesgo de obsolescencia de contexto | Progresivo |
| Aislamiento multi-tenant | Igual que upload actual | Fuente ligada a tenant+owner | **Cuidado**: resultados MCP deben pasar filtro de acceso propio | Idem |
| Velocidad/coste runtime | CPU local E5, cero API | Idem + jobs de diff | Latencia red externa | Idem |

## 4. Recomendacion explícita

1. **Construir ahora: O1** (fuente Markdown/ZIP generica con metadatos de origen y normalizacion de frontmatter/wikilinks como enlaces, no como texto basura). Cubre el caso Obsidian real ("tengo mi vault y quiero consultarla") sin prometer sincronizacion viva, sirve a Logseq/Joplin/Git docs y reaprovecha todo el pipeline verificado de ingesta. El esfuerzo esta dominado por: extractor `MarkdownNormalizer`, endpoint de importacion por lote idempotente (hash de contenido como clave natural), validacion defensiva de ZIP (bombas, symlinks, rutas, tamano, encoding) y UI "Fuentes y conectores > Importar Markdown".
2. **Preparar el terreno para O3 mediante contratos futuros (`R5-05` en [roadmap.md](../../../roadmap.md))** (registro de fuentes/conectores con estados `available|experimental|proposal`, y requisito duro: todo resultado recuperado por un conector pasa por `_apply_access_filter`-equivalente antes de entrar a contexto de Groq). No construir el cliente MCP aqui.
3. **Posponer O2 (conector nativo Obsidian) indefinidamente salvo evidencia**: si tras O1+O3 aparecen tickets de sincronizacion continua y montajes, se re-evalua; Obsidian no aporta hoy capacidades que Markdown+MCP no cubran, y su "API" no es oficial. **No implantar Obsidian de forma predeterminada.**
4. Cualquier opcion debe **separar metadatos de origen** (`documents.metadata.source = {kind, path_rel, sha256, imported_via, batch_id}`) **del original ingestado** (volumen de originales intacto, politica de retencion identica a upload) y respetar el alcance autorizado del usuario que importa (su tenant/area/grupos, igual que `build_document_access_metadata` hoy).

## 5. Pruebas propuestas (fixtures sinteticos)

- Vault sintetica versionada en `tests/fixtures/obsidian-mini/`: notas con frontmatter completo, wikilinks rotos/validos, transclusion, alias, tags anidados, adjunto png, `.canvas`, `.obsidian/` a excluir, nombres con unicode/espacios, symlink malicioso y zip con `../entry` (deben rechazarse), archivo >20 MiB y zip-bomba pequeno (deben rechazarse con error tipificado).
- Casos de ingesta: misma vault importada dos veces → 0 duplicados (idempotencia por `content_sha256` + `batch_id`); nota renombrada con contenido identico → re-vinculada, no duplicada; nota eliminada entre imports → marcada `stale` y desindexada bajo aprobacion explicita del usuario.
- Casos de recuperacion: pregunta que depende de una transclusion responde con la fuente primaria citada (no la copia); pregunta multi-hop entre dos notas → evaluada sobre el corpus sintético `S3` (`R0-04` en [roadmap.md](../../../roadmap.md), donde los wikilinks actúan como grafo explícito de enlaces).
- Multi-tenant: usuaria B del mismo tenant sin acceso a la carpeta destino no recupera fragmentos de la vault de A (mismo test pattern que `test_document_access.py`).
- UI: subir ZIP invalido muestra errores por archivo (no uno global); progreso por lote con conteos `creados/reutilizados/rechazados`.

## 6. Descartes justificados

- **Plugin/agente residente en el navegador vigilando la vault**: APIs de archivos insuficientes cross-browser; complejidad alta para ganancia marginal frente a importar lote.
- **Sincronizacion bidireccional o escritura de vuelta a la vault**: riesgo de corrupcion de datos del usuario, conflicto con Obsidian Sync, y superficie de seguridad injustificada para un producto RAG de consulta.
- **Depender de plugins comunitarios concretos empaquetados**: licencia y mantenimiento de terceros; mejor evaluar protocolo MCP estandar en un ADR dedicado (`R5-05`) donde el usuario trae su servidor.
- **Tabla nueva `obsidian_vaults` dedicada**: prematuro; el modelo generico "document source/import batch" cubre también Drive futuro y CSV.

## 7. Enlaces de referencia (consultados 2026-11-21)

- Obsidian Help (formato, frontmatter, links, transclusion, Canvas): https://help.obsidian.md/
- Plugin comunitario Local REST API (base de muchos MCP Obsidian; no oficial): https://github.com/coddingtonbear/obsidian-local-rest-api
- Servidores MCP comunitarios para Obsidian (ejemplo ecologico, no recomendacion): https://github.com/MarkusPfundstein/mcp-obsidian
- File System Access API (MDN): https://developer.mozilla.org/en-US/docs/Web/API/File_System_API
- Docker Compose volumes/bind mounts multi-SO: https://docs.docker.com/compose/how-tos/start-with-containers/ y https://docs.docker.com/desktop/features/file-sharing/
