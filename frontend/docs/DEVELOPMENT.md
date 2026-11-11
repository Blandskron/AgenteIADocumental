# Frontend documental

React 19, Vite y TypeScript. Node 24 es la versión de desarrollo y CI. La API conserva sus contratos; ningún secreto de servidor debe llegar a las variables `VITE_*`.

## Decisiones de la auditoría (2026-11-10)

La separación existente `app → pages → widgets/features → entities/shared` es útil y se conserva. Los controladores ya protegen operaciones asíncronas y cambios de cuenta/tenant; sustituirlos por un store global duplicaría estado y arriesgaría esas garantías. Context mantiene sesión y tema; cada funcionalidad conserva su estado local y sus controladores.

Los principales déficits eran JavaScript sin comprobación estática, ausencia de linting, imports profundos, todas las páginas en el bundle inicial, una biblioteca de 1.113 líneas y estilos acumulados con colores independientes del tema. También había acciones anidadas, controles sin acción y navegación móvil insuficiente.

La modernización introduce contratos TypeScript estrictos, alias `@/`, carga por página con recuperación de errores, separación de secciones y componentes accesibles. No requiere Redux, Zustand, Tailwind ni una biblioteca completa de UI: el tamaño y los flujos actuales no lo justifican. La inspiración Fluent/shadcn se expresa con superficies, radios, foco, tipografía y tokens semánticos propios, sin copiar sus implementaciones.

## Convenciones

- `app/`: configuración, proveedores y navegación; `pages/`: composición de pantallas.
- `features/`: API, controladores, hooks y UI del dominio; `entities/`: modelos compartidos.
- `shared/`: primitivas visuales, layout, HTTP, almacenamiento y tokens. No importa páginas ni funcionalidades.
- Usa `@/` entre capas; una ruta relativa corta es válida dentro del mismo componente.
- Conserva el aislamiento por sesión, tenant y generación de solicitud. Los permisos de UI son orientativos: la autorización efectiva pertenece al servidor.
- Los mensajes y documentos se renderizan como texto; evita HTML sin sanitizar. Las URL de avatar y los downloads conservan su contrato privado.
- No persistas contraseñas ni claves. El almacenamiento de tokens existente es un límite de la arquitectura actual: migrar a cookies HttpOnly requiere cambios coordinados del backend y queda fuera de este trabajo.

## Verificación

```powershell
npm ci
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

El job de frontend de CI usa la imagen oficial de Playwright con los navegadores preinstalados. Si cambia la versión de `@playwright/test` en el lockfile, actualiza la etiqueta y el digest de la imagen en el [workflow de validación](../../.github/workflows/validate.yml).

## Design System

`shared/styles/tokens.css` define superficies, texto, acento, estados, foco, radios, espacios y elevación para ambos temas. Los estilos se distribuyen en primitivas, navegación, chat, documentos, integraciones y diálogos. Perfil y administración mantienen sus hojas locales y consumen los mismos tokens.

Usa `Button` para nuevas acciones y `IconButton` para controles con iconos y nombre accesible. `ModalDialog` centraliza foco, Escape, contención y restitución al disparador; los formularios pueden indicar `initialFocusRef`. Las vistas de selección por URL usan navegación y estado actual anunciado, sin fingir un widget de pestañas.

Context conserva sesión y tema. El tema valida el valor almacenado y usa la preferencia del sistema al entrar por primera vez. La sesión distingue credenciales renovadas de identidad/tenant; no agregues JWT a las dependencias de un editor ni traslades borradores a un store global.

Los clientes HTTP distinguen JSON y blobs por tipos; los adaptadores de cada endpoint mantienen DTO y normalización, con las validaciones de formato existentes. TypeScript no sustituye la validación de datos externos ni la autorización del servidor.

## Dependencias y alcance

Las incorporaciones son herramientas de desarrollo: TypeScript/tipos, ESLint, Prettier y axe. `minimatch` está fijado por override a una versión corregida de la línea 11 para las herramientas de desarrollo, por [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249); el lockfile y las comprobaciones se validan con esa resolución. No se añadió un framework de estilos, routing ni estado.

El [informe de auditoría](../AUDIT.md) registra decisiones, comprobaciones y límites. Las referencias técnicas principales son [TypeScript strict](https://www.typescriptlang.org/tsconfig/strict), [React lazy](https://react.dev/reference/react/lazy) y [Disclosure de WAI-ARIA](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/).
