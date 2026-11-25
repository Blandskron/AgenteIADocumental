# Design System — KronDocs: Document Intelligence

Sistema de diseño tokenizado para React 19 + CSS nativo de **KronDocs — Document Intelligence** (*Open Source · By BLANDSKRON*), sin frameworks externos de estilos y validado con ESLint, Playwright y `@axe-core/playwright` bajo **WCAG 2.2 AA**.

---

## 1. Arquitectura de Estilos y Capas

Los estilos viven en [frontend/src/shared/styles/](../frontend/src/shared/styles/index.css) y se cargan en orden determinista:

1. `tokens.css`: `@font-face` autohospedados, primitivos de marca/semánticos, temas (`dark` por defecto y `light`), escala de espaciado, radios, elevación y movimiento.
2. `global.css`: Reset ligero, lienzo atmosférico sutil con grilla geométrica de `32 px`, tipografía base, foco accesible `:focus-visible` (`3 px` sólido) y `@media (prefers-reduced-motion: reduce)`.
3. `primitives.css`: Botones (`Button`), controles con icono (`IconButton`), `Badge`, `PageHeader`, `ThemeSwitcher`, `Brand` y flujo de acceso `LoginPage`.
4. `navigation.css`: `AppShell`, `Sidebar` colapsable, búsqueda rápida `Ctrl+K`, drawer móvil (`ModalDialog`) y menú de cuenta.
5. `chat.css`: Estado inicial Bento, burbujas de conversación, modo lectura editorial (`Source Serif 4`), `SafeMarkdown`, citas clicables `[Fuente N]`, panel de fuentes verificadas, selector unificado (`Chat · Agente · Code Mode`), `AgentRunPanel` (HITL) y `CommandPalette`.
6. `documents.css`: Cabecera de biblioteca, KPIs Bento `tabular-nums`, subtabs de vistas, tarjetas de documentos, carpetas y tarjetas de asignaciones/firmas.
7. `integrations.css`: Conectores (`Google Drive`, importación ZIP/Markdown), layout compartido `.settings-ai-*` y tablas/subtarjetas `.ui-*` para Configuración IA, Knowledge Studio y Auditoría.
8. `dialogs.css`: Modales nativos `<dialog>`, visor previo de documentos, historial de exportaciones PDF y transferencias.

> **Blindaje automático en Lint:** `frontend/eslint.config.js` prohíbe tokens fantasma (`--border-subtle`, `--surface-card`, `--text-muted`, etc.) y restringe imports cruzados desde `shared/` y `entities/`.

---

## 2. Sistema de Tokens (`tokens.css`)

### 2.1 Escala de Espaciado (base 4 px)

| Token | Valor | Uso |
| :--- | ---: | :--- |
| `--space-1` | `4px` | Separación mínima entre icono y texto o badges |
| `--space-2` | `8px` | Gaps internos de botones, toolbars y chips |
| `--space-3` | `12px` | Padding de inputs, filas y separación de shell |
| `--space-4` | `16px` | Padding estándar de tarjetas y grillas |
| `--space-5` | `20px` | Padding de tarjetas principales y modales |
| `--space-6` | `24px` | Separación entre secciones de página |
| `--space-8` | `32px` | Márgenes de lectura y contenedores amplios |
| `--space-12` | `48px` | Espaciado de estados vacíos y hero |

### 2.2 Escala de Radios y Elevación

| Token | Valor | Uso |
| :--- | ---: | :--- |
| `--radius-sm` | `8px` | Inputs, botones, items de menú y badges de código |
| `--radius-md` | `12px` | Avatares, iconos de cabecera, tarjetas compactas y alertas |
| `--radius-lg` | `16px` | Tarjetas Bento, burbujas de mensaje, paneles Studio y Admin |
| `--radius-xl` | `24px` | Contenedores principales (`AppShell`, `Sidebar`, `PageHeader`, `LoginWindow`, `<dialog>`) |
| `--radius-pill` | `9999px` | Badges semánticos y selector de modos (`Chat · Agente · Code Mode`) |

### 2.3 Floating Glassmorphism Sutil y Accesibilidad Visual

Los paneles principales (`Sidebar`, `main`, `PageHeader`, `Composer`, `<dialog>`) emplean superficies translúcidas con desenfoque controlado (`--glass-blur: blur(20px) saturate(135%)`) e iluminado superior sutil (`--glass-shadow`), mientras que los controles de lectura y edición usan mayor opacidad (`--glass-strong`, `--surface`) para garantizar legibilidad.

Cuando el sistema operativo activa `prefers-reduced-transparency: reduce`, `prefers-contrast: more` o `forced-colors: active`, el Design System desactiva automáticamente el desenfoque y conmuta a superficies sólidas de alto contraste (`var(--surface)` y `var(--border-strong)`).

### 2.4 Microinteracciones (150–250 ms)

- `--duration-fast: 150ms`: Estados hover de inputs, botones y chips.
- `--duration: 180ms`: Transiciones de tarjetas Bento y navegación lateral.
- `--duration-slow: 240ms`: Apertura de paneles y transiciones suaves de contenedor.
- `--ease-standard: cubic-bezier(0.2, 0.8, 0.2, 1)`: Curva desacelerada sin rebote excesivo.
- `@media (prefers-reduced-motion: reduce)` reduce animaciones y transiciones a `0.01ms`.

---

## 3. Gestión de Temas (`ThemeProvider` & `ThemeSwitcher`)

- **Preferencia por defecto:** **Dark Mode (`"dark"`)** en primera visita.
- **Modos soportados:** `"dark"` (Oscuro), `"light"` (Claro) y `"system"` (Preferencia del sistema operativo mediante `prefers-color-scheme`).
- **Persistencia compatible:** Guarda en `localStorage["krondocs:theme"]` (y sincroniza `blandskron:theme` con el tema resuelto `"dark" | "light"` para compatibilidad con integraciones y pruebas heredadas).

---

## 4. Primitivas Compartidas (`frontend/src/shared/components/`)

| Componente | Propósito | Variantes / Notas |
| :--- | :--- | :--- |
| **`Brand`** | Lockup oficial e isotipo SVG | `variant="wordmark" \| "compact" \| "isotipo"`, `showDescriptor`, `showSignature` |
| **`Button`** | Acción principal/secundaria accesible | `variant="primary" \| "secondary" \| "ghost" \| "danger"`, `busy`, soporte `forwardRef` |
| **`IconButton`** | Botón cuadrado `40×40 px` con icono | Requiere `aria-label` descriptivo |
| **`Badge`** | Etiqueta semántica de estado o procedencia | `neutral \| accent \| success \| warning \| danger \| info \| ai \| verified \| pending` |
| **`PageHeader`** | Cabecera editorial unificada | Eyebrow `JetBrains Mono` con marcador cyan, título `Sora`, badges y acciones |
| **`ThemeSwitcher`** | Selector de 3 estados (`Oscuro · Claro · Sistema`) | Colapsa a botón de alternancia rápida cuando el sidebar está contraído |
| **`ModalDialog`** | Contenedor modal nativo accesible | Gestión de foco, cierre por `Escape` y restitución al disparador |

---

## 5. Patrones UX/UI de Inteligencia Documental

1. **Workspace Orientado a Fuentes:** El estado inicial del chat guía con 3 acciones Bento concretas; al responder, cada afirmación citada `[Fuente N]` se renderiza como chip interactivo (`--verified-source`) que despliega y desplaza suavemente al fragmento exacto en **Fuentes verificadas**.
2. **Lectura Editorial Confortable:** Cada respuesta del asistente ofrece el botón **Lectura** (`aria-pressed`), alternando `Source Serif 4` a `15.5 px`, `line-height: 1.78` y medida óptima de `68ch`.
3. **Orquestación Agéntica y Code Mode (HITL):** El selector en píldora separa visualmente `Chat`, `Agente` y `Code Mode`. El panel `AgentRunPanel` identifica estado y proveedor mediante `Badge` semánticos, presenta código de sandbox en `JetBrains Mono` y destaca con borde/superficie `warning` cualquier solicitud de aprobación humana.
4. **Navegación Rápida (`Ctrl+K`):** Accesible por atajo de teclado o desde el botón superior del sidebar; respeta permisos efectivos del usuario y anuncia selección con roles `listbox`/`option`.

---

## 6. Checklist WCAG 2.2 AA

- [x] Contraste mínimo ≥ 4.5:1 en texto normal y ≥ 3:1 en bordes de controles e iconos en Dark y Light Mode.
- [x] Indicador de foco visible (`3 px solid var(--focus)`) en todos los controles interactivos.
- [x] Tamaño mínimo de objetivo táctil (`≥ 40 px` en botones y `≥ 44 px` en navegación móvil).
- [x] Navegación por teclado completa (skip link `#main-content`, `Escape` en modales/menús, `Ctrl+K`).
- [x] Soporte para `prefers-reduced-motion`, `prefers-reduced-transparency`, `prefers-contrast: more` y `forced-colors: active`.
- [x] Verificación automatizada con `@axe-core/playwright` (`wcag2a`, `wcag2aa`, `wcag21aa`, `wcag22aa`).
