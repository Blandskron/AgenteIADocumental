# Contribuir

Antes de implementar, revisa las issues y PR abiertos y describe el problema concreto y el alcance. La primera versión se centra en instalación, autenticación, carga/búsqueda/RAG y PDF; las nuevas funcionalidades no forman parte del cierre.

Lee README.md, AGENTS.md y el contrato del servicio afectado. Trabaja en una rama independiente, usa documentos sintéticos y conserva migraciones y compatibilidad con instalaciones existentes. No incluyas secretos ni datos personales.

El PR debe explicar el comportamiento anterior y nuevo, aportar pruebas pertinentes y declarar las limitaciones. La [verificación de entrega](docs/release/README.md) describe el entorno aislado; nunca ejecutes fixtures contra datos propios. Para la web: `npm ci`, `npm test`, `npm run build` y pruebas de navegador cuando corresponda.

La licencia actual reserva derechos. No presupongas una licencia Open Source ni cambies LICENSE o atribuciones; la decisión y la aceptación de contribuciones requieren confirmación del titular.
