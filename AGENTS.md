# Cómo colaborar en Blandskron Documental

El [README](README.md) es la entrada humana. Cada servicio mantiene su contrato en README e instrucciones locales en AGENTS. La [verificación de entrega](docs/release/README.md) describe comprobaciones, alcance local y avisos residuales. La modernización del portafolio está integrada; los nuevos cambios se delimitan en una issue o en la descripción del PR.

## Antes de empezar

1. Lee el README raíz y la documentación e instrucciones del componente que vas a tocar.
2. Ejecuta `git status --short` y `git branch --show-current`; conserva los cambios existentes. Comprueba main antes de crear una rama codex/.
3. Revisa las issues y PR abiertos antes de iniciar trabajo; retoma cambios pendientes antes de duplicarlos.

## Durante el trabajo

- Entrega incrementos revisables con objetivo, alcance y evidencia en el PR. Reutiliza contratos y convenciones; revisa consumidores, configuración y migraciones cuando cambien.
- Usa documentos sintéticos. No guardes claves, tokens, datos personales ni credenciales en código, ejemplos, logs o capturas.
- Código y recursos propios de Blandskron: conserva LICENSE y atribuciones de terceros. La demo se limita a desarrollo local en loopback; Google Drive es opcional.
- docs/ contiene documentación y evidencia. El código de comprobación y mantenimiento vive en scripts/ y las pruebas en sus suites.

## Git autorizado

El usuario autorizó crear/eliminar ramas, hacer commits, integrar y hacer push. Antes de eliminar o reescribir una referencia, verifica destino y commits por conservar. Antes de hacer push, verifica remoto, rama y cambios. No borres datos o recursos ajenos para limpiar el repositorio.

## Antes de cerrar

- Ejecuta las comprobaciones apropiadas al cambio y registra resultados y limitaciones en el PR. Para frontend: `npm ci`, `npm test`, `npm run build` y navegador cuando corresponda. Para Compose: `docker compose -f docker/docker-compose.yml config --quiet` desde raíz con su configuración requerida.
- Usa el proyecto sintético bd-final-check y .env.example para la verificación transversal; no montes archivos o secretos personales. Conserva migraciones y pruebas necesarias para operar instalaciones existentes.
- Actualiza el README si cambian comandos, variables o recorrido de la demo. Valida enlaces al retirar documentación.
- No presentes un escaneo histórico como auditoría de otra imagen, ni un proveedor simulado como integración en vivo. Conserva evidencia fechada y disposición de avisos; reconstruye y reevalúa antes de otro despliegue.
