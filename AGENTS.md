# Cómo colaborar en este repositorio

Este repositorio contiene Blandskron Documental, una plataforma documental de portafolio. El [tablero](ROADMAP.md) registra entregas, evidencia y trabajo autorizado. El [README](README.md) es la entrada humana; cada servicio mantiene su contrato y sus instrucciones locales.

## Antes de empezar

1. Lee el [tablero](ROADMAP.md), el [README](README.md) y la documentación del servicio que vas a tocar.
2. Ejecuta `git status --short` y `git branch --show-current`. Conserva los cambios existentes. La base documental está en `main`; comprueba la referencia antes de iniciar una rama.
3. Elige una tarjeta de **Lista**. Si ya hay una en **En curso**, retómala o registra el bloqueo antes de tomar otra.

## Durante el trabajo

- Usa el ID de la tarjeta en la descripción del cambio. Entrega un incremento que pueda revisarse y validarse por sí solo.
- Reutiliza los contratos y convenciones del servicio. Si cambias un contrato, revisa sus consumidores, configuración y migraciones.
- Usa documentos sintéticos. Mantén las claves fuera del código, ejemplos, logs y capturas. Consulta el alcance de publicación indicado en el tablero antes de preparar material para terceros.

## Operaciones Git autorizadas

- El usuario autorizó crear y eliminar ramas, hacer commits, integrar cambios y hacer push para avanzar el trabajo. Usa `codex/` para las ramas de trabajo.
- Antes de eliminar una rama o reescribir una referencia, comprueba su destino y si contiene commits que deban conservarse. Antes de hacer push, verifica el remoto, la rama y los cambios que se enviarán.
- La autorización sobre Git es operativa. El alcance para modificar y compartir el código y los recursos de terceros se resuelve en BD-002.

## Antes de cerrar

- Ejecuta las comprobaciones de la tarjeta. Para frontend, usa `npm ci` y `npm run build` desde `frontend`. Para Compose, ejecuta `docker compose -f docker/docker-compose.yml config --quiet` desde la raíz con la configuración requerida por la rama.
- Registra evidencia breve en la tarjeta, incluyendo comandos ejecutados y comprobaciones pendientes. Pásala a **En revisión**. Ciérrala cuando cumpla sus criterios de aceptación.
- Actualiza el README si cambian comandos, variables requeridas o el recorrido de la demo.
- Para cambios transversales usa la [verificación de entrega](docs/release/README.md): proyecto dedicado `bd-final-check`, `.env.example`, datos sintéticos y herramientas en `scripts/release/`. `docs/` conserva solo documentación/evidencia. No declares una auditoría histórica como resultado de la imagen actual ni una prueba con proveedor simulado como integración en vivo.
