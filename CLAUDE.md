# Developer Guide

## Commands

### Environment Management
- Start services: `docker compose up -d`
- Stop services: `docker compose down`
- Check logs: `docker compose logs`
- View service status: `docker compose ps`
- Run config validation: `docker compose config`

### Local Execution and Verification
- Airflow UI: http://localhost:8080
- MinIO Console: http://localhost:9001
- MinIO API: http://localhost:9000
- PostgreSQL Port: 5432
- Redis Port: 6379
- Kafka Port: 9092

## Behavioral Guidelines

- **Think Before Coding**: State assumptions explicitly before creating file structures or drafting architecture.
- **Simplicity First**: Write the absolute minimum configuration necessary to establish a clean development environment.
- **Surgical Execution**: Do not add speculative tools or configuration directories beyond what is specified.
- **Goal-Driven Execution**: State a brief step-by-step initialization plan and verify success criteria at each checkpoint.
- **No Code Comments**: All source code, orchestration workflows, dbt layers, and scripts must be completely self-documenting. Absolutely no comments, explanatory notes, or prose are permitted within any files.
