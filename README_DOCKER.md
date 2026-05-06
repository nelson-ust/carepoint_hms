# Docker Deployment Guide for Carepoint HMS

This project is configured for containerized deployment using Docker.

## Files Included
- `Dockerfile`: Multi-stage, production-ready build using Python 3.10-slim.
- `docker-compose.yml`: Orchestrates the FastAPI app and PostgreSQL database.
- `.dockerignore`: Optimizes image size by excluding unnecessary files.
- `scripts/entrypoint.sh`: Handles database initialization and starts the Gunicorn server.

## Local Development / Quick Start
To start the entire stack locally:
```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`.

## Production Deployment with Docker Registry

### 1. Build and Tag the Image
Replace `your-registry.com` and `your-project` with your actual registry details (e.g., Docker Hub, AWS ECR, or Google Artifact Registry).

```bash
docker build -t your-registry.com/your-project/carepoint-hms:latest .
```

### 2. Push to Registry
```bash
docker push your-registry.com/your-project/carepoint-hms:latest
```

### 3. Deploy on Production Server
On your production server, you can use the `docker-compose.yml` file. Update the `image` field for the `app` service to point to your registry.

```yaml
services:
  app:
    image: your-registry.com/your-project/carepoint-hms:latest
    # ... other config ...
```

Then run:
```bash
docker-compose up -d
```

## Security Notes
- The Dockerfile runs as a non-root `appuser`.
- Ensure your `.env` file contains strong passwords for `POSTGRES_PASSWORD` and `DATABASE_ENCRYPTION_KEY`.
- In production, it is recommended to use a managed database service (RDS, Cloud SQL, etc.) and update the `DATABASE_URL` accordingly.
