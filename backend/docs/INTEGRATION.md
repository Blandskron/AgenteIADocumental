# Integración entre servicios

## Identidad y autorización

Auth emite el JWT y mantiene la cuenta, la huella de contraseña y las membresías. Chat, Ingesta, Búsqueda, Acceso, Biblioteca, Transferencias y Conversaciones verifican el token y consultan la identidad vigente por HTTP. Perfil, Exportación y Drive verifican la vigencia mediante funciones SQL acotadas. Cada dominio aplica además sus permisos sobre documentos, referencias o recursos del dueño. Los roles de PostgreSQL restringen qué tablas y funciones usa cada runtime.

## Datos y cambios coordinados

| Flujo | Propietario y consumidores | Qué revisar al cambiarlo |
| --- | --- | --- |
| Alta y procesamiento de documentos | Ingesta escribe originales, metadatos y fragmentos. La web y Drive llaman a Ingesta. | Contrato multipart, estados, reindexación y compatibilidad de embeddings con Chat. |
| Visibilidad y borrado | Búsqueda, Acceso, Biblioteca y Chat aplican visibilidad documental. Acceso coordina el borrado con PostgreSQL y el volumen compartido. | Aislamiento entre cuentas y empresas, ciclo de vida de referencias y carreras con Ingesta o Biblioteca. |
| Conversaciones y exportación | Conversaciones mantiene el historial. Exportación persiste una instantánea aportada por la web y valida las referencias que recibe. | Propiedad y coherencia de conversación y mensaje, IDs locales, reintentos y descarga privada. |
| Perfil e identidad | Perfil posee contacto y avatar. Auth posee identidad, permisos y membresías. | Revocación, versión de escritura y conservación de borradores durante la renovación de sesión. |
| Importación y transferencias | Drive mantiene su diario de importación. Transferencias registra el flujo de la web. | Diferencia entre operación confirmada y resultado incierto, deduplicación y limpieza de eventos propios. |

Los despliegues que cambian esquema, contratos HTTP o DTO de la web deben coordinar las tres capas. Usa el mapa de escritores y el preflight antes de imponer relaciones SQL. Para validar el recorrido entre dominios, usa dos identidades sintéticas y el proyecto Compose aislado de entrega. [Esquema y migraciones](../../scripts/database/README.md) · [Verificación integral](../../docs/release/README.md)
