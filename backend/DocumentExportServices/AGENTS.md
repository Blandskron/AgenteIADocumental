# Trabajar en DocumentExportServices

Lee [README.md](README.md) y [ROADMAP.md](../../ROADMAP.md#documentexportservices), además de [AGENTS raíz](../../AGENTS.md). EXPORT-001 es diagnóstico: no presentar propuestas como garantías implementadas. Retoma la tarjeta en curso o elige una de Lista; entrega un incremento revisable por PR con su ID y evidencia.

## Límites del servicio

- Export recibe una instantánea de pregunta/respuesta/fuentes; hoy no consulta mensajes, documentos ni LLM. No añadir fetch remoto/HTML activo ni prometer procedencia certificada sin un contrato nuevo.
- La identidad pertenece a Auth. El fallback de dueño y la falta de revocación actuales están pendientes de EXPORT-003; no copiarlos como estándar. Ningún rol administrativo debe ampliar acceso a exports ajenos.
- Revisa juntos request/DTO, ManageExports, repositorio, renderer, SQL y consumidores `features/document-export`, ChatPage, ChatMessages y AuthProvider. Las referencias opcionales deben respetar dueño/coherencia y no romper la exportación desde mensajes aún no sincronizados.
- PDF y fila son dos recursos en la línea base. No borrar fuentes/filas ni reubicar PDFs heredados indiscriminadamente; inventariar/revisar antes de cambiar storage. La decisión de EXPORT-005 depende de límites, capacidad y recuperación, no de copiar automáticamente Avatar.
- Usa claves y PDFs sintéticos, directorio/volumen separado y configuración explícita. No montes `documents/exports` real para probar fallos ni vuelques `.env`, JWT, preguntas, respuestas o rutas personales a logs.
- `docs/` conserva evidencia documental, no aplicaciones Python. Mantén pruebas/código en sus ubicaciones propias y conserva migraciones hasta tener un reemplazo probado.

## Verificación y evidencia

- La línea base se midió en Windows con Python 3.12.14, repositorio sustituido y sin lifespan/PostgreSQL/Auth real. No llamar integración a esas sondas ni extrapolar su auditoría a Linux; consulta [BASELINE.json](docs/BASELINE.json).
- EXPORT-002 debe añadir suite mantenida PostgreSQL y separar runtime/test/audit. Agrega pruebas de cada corrección sin conservar expectativas de comportamiento inseguro como garantía. Concurrencia se prueba entre conexiones reales con limpieza verificada.
- Para renderer, genera casos español/Unicode, fuentes y tablas extensas/multipágina; verifica texto y render PNG con Poppler. No basta con que el archivo tenga bytes o comience por %PDF.
- Para frontend, ejecuta npm ci/test/build y las pruebas de navegador aplicables. Para Compose, ejecuta config --quiet desde raíz. Para imagen, distingue dependencias instaladas, SO y vendorizados y registra artefacto/avisos.
- Actualiza README/tablero con comandos, límites y pendientes reales; pasa a En revisión, cierra al integrar. Al cerrar EXPORT-008, sustituye el diagnóstico por operación final y conserva seguimientos transversales.
