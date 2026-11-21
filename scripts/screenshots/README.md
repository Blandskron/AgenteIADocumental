# Generación automatizada de capturas reales

El script [capture_screenshots.mjs](capture_screenshots.mjs) utiliza Playwright para recorrer la aplicación real ejecutándose en Docker Compose, crear/autenticar una cuenta sintética y guardar capturas optimizadas (WebP cuando `cwebp` está instalado, PNG como respaldo) en `docs/assets/screenshots/`.

## Requisitos

1. Stack activo en local:
   ```bash
   docker compose up -d --build
   ```
2. Dependencias del frontend instaladas (`cd frontend && npm ci && npx playwright install chromium`).
3. Opcional: `cwebp` (`sudo apt-get install webp` en Ubuntu/Debian o `brew install webp` en macOS) para comprimir automáticamente a `.webp`.

## Ejecución manual

```bash
node scripts/screenshots/capture_screenshots.mjs --base-url http://localhost:3000
```

El reporte de pantallas capturadas u omitidas se guarda en `.release-reports/SCREENSHOTS_REPORT.json`.

## Publicación en GitHub Pages

1. En **Settings → Pages** del repositorio en GitHub, selecciona **Deploy from a branch** → rama `main`, carpeta **`/ (root)`**.
2. La landing `/index.html` usa exclusivamente rutas relativas (`docs/assets/landing.css`, `docs/assets/landing.js`, `frontend/public/blandskron-symbol.png`, `docs/assets/screenshots/*.webp`), por lo que funciona directamente bajo `https://blandskron.github.io/AgenteIADocumental/`.

