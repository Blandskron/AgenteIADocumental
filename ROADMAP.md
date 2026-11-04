# Blandskron Documental · Tablero de trabajo

El objetivo es una demo de portafolio que permita subir un documento sintético, encontrarlo, conversar con él y exportar la conversación. El nombre público propuesto es **Blandskron Documental** y el identificador técnico, `blandskron-documental`.

## Kanban

Mantener una sola tarjeta **En curso**. Moverla a **En revisión** con evidencia y a **Hecha** cuando cumpla su criterio de aceptación. Una dependencia pendiente mantiene la tarjeta en **Backlog** o **Bloqueada**.

| Estado | ID | Entrega | Depende de |
|---|---|---|---|
| Hecha | BD-000 | Tablero y guía de colaboración | — |
| En revisión | BD-001 | Inventario interno de marca y material publicable | — |
| Hecha | BD-002 | Definir la vía y el alcance de publicación | — |
| En curso | BD-003 | Fijar la base y comprobar que arranca | BD-002 |
| En revisión | BD-004 | Aplicar la identidad Blandskron | BD-001, BD-003 para validación integral |
| En revisión | BD-005 | Migrar el chat a Groq | Recorrido RAG con el stack |
| En revisión | BD-006 | Separar embeddings de Azure | Prueba real del modelo, migración y reindexación |
| En curso | BD-007 | Automatizar la validación del recorrido | BD-006 para la prueba integral |
| Backlog | BD-008 | Preparar la entrega de portafolio | BD-007 |

## Etapa 0 · Alcance e inventario

**Evidencia de BD-001.** La búsqueda `git grep -ilE '<marcas anteriores>' <rama>` encontró coincidencias en 76 archivos de `main` y 33 de la rama documental. `git ls-tree -r --name-only <rama>` detectó nombres de recursos gráficos y archivos subidos. `git log --all --format=%h --regexp-ignore-case '-G<marcas anteriores>' --` encontró 32 commits con cambios textuales relacionados en las referencias locales.

| Rutas o material | Tratamiento propuesto |
|---|---|
| `frontend/index.html`, `src/shared/components/Brand/`, chat, búsqueda, perfil, barra lateral y aplicaciones | Reemplazar identidad y textos visibles. Revisar menciones a la empresa de la prueba técnica en `AdminPage.jsx` y distinguir atribución de texto de producto. |
| `frontend/<logo anterior>`, `frontend/public/<logo mini anterior>`, `frontend/public/<logo anterior>`, favicons y `frontend/logo.png` | Reemplazar los logos identificados. Inspeccionar visualmente los favicons y el logo genérico para decidir si se reemplazan o excluyen. Revisar por separado los logos de Drive y SharePoint como recursos de terceros. |
| `frontend/src/entities/{auth,conversation}/`, `ThemeProvider.jsx`, `package*.json`, scripts de entrada y configuración del frontend | Reemplazar identificadores. Decidir compatibilidad de almacenamiento del navegador según el entorno de destino. |
| `backend/RagDocumentChatServices/`, `backend/DocumentExportServices/`, `backend/AuthServices/`, `backend/GoogleDriveImportServices/` | Reemplazar marca en prompts, PDF, configuración y documentación. Verificar PDF y chat con datos sintéticos. |
| `.env.example`, `docker/`, `scripts/database/` y `README.md` | Reemplazar nombres técnicos y de producto. Revisar nombres de bases, volúmenes y configuración antes de aplicarlos sobre instalaciones existentes. |
| `backend/<servicio de agentes retirado>/`, `backend/WhatsAppIntegrationServices/`, `backend/AgentOrchestrationServices/` y otros módulos ajenos al flujo documental | Excluir de la entrega documental. La rama documental ya los retira. |
| `uploads/profile/` | Excluir los archivos subidos de la entrega. Dos están versionados en `main`; el directorio también aparece en el historial local. |
| `LICENSE`, atribuciones, commits y otros metadatos históricos | Preservar atribuciones aplicables y revisar autorización. Definir el historial compartible en BD-002 antes de preparar la entrega. |

El barrido es interno. La inspección visual de recursos genéricos sigue pendiente. La revisión exhaustiva del historial y credenciales corresponde a BD-008.

**Verificación de recursos.** En la rama documental, `frontend/public/favicon.ico` y `frontend/public/<logo mini anterior>` apuntan al mismo blob. El favicon público entra en el reemplazo de marca por identidad de contenido. El favicon de la raíz de `frontend/` es un blob distinto y queda pendiente de inspección. Las copias raíz y pública de `<logo anterior>` también son idénticas y ambas entran en el reemplazo.

- **BD-001 · Inventario.** Revisar ambas ramas y registrar rutas, tipo de referencia y tratamiento propuesto. Incluir texto, nombres de archivos, recursos visuales, PDF exportado, configuración, almacenamiento del navegador, archivos subidos e historial. **Aceptación.** Cada hallazgo queda clasificado como reemplazar, excluir, preservar por atribución o revisar autorización. Registrar rutas y categorías sin copiar valores sensibles.
- **BD-002 · Vía de publicación.** Blandskron confirmó que creó este código como prueba técnica y que el código de la empresa de la prueba técnica vive en sus propios repositorios. Se reutilizará la base documental para el portafolio. El archivo `LICENSE` identifica a Blandskron como titular y reserva los derechos mientras se decide la licencia de distribución. La revisión de recursos de terceros, atribuciones e historial forma parte de BD-008.

## Etapa 1 · Base e identidad

**Evidencia de BD-004.** Se reemplazaron marcas de producto en frontend, configuración, Docker, documentación, prompt y exportación PDF. Se retiraron los logos anteriores y se creó un SVG documental para icono y favicon. El espacio de nombres del navegador cambia para iniciar una demo limpia. Pasaron el build, Compose config y la búsqueda de nombres anteriores en el build. Quedan por verificar el login y el PDF generado con el stack en marcha. El inventario interno conserva los nombres históricos como evidencia de revisión.

**Preparación de BD-003.** El clon mantiene la relación de 0 commits exclusivos de `main` y 11 exclusivos de la rama documental. Se verificaron los clientes locales Node 24.15.0, npm 11.14.1, Docker 29.9.1 y Compose 5.6.0. El ejecutable `python` detectado apunta al alias de Windows y falló al ejecutarse. La rama local de trabajo es `codex/blandskron-documental`, creada desde `7a22130`. Compose pasó `docker compose -f docker/docker-compose.yml config --quiet` con un `.env` local ignorado, copiado del ejemplo. `npm ci` pasó. El build falla porque falta `frontend/src/features/google-drive-import/lib/google-picker.js`, importado por ApplicationsPage y DocumentSearchPage. La regla general `lib/` de `.gitignore` cubre esa ruta. El motor Linux de Docker Desktop no respondió, por lo que queda pendiente el arranque.

- **BD-003 · Base reproducible.** Partir de la rama documental. La comparación inicial observó `main` en `b20ea4b` y `origin/feature/documentalAi` en `7a22130`, con 0 commits exclusivos de main y 11 de la rama documental. **Aceptación.** Revalidar la relación, registrar el commit base, verificar build y Compose, y arrancar con datos sintéticos. Promover a main tras la revisión.
- **BD-004 · Marca.** Cambiar textos, recursos gráficos y nombres técnicos publicables. Revisar las claves de navegador y definir cómo migrar el estado existente o iniciar una demo limpia. **Aceptación.** Login, chat, favicon y PDF usan la nueva identidad. Una búsqueda de los nombres antiguos en la entrega y una inspección de los recursos visuales confirman la limpieza dentro del alcance aprobado.

## Etapa 2 · IA y recuperación

**Evidencia de BD-006.** Ingesta y chat usan embeddings locales de 384 dimensiones con prefijos `passage:` y `query:`. Se agregó una migración explícita para marcar documentos y reconstruir el índice anterior. Pasaron el análisis de sintaxis Python, pruebas simuladas de los adaptadores, Compose config y la revisión de whitespace. Queda pendiente ejecutar el modelo real y verificar migración, reindexación y recuperación con PostgreSQL activo.

- **BD-005 · Chat con Groq.** Configurar el adaptador de generación con `GROQ_API_KEY` y `GROQ_CHAT_MODEL` en el servidor. **Aceptación.** Una prueba con texto sintético confirma una respuesta en español basada en el documento. La demo presenta errores claros cuando falta configuración o el proveedor falla.
- **BD-006 · Embeddings.** Evaluar un modelo local multilingüe para indexación y consulta. La base actual fija vectores de 1536 dimensiones. **Aceptación.** El esquema y los adaptadores usan la dimensión del modelo elegido, se reconstruye el índice y se verifica la recuperación sobre preguntas conocidas. El recorrido documental arranca y funciona sin credenciales de Azure.

## Etapa 3 · Calidad y entrega

El primer PR se integró en `main`. La API real de Groq respondió correctamente una pregunta en español sobre un contrato sintético. La comprobación se hizo directamente contra Groq y queda por repetir desde el chat. Se agregaron checks de build y Compose para los PR y se alineó la imagen del frontend con Node 24 y el lockfile.

- **BD-007 · CI y prueba integral.** Automatizar build, validación de Compose y el recorrido de login, carga, indexación, búsqueda, chat y exportación. **Aceptación.** Los checks se ejecutan desde una base limpia. Una prueba con dos usuarios demuestra el aislamiento en la recuperación de documentos.
- **BD-008 · Portafolio.** Preparar README con instrucciones verificadas, diagrama breve y una demo con datos sintéticos. Dejar Drive como opcional y describir las integraciones según su comportamiento verificado. **Aceptación.** Otra persona puede seguir el README y completar el recorrido. El contenido e historial a compartir pasan la revisión de permisos, marcas, datos y credenciales. La entrega queda lista para revisión antes de hacerse pública.

**BD-003 · Build restaurado.** Se implementó el selector de Drive en una ruta versionable y se actualizaron sus dos consumidores. Pasaron npm run build, docker compose config --quiet y git diff --check. Quedan pendientes el arranque con Docker Desktop y la prueba OAuth de Drive con una configuración real.

**BD-005.** Adaptador Groq integrado. Validación de sintaxis Python, prueba simulada con contexto sintético y clave ausente, y configuración de Compose correctas. Pendiente una solicitud real y el recorrido RAG con el stack activo.
