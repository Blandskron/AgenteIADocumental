# Blandskron Documental

Aplicación de portafolio para cargar y organizar documentos, buscar por contenido y hacer preguntas con fuentes. La interfaz permite revisar los fragmentos recuperados, guardar conversaciones y exportar una respuesta a PDF.

La web usa React y TypeScript. Django administra la identidad y once servicios de aplicación en total cubren el recorrido documental. La ingesta y el chat calculan embeddings en CPU. PostgreSQL con pgvector almacena los vectores y el chat envía a Groq la pregunta y el contexto recuperado según los permisos vigentes.

| Guía | Contenido |
| --- | --- |
| [Arquitectura](docs/architecture.md) | Topología, límites de confianza, secuencia de ingesta, RAG y exportación, y mapa de servicios. |
| [Operación local](docs/operations.md) | Arranque, configuración, diagnóstico, actualización y mantenimiento. |
| [Verificación de entrega](docs/release/README.md) | Suite sintética, evidencias fechadas, auditoría de imágenes y alcance de CI. |
| [Frontend](frontend/README.md) | Estructura, convenciones, diseño y pruebas de la interfaz. |

## Probar en local

Necesitas Docker con Compose compatible con `include`. Desde la raíz, en PowerShell, crea el archivo de configuración si aún no existe.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edita `.env` y configura `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, `INITIAL_ADMIN_USERNAME` e `INITIAL_ADMIN_PASSWORD`. Añade `GROQ_API_KEY` para probar respuestas con el proveedor real. Usa valores propios y conserva el archivo fuera de Git.

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up -d --build --wait
```

1. Abre [la aplicación local](http://localhost:3000) e inicia sesión con el administrador inicial.
2. Carga un archivo de texto sintético que diga «El plazo del contrato de prueba es de 97 días». El primer uso descarga el modelo de embeddings.
3. Busca el documento, selecciónalo y pregunta «¿Cuál es el plazo del contrato?». Abre una fuente de la respuesta y exporta el mensaje a PDF. Puedes volver a descargarlo desde **Mis PDFs**.

Compose publica los puertos en loopback para desarrollo local. Google Drive es opcional y arranca deshabilitado. Para ejecutar el recorrido integral con Groq simulado y sin credenciales personales, sigue la [guía de verificación](docs/release/README.md).

## Colaboración

Consulta las [reglas de colaboración](AGENTS.md), las [pautas de contribución](CONTRIBUTING.md), el [canal de reporte de vulnerabilidades](SECURITY.md) y la [licencia](LICENSE). El proyecto conserva su licencia con reserva de derechos.
