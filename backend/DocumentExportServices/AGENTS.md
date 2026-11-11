# Trabajar en DocumentExportServices

Skill del componente: [documental-export](../../.agents/skills/documental-export/SKILL.md).

Lee el [README](README.md), las [reglas raíz](../../AGENTS.md) y la [verificación de entrega](../../docs/release/README.md). Delimita cada cambio en su PR y conserva los contratos vigentes.

## Límites del servicio

- Export recibe una instantánea de pregunta/respuesta/fuentes; hoy no consulta mensajes, documentos ni LLM. No añadir fetch remoto/HTML activo ni prometer procedencia certificada sin un contrato nuevo.
- La identidad pertenece a Auth. Usa ExportUser canónico y helpers booleanos privados con cuenta activa/huella/locks; no conceder al runtime lectura directa de identidad, referencias o rutas; no reintroducir fallback ni liberar la transacción antes de validar/renderizar/persistir. Ningún rol administrativo debe ampliar acceso a exports ajenos.
- Revisa juntos request/DTO, ManageExports, repositorio, renderer, SQL y consumidores `features/document-export`, ChatPage, ChatMessages y AuthProvider. Las referencias opcionales deben respetar ambos dueños y coherencia antes de renderizar, manteniendo locks. El historial usa cursor por dueño/filtro con desempate; no volver al array sin límites. La web omite IDs locales de mensajes/conversaciones no sincronizados, sin reintentar referencias rechazadas como instantáneas sin vínculo.
- La línea base usaba PDF y fila como dos recursos. El runtime actual guarda bytes acotados y fila juntos en DB; no reintroducir escrituras/descargas por ruta. No borrar fuentes/filas ni reubicar PDFs heredados indiscriminadamente; inventariar/revisar antes de cambiar storage. La migración debe ser dry-run/revisión/checksum y preservar originales, sin fallback que siga enlaces. Cuotas e idempotencia se serializan en SQL, no solo con locks de memoria.
- Usa claves y PDFs sintéticos, directorio/volumen separado y configuración explícita. No montes `documents/exports` real para probar fallos ni vuelques `.env`, JWT, preguntas, respuestas o rutas personales a logs.
- `docs/` conserva evidencia documental, no aplicaciones Python. Mantén pruebas/código en sus ubicaciones propias y conserva migraciones hasta tener un reemplazo probado.

## Verificación y evidencia

- Usa export-tests y export-audit según README. Mantén el worker aislado con deadline/recogida, los límites de páginas/bytes y la licencia/hashes de fuentes; valida contra glifos soportados. La suite completa exige EXPORT_TEST_DATABASE_URL explícita y esquema sintético; para pruebas sin DB usa el marcador not postgres. Agrega pruebas de cada corrección sin conservar expectativas de comportamiento inseguro como garantía. Concurrencia se prueba entre conexiones reales con limpieza verificada.
- Para renderer, genera casos español/Unicode, fuentes y tablas extensas/multipágina; verifica texto y render PNG con Poppler. No basta con que el archivo tenga bytes o comience por %PDF.
- Para frontend, ejecuta npm ci/test/build y las pruebas de navegador aplicables. Para Compose, ejecuta config --quiet desde raíz. Para imagen, distingue dependencias instaladas, SO y vendorizados y registra artefacto/avisos.
- Comprueba cursor/listado y controlador web como contrato conjunto: epoch, abort, sesión estable durante refresh, object URLs en finally y reintentos con misma clave de operación. Para imagen usa audit_image.py/inspect_runtime.py; no montar credenciales o documentos, ni instalar pip/test/audit en runtime para verificarlo. Registra digest e inventario y reevalúa los avisos antes de otro despliegue.
- Actualiza README y PR con comandos, contratos, resultados y limitaciones; conserva migradores y evidencia trazable.
