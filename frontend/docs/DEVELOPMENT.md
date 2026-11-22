# Frontend documental

React 19, Vite y TypeScript estricto. Node 24 es la versión de desarrollo y CI. Ningún secreto de servidor debe llegar a las variables `VITE_*` (`VITE_AUTH_BASE_URL` … `VITE_AGENT_ORCHESTRATOR_BASE_URL`).

## Arquitectura vigente

La separación `app → pages → widgets/features → entities/shared` mantiene la sesión y el tema en Context mientras cada dominio conserva su estado local y controladores protegidos frente a cambios de cuenta o empresa (`useAgentExecution`, `library-controller`, `export-controller`, `drive-controller`, `transfers-controller`). No se usa Redux, Zustand ni frameworks externos de estilos.

## Convenciones

- `app/`: configuración, proveedores y navegación (`useAppRouter` valida las 15 rutas con títulos exhaustivos `Record<AppRoute, string>` y preserva query strings como `/studio?artifact=<id>`); `pages/`: composición de pantallas envueltas en `ErrorBoundary` con `resetKey={route}`.
- `features/`: API, controladores, hooks y UI del dominio; `entities/`: modelos compartidos.
- `shared/`: primitivas visuales, layout, HTTP, almacenamiento y tokens. No importa páginas ni funcionalidades (blindado automáticamente en `eslint.config.js` con `@typescript-eslint/no-restricted-imports`).
- Usa `@/` entre capas; una ruta relativa corta es válida dentro del mismo componente.
- Todas las variables CSS deben provenir de `src/shared/styles/tokens.css`; `eslint.config.js` bloquea en tiempo de lint el uso de tokens fantasma (`--border-subtle`, `--surface-card`, `--text-muted`, `--surface-elevated`, `--surface-muted`, `--surface-primary`, `--accent-primary`).
- Los adaptadores HTTP de listado aceptan `signal?: AbortSignal` para cancelar peticiones en vuelo al filtrar o desmontar vistas (`AuditLogsPage`, `SettingsAIPage`, `useAgentExecution`) y normalizan colecciones defensivamente con `Array.isArray`.
- Conserva el aislamiento por sesión, tenant y generación de solicitud. Los permisos de UI son orientativos: la autorización efectiva pertenece al servidor.
- Los mensajes y documentos se renderizan como texto; evita HTML sin sanitizar. Las URL de avatar y los downloads conservan su contrato privado.
- No persistas contraseñas ni claves. El almacenamiento de tokens existente es un límite de la arquitectura actual: migrar a cookies HttpOnly requiere cambios coordinados del backend y queda fuera de este trabajo.

## Verificación

```powershell
npm ci
npm run audit:dependencies
npm run lint
npm run typecheck
npm run format:check
npm test
npm run build
npx playwright install chromium
npm run test:browser
```

Las pruebas de navegador usan identidad y documentos sintéticos y contratos HTTP simulados. No prueban una integración Google/Groq en vivo ni certifican cumplimiento WCAG completo. La verificación integral de servicios se documenta en [`docs/release`](../../docs/release/README.md).

Los comandos `dev` y `preview` escuchan en `127.0.0.1` de forma predeterminada, conforme al alcance local del proyecto. Playwright sirve `dist/` con `vite preview` en loopback: ejecuta `npm run build` antes de las pruebas de navegador. `npm run format` aplica el formato de código de `src/`.

El job de frontend de CI usa la imagen oficial de Playwright con los navegadores preinstalados. Si cambia la versión de `@playwright/test` en el lockfile, actualiza la etiqueta y el digest de la imagen en el [workflow de CI rápido](../../.github/workflows/ci-fast.yml).

## Design System

`shared/styles/tokens.css` define superficies, texto, acento, estados, foco, radios, espacios y elevación para ambos temas (`light` y `dark`). Los estilos se distribuyen en `primitives.css`, `navigation.css`, `chat.css` (incluyendo selectores y paneles agénticos `.agent-*`), `documents.css`, `integrations.css` (incluyendo tarjetas, tablas y alertas compartidas `.settings-ai-*` y `.ui-*` para Configuración IA, Knowledge Studio y Auditoría) y `dialogs.css`. Perfil y administración mantienen sus hojas locales y consumen los mismos tokens.

Las suites de Playwright ejecutan `@axe-core/playwright` (`AxeBuilder`) tanto en tema claro como en tema oscuro sobre las vistas principales y operativas (`/login`, `/`, `/documents`, `/settings/ai`, `/studio`, `/admin/audit` y `AgentRunPanel`).

El diseño Floating Glass usa el púrpura Blandskron `#4A148C` y el púrpura profundo `#2E0B59`. Los contenedores principales usan las superficies translúcidas, los bordes iluminados y la elevación de los tokens `--glass*`. Los controles de lectura y edición usan superficies de mayor opacidad. Las preferencias de menor transparencia, mayor contraste y colores forzados activan superficies sólidas. La interfaz respeta la preferencia de movimiento reducido.

El símbolo y el logotipo horizontal provienen de la guía de marca de Blandskron. Inter 4.1 se sirve desde el repositorio y conserva su aviso de licencia. [Inter](https://github.com/rsms/inter/tree/v4.1) · [SIL Open Font License](../public/fonts/OFL-Inter.txt)

Usa `Button` para nuevas acciones y `IconButton` para controles con iconos y nombre accesible. `ModalDialog` centraliza foco, Escape, contención y restitución al disparador; los formularios pueden indicar `initialFocusRef`. Las vistas de selección por URL usan navegación y estado actual anunciado, sin fingir un widget de pestañas.

Context conserva sesión y tema. El tema valida el valor almacenado y usa la preferencia del sistema al entrar por primera vez. La sesión distingue credenciales renovadas de identidad/tenant; no agregues JWT a las dependencias de un editor ni traslades borradores a un store global.

Los clientes HTTP distinguen JSON y blobs por tipos; los adaptadores de cada endpoint mantienen DTO y normalización, con las validaciones de formato existentes. TypeScript no sustituye la validación de datos externos ni la autorización del servidor.

## Dependencias y alcance

`npm run audit:dependencies` ejecuta la auditoría de npm y bloquea los hallazgos nuevos. Admite temporalmente GHSA-fc5q-39xc-vjpf para la copia transitiva de `picomatch` 4.0.7 y su cadena actual de Vite y TypeScript ESLint. La aplicación recibe texto y documentos, mientras que los patrones glob de compilación y lint se definen en el repositorio. La imagen final distribuye los archivos compilados con Nginx. Cuando se publique una versión corregida compatible, actualiza el lockfile y retira la excepción. [Aviso de picomatch](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)

Las incorporaciones son herramientas de desarrollo: TypeScript/tipos, ESLint, Prettier y axe. `minimatch` está fijado por override a una versión corregida de la línea 11 para las herramientas de desarrollo, por [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249); el lockfile y las comprobaciones se validan con esa resolución. No se añadió un framework de estilos, routing ni estado.

Las referencias técnicas principales son [TypeScript strict](https://www.typescriptlang.org/tsconfig/strict), [React lazy](https://react.dev/reference/react/lazy) y [Disclosure de WAI-ARIA](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/).
