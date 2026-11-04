# DocumentLibraryServices

## Overview
DocumentLibraryServices es un microservicio basado en FastAPI responsable de la gestión de carpetas, organización de documentos, favoritos y acceso a la biblioteca documental. Permite a los usuarios organizar documentos en carpetas, marcar favoritos y consultar documentos recientes, integrándose en una arquitectura de microservicios con autenticación JWT y persistencia en PostgreSQL.

## Features
- CRUD de carpetas (crear, listar, actualizar, eliminar)
- Organización de documentos en carpetas
- Gestión de documentos favoritos
- Consulta de documentos recientes
- Endpoints autenticados vía JWT
- Health checks
- CORS para integración frontend

## API Endpoints

### Health
- `GET /api/v1/health` — Verifica el estado del servicio
- `GET /api/v1/health/db` — Verifica la conectividad con la base de datos

### Carpetas (Folders)
- `GET /api/v1/folders` — Lista carpetas (opcionalmente por carpeta padre)
- `POST /api/v1/folders` — Crea una nueva carpeta
- `PATCH /api/v1/folders/{folder_id}` — Actualiza una carpeta
- `DELETE /api/v1/folders/{folder_id}` — Elimina una carpeta
- `GET /api/v1/folders/{folder_id}/documents` — Lista documentos en una carpeta
- `POST /api/v1/folders/{folder_id}/documents/{document_id}` — Añade un documento a una carpeta
- `DELETE /api/v1/folders/{folder_id}/documents/{document_id}` — Elimina un documento de una carpeta

### Biblioteca y Favoritos
- `GET /api/v1/library/recent` — Lista documentos recientes
- `GET /api/v1/library/favorites` — Lista documentos favoritos
- `POST /api/v1/library/favorites/{document_id}` — Añade un documento a favoritos
- `DELETE /api/v1/library/favorites/{document_id}` — Elimina un documento de favoritos

## Data Models

### Folder
- `folder_id`: str
- `name`: str
- `parent_folder_id`: str | None
- `owner_user_id`: str
- `metadata`: dict
- `created_at`: datetime
- `updated_at`: datetime

### Document
- `document_id`: str
- `filename`: str
- `mime_type`: str
- `status`: str
- `updated_at`: datetime

### DeleteResponse
- `deleted`: bool

### CountResponse
- `count`: int

## Authentication
Todos los endpoints (excepto health checks) requieren un JWT válido en el header `Authorization: Bearer <token>`. El token se valida con la clave pública RSA configurada y debe tener `token_type: access`.

## Architecture
- **FastAPI** para la capa API
- **SQLAlchemy** para ORM/acceso a base de datos
- **PostgreSQL** como base de datos
- **Pydantic** para validación de requests/responses
- **Docker** para contenerización
- **CORS** habilitado para integración frontend

## Project Structure
- `app/main.py`: Setup de FastAPI, middleware, manejo de errores
- `app/interfaces/api/router.py`: Registro de rutas y endpoints
- `app/interfaces/api/v1/routes/`: Implementación de endpoints
- `app/application/use_cases/`: Lógica de negocio
- `app/infrastructure/database/`: Modelos, repositorios, conexión a BD
- `app/config/`: Configuración, seguridad, logging
- `app/shared/`: Clases de error compartidas

## Running the Service
1. Instala dependencias: `pip install -r requirements.txt`
2. Configura variables de entorno o edita el archivo de configuración
3. Ejecuta con Uvicorn: `uvicorn app.main:app --reload`
4. O usa Docker: `docker build -t document-library-services . && docker run ...`

## Example Requests

**Crear carpeta**
```json
POST /api/v1/folders
{
  "name": "Proyectos",
  "parent_folder_id": null,
  "metadata": {}
}
```

**Añadir documento a favoritos**
```
POST /api/v1/library/favorites/{document_id}
Authorization: Bearer <token>
```

## License
Este proyecto está licenciado bajo los términos del archivo LICENSE del repositorio.
