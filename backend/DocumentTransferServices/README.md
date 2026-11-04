# DocumentTransferServices

## Overview
DocumentTransferServices es un microservicio basado en FastAPI responsable de gestionar y registrar transferencias de documentos (subidas y descargas). Permite crear, listar, actualizar y limpiar el historial de transferencias, integrándose en una arquitectura de microservicios con autenticación JWT y persistencia en PostgreSQL.

## Features
- Registro de transferencias de documentos (UPLOAD/DOWNLOAD)
- Listado de transferencias recientes
- Actualización de estado y progreso de transferencias
- Limpieza del historial de transferencias completadas, fallidas o canceladas
- Endpoints autenticados vía JWT
- Health checks
- CORS para integración frontend

## API Endpoints

### Health
- `GET /api/v1/health` — Verifica el estado del servicio
- `GET /api/v1/health/db` — Verifica la conectividad con la base de datos

### Transferencias (Authenticated)
- `GET /api/v1/transfers` — Lista transferencias recientes (parámetro: limit)
- `POST /api/v1/transfers` — Crea un registro de transferencia
- `PATCH /api/v1/transfers/{transfer_id}` — Actualiza una transferencia
- `DELETE /api/v1/transfers/history` — Limpia el historial de transferencias completadas/fallidas/canceladas

## Data Models

### TransferResponse
- `transfer_id`: str
- `owner_user_id`: str
- `document_id`: str | None
- `filename`: str
- `direction`: "UPLOAD" | "DOWNLOAD"
- `status`: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED"
- `progress`: int (0-100)
- `size_bytes`: int | None
- `metadata`: dict
- `created_at`: datetime | None
- `updated_at`: datetime | None

### TransferCreateRequest
- `filename`: str
- `direction`: "UPLOAD" | "DOWNLOAD"
- `status`: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED" (default: "PENDING")
- `progress`: int (default: 0)
- `document_id`: str | None
- `size_bytes`: int | None
- `metadata`: dict

### TransferUpdateRequest
- `status`: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED" | None
- `progress`: int | None
- `document_id`: str | None
- `size_bytes`: int | None
- `metadata`: dict | None

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
4. O usa Docker: `docker build -t document-transfer-services . && docker run ...`

## Example Requests

**Crear transferencia**
```json
POST /api/v1/transfers
{
  "filename": "contrato.pdf",
  "direction": "UPLOAD",
  "status": "PENDING",
  "progress": 0,
  "document_id": null,
  "size_bytes": 123456,
  "metadata": {}
}
```

**Actualizar transferencia**
```json
PATCH /api/v1/transfers/{transfer_id}
{
  "status": "COMPLETED",
  "progress": 100
}
```

## License
Este proyecto está licenciado bajo los términos del archivo LICENSE del repositorio.
