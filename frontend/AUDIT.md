# Auditoría y modernización de frontend — 2026-11-10

## Alcance y diagnóstico

Base: `main` en `f8d9aec`. Se revisaron las pantallas de acceso, chat, biblioteca, asignaciones/notificaciones, integraciones, perfil y administración; sus clientes, controladores, almacenamiento, estilos y regresiones. No se modificaron servicios, esquema, secretos ni datos. Las únicas adaptaciones fuera de `frontend/` son los gates de lint/tipos en CI y el selector de contraseña de la prueba transversal para admitir la etiqueta en español.

La base tenía 34 archivos JSX y 61 archivos JavaScript, sin TypeScript ni ESLint. La biblioteca concentraba 1.113 líneas y `components.css` acumulaba 3.673, con capas históricas superpuestas. Todas las páginas se importaban al entrar. El historial anidaba acciones interactivas; varias sugerencias y controles no tenían acción. La navegación móvil y los estados de foco carecían de un contrato uniforme. Los controladores de operaciones, la paginación y la separación por funcionalidades ya aportaban valor y tenían regresiones útiles.

## Decisiones e implementación

| Área | Decisión y resultado |
| --- | --- |
| Arquitectura | Mantener `app/pages/widgets/features/entities/shared`; extraer diálogos y vistas de asignaciones, biblioteca, Drive y paneles de administración. Retirar seis módulos de UI/hooks sin consumidores, incluido un diálogo antiguo sin contención de foco. |
| Tipos | Migrar todo el código de `src/` a TS/TSX, con `strict`, parámetros/locales sin usar y fallthrough comprobados. Sin `allowJs`, `any` explícito ni exclusiones de tipos para el código de aplicación. Modelos de sesión, documentos, conversación, perfil y Drive; DTO por endpoint. |
| Entrega | Excepción local a la regla Python `lib/` de Git para conservar los módulos TypeScript de aplicación. LF explícito en frontend y exclusión de `.env*`, pruebas y artefactos del contexto Docker. |
| Estado | Conservar Context para sesión/tema y controladores por funcionalidad. Una fábrica crea los clientes de sesión; renovar credenciales no cambia el propietario de una operación. No se añade Redux/Zustand ni se duplica estado remoto. |
| Routing | Conservar las URL estáticas; un hook concentra History/Popstate, normalización y título por vista. Páginas con `lazy`/`Suspense` y recuperación de errores en la raíz. No se necesita otro router para este contrato. |
| Diseño | Tokens semánticos claros/oscuros, superficies sobrias, acento verde, radios y elevación consistentes. CSS separado por dominio; botones tipados, diálogos nativos, formularios y estados compartidos. Inspiración Fluent/shadcn, sin incorporar sus bibliotecas. |
| UX | Sugerencias del chat rellenan preguntas útiles; se retiran el filtro y selector de modelo sin acción. Búsqueda etiquetada, estado de vista comunicado, posibilidad de marcar notificaciones como leídas, errores recuperables y una sola creación ante envíos duplicados de carpeta. |
| Accesibilidad | Foco visible, salto al contenido, título por ruta, botones separados para abrir/eliminar conversación, disclosures con estado, Escape y restitución de foco, menú móvil modal, reducción de movimiento y soporte de colores forzados. |
| Seguridad | Se conservan los controles vigentes de sesión/tenant, PKCE, reintentos idempotentes y validación de descargas privadas. Vista previa en iframe con sandbox. Mensajes como texto y errores de render sin detalles internos. La autorización sigue en las APIs. |
| Rendimiento | Carga de páginas bajo demanda, sin incluir todas las funcionalidades en el acceso inicial. No se incorpora memoización indiscriminada ni virtualización sobre listas paginadas de 20/50 elementos. |

## Evidencia local

Validación con Node 24.15.0, npm 11.14.1 y Chromium. Todas las identidades y respuestas usadas por las pruebas web son sintéticas. Playwright sirve la compilación `dist/` con `vite preview` en loopback.

- Instalación limpia con `npm ci` y `npm audit --audit-level=low`: cero vulnerabilidades informadas en el grafo resuelto, incluidas herramientas de desarrollo, en esta fecha.
- `npm run lint`: sin errores ni advertencias; incluye reglas de hooks, imports por alias y prohibición de `any` explícito.
- `npm run typecheck` y `npm run format:check`: aprobados.
- `npm test`: 123 pruebas aprobadas, conservando regresiones de permisos, paginación, sesión, perfil, Drive, exportación y transferencias.
- `npm run build`: aprobado, con chunks separados para chat, documentos, perfil, administración e integraciones. El JS de entrada ocupa aproximadamente 247 kB / 79 kB gzip; no se atribuye una mejora porcentual sin una medición equivalente de la base.
- `npm run test:browser`: 35 pruebas aprobadas sobre producción, incluidas 14 nuevas de diseño, teclado, accesibilidad, recuperación y exclusión de envíos duplicados. Axe aplica etiquetas WCAG 2 A/AA, 2.1 AA y 2.2 AA. La cobertura automática incluye login, chat claro/oscuro, biblioteca/diálogo, móvil a 320/390 px, perfil, administración y aplicaciones en ambos temas.
- Se revisaron capturas sintéticas de login, chat claro/oscuro y biblioteca de escritorio/móvil; se conservan como artefactos locales de Playwright en `test-results/`.

## Límites y operación

Las reglas automáticas de axe y la revisión de teclado/capturas cubren las pantallas y estados probados. No equivalen a una certificación WCAG ni a una prueba exhaustiva con lectores de pantalla. No se ejecutó Google/Groq en vivo ni se sustituyó la verificación transversal real de servicios por los mocks web.

Los tokens existentes siguen en almacenamiento del navegador. Su traslado a cookies HttpOnly requiere un contrato coordinado de backend, CORS y CSRF y no se simula desde React. El escaneo de dependencias no es un nuevo escaneo de las imágenes Docker; la evidencia histórica de `docs/release/` se conserva con su alcance original.

No se desplegó ni reconstruyó el stack personal. Para revisar el resultado usa `npm run dev`; para publicar, integra el PR y reconstruye la imagen web siguiendo el procedimiento del repositorio. Los cambios de API y migraciones están fuera del alcance de esta entrega.
