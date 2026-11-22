# 08 — Auditoría de Experiencia de Producto y Frontend

- **Alcance auditado:** `frontend/` (`package.json`, `vite.config.ts`, `src/`, `tests/`, `nginx.conf`, `docker-entrypoint.d/20-runtime-config.sh`).
- **Verificación local ejecutada:** `npm test` (**138/138 passed**), `npm run lint` (**PASS**, 0 warnings), `npm run typecheck` (**PASS**).
- **Commit base:** `develop@5a4fac2` (22 de noviembre de 2026).

---

## 1. Fortalezas comprobadas del frontend actual

1. **Huella mínima y rendimiento base excelente:** Solo 3 dependencias runtime (`react@19.3.1`, `react-dom@19.3.1`, `lucide-react@1.70.0`), code-splitting automático con `React.lazy` + `Suspense` en `src/app/App.tsx`, y bundle principal compacto (`220.8 KB` JS + `43.8 KB` CSS).
2. **Design System *Floating Glass* coherente y 100 % local:** `src/shared/styles/tokens.css` sirve la fuente `Inter` localmente (`/fonts/inter-variable.woff2`, sin fuentes externas), define tokens semánticos completos para modo claro y `[data-theme="dark"]`, y contempla degradación accesible (`prefers-reduced-transparency`, `prefers-contrast: more`, `forced-colors: active`).
3. **Accesibilidad y responsive verificados:** `skip-link`, drawer móvil accesible (`ModalDialog` bajo `760px`), navegación por teclado y 6 suites Playwright con `@axe-core/playwright` en modo claro y oscuro.
4. **Resiliencia HTTP:** `httpClient.ts` implementa refresco coordinado ante `401`, normalización defensiva de arrays (`Array.isArray`) y cancelación con `AbortController`.

---

## 2. Auditoría vista por vista (Sección 7.5)

| Vista / Flujo | Ruta | Estado auditado | Brechas reales encontradas en código |
|---|---|---|---|
| **Login / Registro** | `/login` | `IMPLEMENTADO PARCIALMENTE` | Registro admin local funciona offline. `googleOidcLoginRequest` existe en `auth.api.ts`, pero `LoginPage.tsx:260-270` solo muestra un `<p>` informativo sin botón OIDC ejecutable. |
| **Chat RAG** | `/` | `IMPLEMENTADO PARCIALMENTE` | Selector unificado `Chat`/`Agente`/`Code Mode` bien integrado. `SafeMarkdown.tsx` **no renderiza tablas Markdown**; `SourceList.tsx` solo despliega texto crudo sin abrir documento en la página citada; carga limitada a 1 archivo por clic. |
| **Agente y Code Mode** | `/` | `IMPLEMENTADO PARCIALMENTE` | UI de plantillas, pasos, filtros, hallazgos, riesgo, retry y auditoría existe, pero depende del SSE real, de `20-runtime-config.sh` (hoy omite `VITE_AGENT_ORCHESTRATOR_BASE_URL`) y de las correcciones SQL de `AgentOrchestratorServices`. |
| **Biblioteca, Carpetas, Favoritos, Asignaciones y Notificaciones** | `/documents*` | `IMPLEMENTADO PARCIALMENTE` | Muy completa en permisos y asignaciones; falta drag-and-drop multiarchivo, navegación de subcarpetas anidadas, etiquetas/metadatos editables, versionado, y tarjetas KPI muestran conteos de la página cargada en memoria en lugar de totales globales. |
| **Visor documental** | Modal (`DocumentPreviewModal.tsx`) | `IMPLEMENTADO PARCIALMENTE` | Usa `<iframe sandbox="" src={preview.url} />`, lo que impide salto a página (`#page=N`), resaltado de fragmentos y bloquea el visor PDF nativo en varios navegadores. |
| **Knowledge Studio** | `/studio` | `IMPLEMENTADO PARCIALMENTE` | **Mayor brecha de desconexión:** no invoca `listStudioTemplates`, `validateStudioMermaid`, `exportStudioCsv` ni renderiza `VerifiedVisualsPanel.tsx`; `OfflineFlashcardDeck` e `InteractiveQuizPanel` usan datos estáticos hardcodeados; `handleSaveArtifact` fabrica una cita sintética descartando las `sources` reales; `App.tsx` no valida `canUseChat` al entrar por URL directa. |
| **Configuración de IA** | `/settings/ai` | `IMPLEMENTADO PARCIALMENTE` | Soporta Groq y Ollama (con descarga de modelos en allowlist). No muestra requisitos de RAM por modelo Ollama ni permite configurar proveedores `openai_compatible` genéricos. |
| **Administración y Auditoría** | `/admin`, `/admin/audit` | `IMPLEMENTADO PARCIALMENTE` | `AdminPage` sólida en tenants/áreas/membresías/grupos. `AuditLogsPage` está fija a `limit: 50, offset: 0`, dispara un `fetch` por cada tecla en `actionFilter` (sin debounce/transition), y carece de paginación, filtro de fechas y exportación CSV/JSON. |
| **Importaciones / Aplicaciones** | `/applications*` | `IMPLEMENTADO PARCIALMENTE` | Google Drive (PKCE + Picker) y `MarkdownBatchImportCard` (multiarchivo/ZIP) operativos. Existe permiso `use_sharepoint` en UI/RBAC sin conector asociado (limpiar o marcar explícitamente no implementado). |
| **Perfil y Exportaciones** | `/profile`, modal transferencias/PDF | `IMPLEMENTADO Y VERIFICADO` | Sólidos, con manejo optimista de conflictos `409`, revocación segura de Object URLs y descarga privada con `AbortController`. |

---

## 3. Consistencia del Design System y deuda CSS menor

- La mayoría de hojas (`AdminPage.css`, `ProfilePage.css`, `documents.css`, `navigation.css`, `integrations.css`) ya usan tokens `--glass*` sin hex literales.
- Quedan **19 valores hex literales** por migrar a tokens en `primitives.css` (10), `ConfirmModal.css` (5), `chat.css` (3), `dialogs.css` (1) y estilos inline de colores de carpetas en `DocumentSearchPage.tsx:771-778`.
- **Regla respetada:** No duplicar ni reemplazar *Floating Glass*; consolidar los últimos literales en `tokens.css`.

---

## 4. Brechas transversales de UX y configuración runtime

1. **Bug runtime Docker (`frontend/docker-entrypoint.d/20-runtime-config.sh`):** No inyecta `VITE_KNOWLEDGE_STUDIO_BASE_URL` ni `VITE_AGENT_ORCHESTRATOR_BASE_URL` en `window.__BLANDSKRON_CONFIG__`, rompiendo despliegues con puertos o hosts personalizados.
2. **Sin Command Palette / Búsqueda global (`Ctrl+K` / `Cmd+K`):** Los usuarios con decenas de documentos y conversaciones carecen de navegación rápida por teclado.
3. **Sin onboarding post-registro:** Tras crear la cuenta administradora en `/login`, el usuario entra a un chat vacío sin guía progresiva (*1. Configurar IA local o Groq → 2. Subir primer documento → 3. Hacer primera consulta*).
4. **Sin sistema unificado de notificaciones/toasts:** Errores y confirmaciones en `StudioPage`, `SettingsAIPage` y `AuditLogsPage` usan banners inline dispares sin botón de reintento consistente.
5. **Sesión con cookies HttpOnly sin activar:** `cookieLoginRequest`/`cookieRefreshRequest`/`cookieLogoutRequest` ya existen y pasan tests en `auth.api.ts`, pero `AuthProvider` sigue persistiendo JWT en `localStorage` (`blandskron.auth`).

---

## 5. Mejoras con patrones nativos de React 19 (cero librerías nuevas)

Actualmente no se utiliza ningún hook nuevo de React 19 (`0` usos). Sin añadir dependencias externas:

| Patrón React 19 | Aplicación concreta en Blandskron Documental | Beneficio |
|---|---|---|
| **`useActionState` + `useFormStatus`** | Formularios de `AdminPage`, `SettingsAIPage`, `ProfilePage` y `LoginPage` | Elimina gestión manual repetitiva de `busy`/`error`/`notice` y previene envíos duplicados nativamente. |
| **`useOptimistic`** | Favoritos en `DocumentSearchPage`, lectura de notificaciones y renombrado/borrado de conversaciones en `Sidebar` | Respuesta instantánea en interfaz con reversión automática ante error de red. |
| **`useDeferredValue` / `useTransition`** | Filtro `actionFilter` en `AuditLogsPage` y cambio de pestañas en `DocumentSearchPage` | Evita saturar la red por cada pulsación y mantiene el input fluido. |
| **Metadatos nativos (`<title>`)** | Reemplazar el efecto imperativo de `document.title` en `useAppRouter.ts` | Código más declarativo y coherente con React 19. |
