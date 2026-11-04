# Docker Compose Layout

El stack esta separado por dominio para que el despliegue siga creciendo sin volver inmanejable el archivo principal.

## Levantar todo

```bash
docker compose up --build
```

`docker-compose.yml` usa `include` y carga solo el stack documental:

- `compose/infra.yml`
- `compose/auth.yml`
- `compose/documents.yml`
- `compose/collaboration.yml`
- `compose/profile.yml`
- `compose/frontend.yml`

## Levantar dominios parciales

Infraestructura y autenticacion:

```bash
docker compose -f compose/infra.yml -f compose/auth.yml up --build
```

Servicios documentales:

```bash
docker compose -f compose/infra.yml -f compose/auth.yml -f compose/documents.yml -f compose/collaboration.yml -f compose/profile.yml up --build
```

Frontend con todo el backend:

```bash
docker compose up --build blandskron-frontend
```
