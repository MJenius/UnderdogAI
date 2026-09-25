# UnderdogAI final validation report

Run date: 2026-09-25. Fresh database-backed ML evaluation: MLflow run `0c4c999edaa84b9da557019a54fac51c`. Final report and reproducibility manifest regenerated from the local landing data, MLflow artifacts, and the live fault matrix. Runtime datasets and model artifacts remain ignored under `runtime/` and `mlruns/`.

## Data lineage and temporal correctness

The verified path is raw CSV → Airflow ingestion → PostgreSQL raw tables → dbt staging/intermediate models → `fct_underdog_feature_mart` → Bayesian model/MLflow → API and Kafka worker inference. The MLflow run and [`reproducibility_manifest.json`](reproducibility_manifest.json) record the dataset/config identifiers, feature snapshot hash, training boundaries, model run ID, and evaluation outputs. The exact 23,697-row feature input is retained as the MLflow artifact `reproducibility/fresh_feature_dataset.csv`; its SHA-256 is `6ea1452c7c728ee4f537bdefdfde2efe2f2581f13bb267a26c3e2902d58e63a9`.

Airflow ingestion succeeded (three ingestion tasks, 6.07 seconds); dbt full refresh passed 7/7 models and dbt tests passed 5/5. The feature mart contains 49,413 rows (23,697 with both ranking features), from 1872-11-30 through 2026-06-13. The historical ranking as-of join check found **zero temporal join violations**. The chronological split is train before 2018-01-01, validation 2018-01-01 through 2019-12-31, and test from 2020-01-01. Training used 17,257 matches, validation 1,564, and test 4,876; validation remains reserved rather than used to select/calibrate hyperparameters.

## Fresh ML evaluation

Run `0c4c999edaa84b9da557019a54fac51c` completed with 500 tuning and 1,000 posterior draws across two chains; observed training duration was 631.14 seconds. The table values are from its MLflow `evaluation.json` artifact:

| Split | Rows | Log loss | Multiclass Brier |
|---|---:|---:|---:|
| Validation | 1,564 | 0.8884 | 0.5227 |
| Test | 4,876 | 0.9014 | 0.5290 |

Test one-vs-rest ECE was 0.0297 for home win, 0.0311 for draw, and 0.0216 for away win (macro ECE 0.0275). PyMC reported potential-energy overflow and low effective sample size for some parameters; only two chains ran. The separate elite calibration heuristic reported 62 violations. That heuristic is not a reliability metric. These diagnostics limit model confidence and should be resolved before operational decisions rely on its probabilities. Causal results remain observational under their stated adjustment assumptions; placebo, random-common-cause, and subset refuters are diagnostics, not proof of causality.

## Live local dependency fault tests

Fault injection used the local Docker Compose services. Redis and PostgreSQL were paused to keep service discovery stable while simulating an outage; Kafka was paused during its interruption case.

| Injection | Measured result |
|---|---|
| Redis unavailable | Readiness returned 503 in 0.511 s; valid simulation submission returned 503 in 0.508 s; task-status lookup returned 503 in 0.515 s. All were explicit and bounded. Readiness returned healthy after Redis resumed. |
| Kafka interruption | Simulation submission returned 503 in 5.005 s. Kafka returned healthy within 12 s after resume. |
| Worker stopped with queued task | Task `f076c5e2-3c8c-4cd0-bb5c-8a9b7c194382` stayed `PENDING` while the worker was stopped and reached `COMPLETED` within the 15-second restart observation window. |
| Duplicate completed task | Re-publishing completed task `f9ba4296-cafb-41b3-a283-d0b3d5c3fcdb` left it `COMPLETED`; no retry counter appeared and consumer lag returned to zero. |
| Short PostgreSQL pause | Task `3a5c04f3-3513-44fa-9809-7e50bab871d0` showed `RETRYING` during the pause and completed after PostgreSQL resumed. |
| Prolonged PostgreSQL pause | During an 18-second pause, task `f9ba4296-cafb-41b3-a283-d0b3d5c3fcdb` reached persistent `RECOVERABLE` after the retry budget, then returned to `RETRYING`; it completed after PostgreSQL resumed. No accepted task was silently lost. |

Worker offsets are committed only after result/status persistence; after retry exhaustion the accepted Kafka record stays uncommitted and the same offset is retried after a 5-second backoff. `RECOVERABLE` has no expiry so an exhausted task is not silently labeled as failed or forgotten. Redis remains the task status/result store; if it is unavailable, API calls fail explicitly and the worker still seeks the uncommitted Kafka message. Kafka topic retention is the upper bound on queue durability during a database outage that outlasts retention.

## Validation results and freeze decision

- `python -m pytest -q`: **29 passed**.
- Strict CI flake8 checks (`E9,F63,F7,F82`): **0 errors**. Advisory flake8 scan reports pre-existing style findings and is configured in CI with `--exit-zero`.
- Frontend `npm run lint`: **0 errors, 7 warnings**; `npm run build`: passed including TypeScript and static generation.
- `docker compose config --quiet`: passed. Updated API and worker images built and ran; the worker package entry point was corrected so its container imports and consumes tasks. The existing gRPC service registration now tolerates the repository's pinned grpcio runtime; the service port was open after startup.
- Live Redis, Kafka, worker, duplicate-task, and short/prolonged PostgreSQL recovery checks: passed as summarized above.

**Freeze decision: ready to freeze as a reproducible project snapshot.** Model diagnostics are documented limitations, not claims of production calibration. Keep the run artifacts referenced in the manifest, and do not describe observational causal outputs as proven effects. The Kafka retention window and status/result dependence on Redis remain operational limits.

## Reproduction

```powershell
docker compose up -d db redis minio zookeeper kafka airflow-db airflow-webserver airflow-scheduler
docker compose exec -T airflow-webserver airflow dags trigger elt_underdog_pipeline
docker run --rm --network underdogai_default -e DBT_HOST=db -e DBT_PORT=5432 -v "${PWD}/dbt:/app/dbt" underdog-dbt:test dbt run --full-refresh
docker run --rm --network underdogai_default -e DBT_HOST=db -e DBT_PORT=5432 -v "${PWD}/dbt:/app/dbt" underdog-dbt:test dbt test
python -m pip install -r requirements-model.txt
$env:POSTGRES_HOST='localhost'; $env:POSTGRES_PORT='5433'; $env:POSTGRES_DB='analytical_sandbox'; $env:POSTGRES_USER='postgres'; $env:POSTGRES_PASSWORD='postgres'; $env:MLFLOW_TRACKING_URI='sqlite:///mlflow.db'; $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; python src/models/bayesian_match_engine.py
python benchmarks/flagship_report.py
python -m pytest -q
docker compose up -d --build api worker
```
