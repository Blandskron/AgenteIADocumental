# Guía de Marca — KronDocs: Document Intelligence

> **Marca:** KronDocs  
> **Descriptor:** Document Intelligence  
> **Eslogan:** *Turn Documents into Intelligence.*  
> **Firma:** *Open Source · By BLANDSKRON*  
> **Repositorio oficial:** `https://github.com/Blandskron/AgenteIADocumental`

---

## 1. Propósito y Posicionamiento

**KronDocs** es el nombre oficial de la plataforma open source de inteligencia documental de **BLANDSKRON** (anteriormente denominada *AgenteIADocumental* / *Blandskron Documental*). Forma parte del ecosistema KRON, diseñado para organizaciones que necesitan convertir acervos documentales privados en conocimiento accionable con trazabilidad verificable, control de acceso multiempresa y libertad de proveedor de IA (Groq en la nube u Ollama local).

### Atributos de marca
- **Conocimiento:** Lectura serena, jerarquía editorial y citas clicables ancladas a fuentes reales.
- **Inteligencia:** Recuperación híbrida (`pgvector` HNSW + FTS + RRF), orquestación agéntica y sandbox aislado.
- **Organización:** Estructura modular tipo *Modern Knowledge Workspace* y *Bento Grid*.
- **Confianza:** Contraste WCAG 2.2 AA verificado, aislamiento multiempresa, auditoría persistente y aprobación *Human-in-the-Loop*.

---

## 2. Arquitectura de Marca y Conexión con BLANDSKRON

KronDocs hereda el ADN de ingeniería sobria, precisión geométrica y claridad técnica del sitio corporativo de **BLANDSKRON** (`blandskron.cl` / `Blandskron/blandskronSPA`):

- **Eyebrows técnicos en `JetBrains Mono`:** Encabezados de sección en mayúsculas con espaciado abierto (`0.12em`) precedidos por un marcador cuadrado (`7×7 px`, `rx 2 px`).
- **Puente cromático BLANDSKRON → KRON:** El violeta corporativo de Blandskron (`#4A148C` / `#2E0B59` / `#8B5CF6`) evoluciona hacia **Cognitive Violet (`#A78BFA`)** como acento de síntesis e IA, articulado sobre un núcleo azul técnico (**Knowledge Blue `#699BFF`**, **Intelligence Blue `#3B82F6`**, **Discovery Cyan `#38BDF8`**).
- **Tipografía local-first:** Todas las fuentes se sirven desde el propio repositorio bajo licencia **SIL Open Font License 1.1**, sin dependencias de CDN ni telemetría de terceros.

---

## 3. Sistema de Logotipos e Isotipo

El isotipo de KronDocs fusiona una **K geométrica arquitectónica** con un **folio documental** y **nodos de conocimiento interconectados**:
- **Pilar vertical:** Estabilidad estructural y gobernanza de datos.
- **Folio documental trasero:** Documentos fuente preservados con integridad.
- **Brazo superior hacia nodo Discovery Cyan (`#38BDF8`):** Recuperación semántica y descubrimiento.
- **Brazo inferior hacia nodo Cognitive Violet (`#A78BFA`):** Síntesis inteligente y generación controlada.

### Recursos oficiales en `frontend/public/`

| Recurso | Ruta | Uso recomendado |
| :--- | :--- | :--- |
| **Isotipo a color** | [krondocs-isotipo.svg](../frontend/public/brand/krondocs-isotipo.svg) | App sidebar colapsado, estado inicial del chat, avatares del asistente, badges |
| **Lockup horizontal (Dark)** | [krondocs-logo-dark.svg](../frontend/public/brand/krondocs-logo-dark.svg) | Cabeceras y materiales sobre fondos oscuros (`#0B1020`, `#121A2D`) |
| **Lockup horizontal (Light)** | [krondocs-logo-light.svg](../frontend/public/brand/krondocs-logo-light.svg) | Documentación clara, exportaciones y fondos claros (`#F5F7FB`, `#FFFFFF`) |
| **Isotipo monocromático (Dark BG)** | [krondocs-isotipo-mono-dark.svg](../frontend/public/brand/krondocs-isotipo-mono-dark.svg) | Sellos, marcas de agua y salidas monocromáticas sobre oscuro |
| **Isotipo monocromático (Light BG)** | [krondocs-isotipo-mono-light.svg](../frontend/public/brand/krondocs-isotipo-mono-light.svg) | Documentos impresos, PDFs y fondos claros monocromáticos |
| **Favicon SVG** | [favicon.svg](../frontend/public/favicon.svg) | Pestañas de navegador, PWA y marcadores |

### Área de respeto y tamaños mínimos
- **Área de respeto:** Conservar un margen libre mínimo equivalente al ancho del pilar vertical de la K (`0.25 × altura del isotipo`) en los cuatro lados.
- **Tamaño mínimo:** `20×20 px` para el isotipo; `140 px` de ancho para el lockup horizontal con descriptor.
- **Usos prohibidos:** No deformar proporciones, no invertir la K, no colocar el lockup oscuro sobre fondos claros ni reemplazar `KronDocs` por tipografías condensadas o decorativas ajenas al sistema.

---

## 4. Paleta Oficial y Verificación WCAG 2.2 AA

### Colores principales de marca

| Nombre | Hex | Rol visual |
| :--- | :--- | :--- |
| **Knowledge Blue** | `#699BFF` | Acento primario en Dark Mode, foco visual, nodos del isotipo y acciones principales |
| **Intelligence Blue** | `#3B82F6` | Núcleo de marca, gradientes vectoriales, bordes de acento y estados activos |
| **Cognitive Violet** | `#A78BFA` | Indicadores de generación IA, Knowledge Studio y acentos cognitivos |
| **Discovery Cyan** | `#38BDF8` | Indicadores de foco accesible en Dark Mode, nodos de descubrimiento y badges informativos |

> **Ajuste de accesibilidad documentado:** En botones sólidos con texto blanco `#FFFFFF`, `#3B82F6` alcanza `3.67:1` (insuficiente para WCAG AA 4.5:1 en texto normal). Por ello:
> - En **Dark Mode**, `--primary` usa `#699BFF` con texto `--primary-foreground: #0B1020` (**contraste 7.3:1, AAA**).
> - En **Light Mode**, `--primary` usa `#1D4ED8` con texto `#FFFFFF` (**contraste 6.7:1, AA/AAA**), reservando `#3B82F6` y `#699BFF` para bordes, gradientes e iconografía grande.

### Neutros de superficie y texto

| Token | Dark Mode (por defecto) | Light Mode | Uso |
| :--- | :--- | :--- | :--- |
| `--background` | `#0B1020` | `#F5F7FB` | Lienzo base de la aplicación |
| `--navigation` | `#121A2D` | `#EDF2FA` | Navegación lateral y cabeceras secundarias |
| `--surface` | `#182338` | `#FFFFFF` | Tarjetas, paneles e inputs |
| `--border` | `#2A3652` | `#D0DAEB` | Divisores sutiles y contornos de contenedores |
| `--foreground` | `#F5F7FB` | `#0B1020` | Texto principal (contraste > 13:1) |
| `--foreground-muted` | `#B8C2D9` | `#3F4D68` | Texto secundario, descripciones y metadatos |

### Colores semánticos

| Estado | Primitivo | Texto/Icono en Dark Mode | Texto/Icono en Light Mode | Uso en KronDocs |
| :--- | :--- | :--- | :--- | :--- |
| **Success** | `#22C55E` | `#4ADE80` | `#15803D` | Documentos procesados, firmas completadas, conexión verificada |
| **Warning** | `#F59E0B` | `#FBBF24` | `#B45309` | Aprobación humana pendiente (HITL), citas desvinculadas |
| **Error** | `#EF4444` | `#F87171` | `#B91C1C` | Errores de validación, rechazos, fallos de red o permiso |
| **Info** | `#38BDF8` | `#38BDF8` | `#0369A1` | Ejecuciones activas, pistas operativas y foco nocturno |
| **AI Generated** | `#A78BFA` | `#C4B5FD` | `#6D28D9` | Etiquetas de respuesta asistida por IA y estudio cognitivo |
| **Verified Source** | `#14B8A6` | `#2DD4BF` | `#0F766E` | Citas clicables `[Fuente N]`, fragmentos verificados y procedencia |
| **Pending** | `#64748B` | `#94A3B8` | `#475569` | Estados en cola, cancelados o en espera |

---

## 5. Sistema Tipográfico

| Rol | Familia | Formato autohospedado | Licencia | Uso |
| :--- | :--- | :--- | :--- | :--- |
| **Display / Títulos** | `Sora` | `sora-latin*.woff2` | SIL OFL 1.1 | `h1`–`h4`, títulos de vista, wordmark y métricas KPI |
| **UI / Interfaz** | `Inter` | `inter-variable.woff2` | SIL OFL 1.1 | Navegación, controles, formularios, tablas y mensajes estándar |
| **Lectura extensa** | `Source Serif 4` | `source-serif-4-latin*.woff2` | SIL OFL 1.1 | Modo de lectura editorial en respuestas largas y vistas de análisis |
| **Código / Metadatos** | `JetBrains Mono` | `jetbrains-mono-latin*.woff2` | SIL OFL 1.1 | Bloques de código, citas `[Fuente N]`, eyebrows, logs y Code Mode |

---

## 6. Tono Editorial y Convenciones de Copy

- **Directo, técnico y verificable:** Evitar promesas vagas. Indicar siempre qué ocurre y de dónde proviene la información (ej. *"Fuentes verificadas"*, *"Aprobación humana requerida"*).
- **Español claro como idioma principal de interfaz** con términos técnicos universales reconocidos cuando aportan precisión (*Code Mode*, *Knowledge Studio*, *Open Source · By BLANDSKRON*).
- **Compatibilidad nominal:** En guías de migración o despliegue heredado, referenciar explícitamente que KronDocs corresponde al repositorio `Blandskron/AgenteIADocumental` (antes *Blandskron Documental*).
