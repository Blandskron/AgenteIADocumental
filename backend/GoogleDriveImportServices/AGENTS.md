# Trabajar en GoogleDriveImportServices

Lee [README.md](README.md), [ROADMAP](../../ROADMAP.md#googledriveimportservices) y [AGENTS raíz](../../AGENTS.md). DRIVE-001 es diagnóstico: sus propuestas no son garantías implementadas. Retoma En curso o elige Lista; conserva el ID y evidencia del incremento. Los paquetes propuestos no eliminan criterios de aceptación.

## Fronteras y contratos

- Auth es dueño de identidad, huella, actividad, tenant y permisos. No asumir que verificar firma basta para revocación ni aceptar identidades por username/sub/unknown. El contrato use_google_drive y conexión global/tenant debe ser explícito con sus consumidores.
- Revisa juntos schemas/rutas, ManageGoogleDriveImports, repositorio/cifrador/cliente Google, SQL, Compose y web: ApplicationsPage, DocumentSearchPage, AuthProvider, google-drive-import API y Picker. Los cambios de callback, páginas o estados exigen despliegue conjunto y pruebas de ambas páginas.
- Callback solo de un intento iniciado y ligado a usuario/navegador, aleatorio, corto y de un uso; validar/consumir antes de canjear. No inferir propiedad del state JSON ni convertir return_url en redirección libre. Verificar PKCE y coherencia de cuenta/cliente con el flujo Google realmente elegido.
- Tokens/client secrets/clave de cifrado nunca en DTO, logs, capturas o fixtures. No usar fallback/ejemplos para grants reales. Inventariar versiones y planear rotación/reautorización; no recifrar, revocar ni borrar conexiones existentes indiscriminadamente. Tratar refresh/reconnect/omisión de refresh/invalid_grant como transiciones diferentes.
- Ingesta posee permiso upload_documents, metadata de identidad y procesamiento. No confiar en metadata del cliente como autoridad. XLSX/PPTX no son formatos admitidos por su contrato actual: elegir conversión compatible o rechazar explícitamente. El máximo downstream no limita la memoria de descarga Drive.
- Acotar cuerpo, campos, metadata, lote, bytes reales, tiempo y concurrencia antes de coste remoto. No truncar silenciosamente el lote. En streaming/export contar bytes aunque falten o mientan tamaño/headers, sin fetch a URLs suministradas por el usuario.
- Library conserva el protocolo de locks por dueño/documento y carpeta/ancestros. Comprobar propiedad antes de Google y al asociar; no mantener locks durante descarga/upload. Preservar documento e ID si falla solo la asociación. No repetir uploads completados o ambiguos: idempotencia de asociación no equivale a idempotencia de importación.
- Estado y recuperación deben distinguir fallo conocido, upload confirmado y resultado ambiguo; no dar FAILED a un documento ya creado ni dejar RUNNING sin política. Cuotas, versión y clave de operación necesitan coordinación SQL, no solo flags en memoria.
- `docs/` contiene documentación/evidencia; código mantenido en app/tests y scripts de mantenimiento en scripts/. Conservar esquema, migradores y fuentes de evidencia hasta reemplazo probado. No añadir un plan duplicado del roadmap.

## Verificación

- Solo proveedores/transportes, documentos y claves sintéticos por defecto. No leer ni montar .env, documentos, grants o credenciales personales para probar errores. OAuth real requiere una tarea expresamente autorizada y un proyecto/cuentas de desarrollo.
- Usa un proyecto/volumen PostgreSQL dedicado y .env.example. Ejecuta drive-tests y Ruff según README; confirma limpieza SQL. Las nueve pruebas históricas solo cubren coordinación de carpetas y parciales; ampliar HTTP/identidad/OAuth/transporte/estados/concurrencia conforme cambie el código.
- JWT reales de dos usuarios/tres roles, revocación, permisos/tenant, state ausente/ajeno/vencido/reutilizado, callbacks concurrentes y refresh/reconnect. Asegurar que un rechazo no llama Google ni pierde la conexión previa.
- Cubrir límites binarios/nativos y encabezados falsos, reintentos, fallo DB/proveedor/upload ambiguo, cancelación/reinicio y archivos temporales. Pruebas web Node/Chromium, sesión estable durante refresh, cuenta/tenant/desmontaje y accesibilidad cuando se toquen consumidores.
- Compose config desde raíz; provisión de rol repetible y login real/SQLSTATE negativos. Arranque nuevo y actualización sobre volumen existente; no presentar SET ROLE desde administrador como prueba de login restringido.
- Auditar inventario runtime, SO y copias vendorizadas por separado, identificando imagen/digest exactos. No atribuir un target test al runtime ni un escaneo Python a la imagen completa; registrar alertas y diferencias entre proveedores sin supresiones.
- Actualiza README/tablero con comandos, contratos y evidencia real. En revisión al entregar; Hecha solo al integrar y satisfacer criterios. El cierre Drive no cierra PLAT-001, WEB-001, PLAT-002 ni DEMO-001.
