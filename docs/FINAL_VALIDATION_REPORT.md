# UnderdogAI final validation report

Run date: 2026-09-25. Database-backed work used the checked-out implementation at commit `3cf1bb2` plus the local Airflow Compose mount fix. Generated datasets and model artifacts remain in ignored `runtime/` and `mlruns/` paths.

## Fresh data and model run

- Airflow DAG `elt_underdog_pipeline`: success; all three ingestion tasks completed in 6.07 seconds.
- dbt full refresh: 7/7 models passed; feature mart contains 49,413 rows, 23,697 with both ranking features, covering 1872-11-30 through 2026-06-13.
- dbt SQL tests: 5/5 passed. Historical ranking as-of join violations: 0.
- Fresh MLflow run: `0c4c999edaa84b9da557019a54fac51c`; training used 17,257 matches, validation 1,564, test 4,876. The run used 500 tuning and 1,000 posterior draws across two chains; training took 631.14 seconds.
- Exact 23,697-row feature input snapshot is stored as the MLflow artifact `reproducibility/fresh_feature_dataset.csv`. Its SHA-256 is `6ea1452c7c728ee4f537bdefdfde2efe2f2581f13bb267a26c3e2902d58e63a9`. The hash of the Pandas feature frame matched the dataset hash logged by the training run (`2a94889834ce7f39b1737e93e6ce8a595e981ae95b831f4193fc703f9194b78c`).
- Measured model runtime: Python 3.14.7, PyMC 6.3.2, ArviZ 1.3.0, MLflow 3.16.1, NumPy 2.5.2, pandas 3.0.5, scikit-learn 1.9.0, SciPy 1.18.0, psycopg2-binary 2.9.13. Model-only dependency pins are in `requirements-model.txt`.

| Split | Rows | Log loss | Multiclass Brier |
|---|---:|---:|---:|
| Validation | 1,564 | 0.8884 | 0.5227 |
| Test | 4,876 | 0.9014 | 0.5290 |

Test one-vs-rest ECE: home win 0.0297, draw 0.0311, away win 0.0216; macro ECE 0.0275. These are fresh posterior-predictive measurements from `evaluation.json` in the MLflow run.

### Model limitations

PyMC emitted a potential-energy overflow warning and warned that effective sample size was below 100 for some parameters. Only two chains ran. The separate elite probability heuristic reported 62 violations; it is not a reliability metric, but it signals that the existing elite calibration expectation is not met. Treat these metrics as an initial reproducible evaluation, not freeze-level model validation.

## Live dependency fault findings

| Injection | Observed result |
|---|---|
| Kafka stopped | Readiness stayed HTTP 200 while reporting `kafka:false`; simulation submission returned HTTP 503. Kafka returned healthy in 12 seconds after restart. |
| Worker stopped with a queued task | Restarted worker consumed and completed the queued task. |
| Duplicate completed task published again | Task remained `COMPLETED`; no second result or retry counter was observed. |
| Redis stopped | Readiness probe did not respond within 8 seconds; a valid simulation submission did not respond within 5 seconds. Redis was restarted and health returned. This is a failure finding, not a successful graceful-degradation result. |
| PostgreSQL stopped | `/health/ready` returned HTTP 503 with `postgres:false`; PostgreSQL returned healthy within the 8-second recovery check. |
| Brief PostgreSQL pause during worker task | Redis showed `RETRYING`, attempt 1. After PostgreSQL resumed, the task reached `COMPLETED` within a 14.5-second observation window; no duplicate execution was observed. |
| Longer PostgreSQL outage during worker task | Worker reached attempt 3, committed the offset, and left task status `ERROR`. One queued task did not execute. |

Recovery time figures are upper bounds from command observation windows, not fine-grained service telemetry. No distributed exactly-once claim is made: duplicate suppression relies on Redis task state and task IDs.

## Freeze decision

**Not ready to freeze.** The fresh database/model/report path succeeded, but Redis failure made API probes time out, and a PostgreSQL outage longer than the retry budget left one task unexecuted. The Bayesian run also has convergence and elite-calibration warnings. Address these findings and rerun the affected live tests before freezing.

## Reproduction

```powershell
docker compose up -d db redis minio zookeeper kafka airflow-db airflow-webserver airflow-scheduler
docker compose exec -T airflow-webserver airflow dags trigger elt_underdog_pipeline
docker run --rm --network underdogai_default -e DBT_HOST=db -e DBT_PORT=5432 -v "${PWD}/dbt:/app/dbt" underdog-dbt:test dbt run --full-refresh
docker run --rm --network underdogai_default -e DBT_HOST=db -e DBT_PORT=5432 -v "${PWD}/dbt:/app/dbt" underdog-dbt:test dbt test
python -m pip install -r requirements-model.txt
$env:POSTGRES_HOST='localhost'; $env:POSTGRES_PORT='5433'; $env:POSTGRES_DB='analytical_sandbox'; $env:POSTGRES_USER='postgres'; $env:POSTGRES_PASSWORD='postgres'; $env:MLFLOW_TRACKING_URI='sqlite:///mlflow.db'; $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; python src/models/bayesian_match_engine.py
python benchmarks/flagship_report.py
```
