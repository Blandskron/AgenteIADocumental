# Roadmap de Transformación — KronDocs: Document Intelligence

> **Marca oficial:** **KronDocs — Document Intelligence** (*Turn Documents into Intelligence* · *Open Source · By BLANDSKRON*)  
> **Repositorio:** `Blandskron/AgenteIADocumental` (transición de marca desde AgenteIADocumental / Blandskron Documental preservando compatibilidad operativa).

---

## Fase 1 — Investigación, Auditoría y Planificación

| ID | Tarea | Criterio de aceptación verificable | Estado |
| :--- | :--- | :--- | :--- |
| **KD-101** | Auditoría integral del repositorio, `AGENTS.md`, `frontend/`, `docs/`, CI/CD y landing page | Inventario completo de rutas (15 rutas en `appRoutes`), componentes, hojas CSS, tests y dependencias | Completado |
| **KD-102** | Revisión de seguridad e incorporación de `ui-ux-pro-max-skill` (v2.15.0, MIT) | Scripts Python auditados (solo stdlib, 0 red externa, sin `eval`/`subprocess`); instalada en `.agents/skills/ui-ux-pro-max/` y enlazada en `docs/maintainers.md` | Completado |
| **KD-103** | Análisis del Design System corporativo de BLANDSKRON (`blandskron.cl` / `Blandskron/blandskronSPA`) y referentes de conocimiento | Tokens corporativos (`#4A148C`, `#2E0B59`, `#8B5CF6`, `#090909`, `JetBrains Mono` eyebrows, `Inter` local-first) y arquitectura de 3 paneles / panel de citas verificadas analizados | Completado |
| **KD-104** | Planificación y creación de `docs/ROADMAP.md` | Roadmap versionado con criterios de aceptación verificables por fase | Completado |

---

## Fase 2 — Branding y Design System

| ID | Tarea | Criterio de aceptación verificable | Estado |
| :--- | :--- | :--- | :--- |
| **KD-201** | Sistema de identidad visual KronDocs | Isotipo geométrico K + documentos + nodos de conocimiento (`krondocs-isotipo.svg`), lockups dark/light, variantes monocromáticas y `favicon.svg` creados en `frontend/public/` | Completado |
| **KD-202** | Tipografía local-first SIL OFL 1.1 (`Sora`, `Inter`, `Source Serif 4`, `JetBrains Mono`) | Fuentes variable `.woff2` (latin + latin-ext) y licencias `OFL-*.txt` autohospedadas en `frontend/public/fonts/` sin CDN externos | Completado |
| **KD-203** | Tokens semánticos revalidados WCAG 2.2 AA (`tokens.css`) y `ThemeProvider` (Dark por defecto / Light / Sistema) | Contraste ≥ 4.5:1 en texto normal y ≥ 3:1 en bordes UI en ambos temas; `ThemeProvider` soporta `"dark" \| "light" \| "system"` con fallback `blandskron:theme` | Completado |
| **KD-204** | Primitivas compartidas reutilizables | `Brand`, `Badge`, `ThemeSwitcher`, `PageHeader`, `Button`, `IconButton` siguiendo límites de capa ESLint (`shared/` aislado) | Completado |

---

## Fase 3 — Implementación UX/UI y Transición de Marca

| ID | Tarea | Criterio de aceptación verificable | Estado |
| :--- | :--- | :--- | :--- |
| **KD-301** | Consolidación CSS y eliminación de duplicaciones | Reglas limpias sin tokens fantasma (`eslint.config.js` con 0 warnings), espaciado base 4 px, radios 8/12/16/24 px, transiciones 150–250 ms y `prefers-reduced-motion` | Completado |
| **KD-302** | Refinamiento integral de vistas núcleo: Login, AppShell/Sidebar, CommandPalette (`Ctrl+K`), Chat RAG + Citas + Modo Lectura Editorial, Agentes IA + Code Mode (HITL) | Citas `[Fuente N]` clicables con scroll y resaltado de fuente; toggle de lectura editorial `Source Serif 4`; badges semánticos de IA y fuentes verificadas; 0 estilos inline innecesarios | Completado |
| **KD-303** | Refinamiento integral de vistas operativas: Biblioteca documental, Asignaciones y Firmas, Knowledge Studio (+ SM-2/Quiz), Aplicaciones/Drive, Configuración IA, Administración y Auditoría | Consistencia de `PageHeader`, tablas accesibles, KPIs Bento `tabular-nums`, feedback de estado y preservación total de APIs, RBAC y contratos | Completado |
| **KD-304** | Transición de marca en Landing Page (`index.html`), `README.md`, documentación y scripts de capturas | Landing dark-first con switcher de tema, fuentes locales, isotipo SVG, enlaces intactos a GitHub y documentación actualizada preservando compatibilidad | Completado |

---

## Fase 4 — Validación, Documentación y Perfeccionamiento

| ID | Tarea | Criterio de aceptación verificable | Estado |
| :--- | :--- | :--- | :--- |
| **KD-401** | Documentación oficial: `docs/BRAND_GUIDELINES.md` y `docs/DESIGN_SYSTEM.md` | Guías completas de marca, isotipo, paleta AA, tipografía, tokens, componentes y patrones de conocimiento enlazadas desde `README.md` | Completado |
| **KD-402** | Validación de código, tests unitarios y compilación | `npm run format:check`, `npm run lint` (`--max-warnings=0`), `npm run typecheck`, `npm test` (`138/138`) y `npm run build` (`566 ms`) en verde | Completado |
| **KD-403** | Pruebas Playwright + `@axe-core/playwright` (WCAG 2.2 AA) + Regresión responsive | `41/41` pruebas aprobadas con 0 violaciones WCAG 2.2 AA en tema oscuro, tema claro y móvil (320 px, 390 px), incluyendo `krondocs-design-system.spec.js` | Completado |
| **KD-404** | Capturas reales (`capture_showcase_local.mjs`), inspección visual y auditoría Lighthouse | 24 capturas WebP reales regeneradas e inspeccionadas; Lighthouse Accessibility `100/100/100` registrado en `.release-reports/krondocs-lighthouse/`; `check_docs_links.py` en verde | Completado |

---

## Evidencia de Validación Registrada

| Verificación | Alcance | Resultado observado |
| :--- | :--- | :--- |
| **ESLint (`npm run lint`)** | `frontend/src` (`--max-warnings=0`, bloqueo de tokens fantasma y capas) | 0 errores, 0 warnings |
| **TypeScript (`npm run typecheck`)** | `tsc --noEmit` estricto | 0 errores |
| **Prettier (`npm run format:check`)** | `frontend/src` | Conforme |
| **Unit tests (`npm test`)** | 32 suites unitarias (`node --test`) | `138/138` aprobados |
| **Build (`npm run build`)** | Vite 8.3.7 producción | Compilado en `566 ms` |
| **Playwright + `@axe-core/playwright`** | 6 specs (`41` casos en Dark, Light, 320 px, 390 px) | `41/41` aprobados, 0 violaciones WCAG 2.2 AA |
| **Capturas WebP reales** | `scripts/screenshots/capture_showcase_local.mjs` | `24/24` WebP (`1280×800 @2x`) regeneradas e inspeccionadas |
| **Lighthouse (`landing-desktop`)** | `index.html` (servidor local estático sin compresión HTTP) | Performance `86`, Accessibility `100`, Best Practices `100`, SEO `100` (CLS `0.0`, TBT `0 ms`) |
| **Lighthouse (`landing-mobile`)** | `index.html` (emulación móvil local sin compresión HTTP) | Performance `77`, Accessibility `100`, Best Practices `100`, SEO `100` (CLS `0.0`, TBT `0 ms`) |
| **Lighthouse (`app-login-desktop`)** | `frontend/dist/login` (estático sin backend `/test-api`) | Performance `97`, Accessibility `100`, Best Practices `96`, SEO `91` |
| **Integridad de enlaces Markdown** | `python scripts/ci/check_docs_links.py` | OK (todos los enlaces relativos resuelven) |
