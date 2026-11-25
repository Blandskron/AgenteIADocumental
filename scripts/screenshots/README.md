# Generación automatizada de capturas reales (Modo Claro y Modo Oscuro)

El directorio incluye dos scripts complementarios:

1. **[capture_showcase_local.mjs](capture_showcase_local.mjs):** levanta `vite preview` sobre la compilación de producción (`frontend/dist/`), inyecta datos sintéticos verificados (sin secretos ni PII) y genera automáticamente las **24 capturas WebP de alta resolución (`1280×800 @2x`)** — **12 flujos completos en Modo Claro y 12 en Modo Oscuro** — en `docs/assets/screenshots/`:
   - `login.webp` / `login-dark.webp`
   - `document-chat.webp` / `document-chat-dark.webp`
   - `agent-orchestrator.webp` / `agent-orchestrator-dark.webp`
   - `documents.webp` / `documents-dark.webp`
   - `document-assignments.webp` / `document-assignments-dark.webp`
   - `ai-settings.webp` / `ai-settings-dark.webp`
   - `ai-settings-groq.webp` / `ai-settings-groq-dark.webp`
   - `knowledge-studio.webp` / `knowledge-studio-dark.webp`
   - `knowledge-studio-study.webp` / `knowledge-studio-study-dark.webp`
   - `audit-logs.webp` / `audit-logs-dark.webp`
   - `admin-panel.webp` / `admin-panel-dark.webp`
   - `applications-drive.webp` / `applications-drive-dark.webp`
2. **[capture_screenshots.mjs](capture_screenshots.mjs):** recorre una instancia viva de Docker Compose en `http://localhost:3000`.

## Regeneración rápida de las 24 capturas y del video narrado (sin levantar contenedores)

```bash
cd frontend && npm run build && cd ..
node scripts/screenshots/capture_showcase_local.mjs
python scripts/screenshots/generate_demo_video.py
```

El script [generate_demo_video.py](generate_demo_video.py) compone el video `docs/assets/video/blandskron-documental-demo.mp4` (`1280×800`, H.264 `yuv420p` + audio AAC en español + `+faststart`) y la pista de subtítulos WebVTT `docs/assets/video/blandskron-documental-demo.es.vtt` recorriendo los 12 capítulos en Modo Claro y Modo Oscuro.

El reporte de pantallas capturadas u omitidas se guarda en `.release-reports/SCREENSHOTS_REPORT.json`.

## Publicación en GitHub Pages

1. En **Settings → Pages** del repositorio en GitHub, selecciona **Deploy from a branch** → rama `main`, carpeta **`/ (root)`**.
2. La landing `/index.html` usa exclusivamente rutas relativas (`docs/assets/landing.css`, `docs/assets/landing.js`, `frontend/public/brand/krondocs-isotipo.svg`, `frontend/public/favicon.svg`, `docs/assets/screenshots/*.webp`), por lo que funciona directamente bajo `https://blandskron.github.io/AgenteIADocumental/`.

