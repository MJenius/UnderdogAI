# UnderdogAI

Decision Intelligence and Predictive Football Analytics Platform designed to identify underdogs and predict match/tournament-level upset probabilities at FIFA World Cups.

## System Architecture

### Data Ingestion & ELT
- **Orchestration**: Apache Airflow managing local pipeline DAGs.
- **Extraction**: Extracting raw values (`results.csv`, `shootouts.csv`, `fifa_ranking-2026-01-19.csv`) from local storage.
- **Processing**: Schema enforcement using local Python validation.
- **Target**: Local analytical database engine (PostgreSQL).

### Analytics Engineering
- **Transformation**: dbt Core models managing analytics pipelines.
- **Feature Engineering**: Calculates temporal rolling form factors.
- **Match Matrices**: Dynamic match weighting using international tournament criteria.

### Decision Intelligence Core
- **Uncertainty Quantification**: Bayesian Match Simulation engine written in PyMC.
- **Treatment Effect Analysis**: Causal Inference tracking layout written in DoWhy to isolate historical match treatment effects.

### Microservices Layer
- **APIs**: FastAPI engines for distributed scenario simulations and predictions.
- **Communication**: Typed gRPC data contracts for internal microservice RPCs.
- **Event Mesh**: Apache Kafka event broker for asynchronous updates.

### Observability Layer
- **Telemetry**: OpenTelemetry pipelines tracking system metrics, prediction latencies, and input drift.
- **Monitoring**: Prometheus and Grafana local instances.

### Deployment Mechanics
- **Infrastructure-as-Code**: Terraform configuration blocks targeting AWS (S3, EKS, Redshift).
- **Local Validation**: Minikube or Kind for local Kubernetes orchestration, S3 emulators for local object storage testing.

## Local Directory Structure

- `data/landing`: Raw data landing zone for CSV files.
- `docker-compose.yml`: Multi-service local environment setup.
- `README.md`: System documentation and architecture mapping.
- `CLAUDE.md`: Style guidelines, commands, and behavior constraints.
