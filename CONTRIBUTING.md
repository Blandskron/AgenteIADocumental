# Contribuir a KronDocs — Document Intelligence (antes Blandskron Documental)

Puedes contribuir reportando errores, proponiendo mejoras o enviando cambios de código y documentación.

1. Revisa las [issues](https://github.com/Blandskron/AgenteIADocumental/issues) y los [pull requests](https://github.com/Blandskron/AgenteIADocumental/pulls) abiertos. Describe el problema, los pasos para reproducirlo cuando corresponda y el alcance del cambio. Para informar una vulnerabilidad, sigue la [política de seguridad](SECURITY.md).
2. Lee el [README](README.md), las [reglas del repositorio](AGENTS.md) y la documentación del componente. Trabaja en una rama independiente, usa documentos sintéticos y conserva la compatibilidad con instalaciones existentes. Mantén los secretos y los datos personales fuera de las contribuciones.
3. Abre un pull request dirigido a `main`. Describe el comportamiento anterior, el cambio y cómo lo verificaste. Enlaza la issue si existe e incluye las limitaciones de las pruebas.

La [verificación de entrega](docs/release/README.md) describe cómo probar con datos sintéticos en un entorno aislado. Para cambios de frontend, ejecuta `npm ci`, `npm test` y `npm run build`, más las pruebas de navegador que correspondan al recorrido afectado.

El código y la documentación del proyecto se distribuyen bajo la [licencia MIT](LICENSE). Respeta las licencias y los avisos de autoría de los recursos de terceros.
