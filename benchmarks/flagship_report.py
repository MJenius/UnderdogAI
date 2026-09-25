"""Build the reproducibility report from source files and the latest MLflow evaluation."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data_contracts import schema_fingerprint, validate_csv

OUT = ROOT / "benchmarks" / "flagship_report.md"
DATA = ROOT / "data" / "landing"
CONFIGS = [ROOT / "docker-compose.yml", ROOT / "dbt" / "dbt_project.yml", ROOT / "src" / "models" / "bayesian_match_engine.py"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    datasets = {}
    for path in sorted(DATA.glob("*.csv")):
        rows = validate_csv(path.name, path.read_text(encoding="utf-8-sig"))
        datasets[path.name] = {"sha256": digest(path), "rows": len(rows), "schema_sha256": schema_fingerprint(path.name)}
    evaluations = sorted(ROOT.glob("mlruns/*/*/artifacts/evaluation.json"), key=lambda path: path.stat().st_mtime)
    latest = evaluations[-1] if evaluations else None
    evaluation = json.loads(latest.read_text(encoding="utf-8")) if latest else None
    run_id = latest.parent.parent.name if latest else None
    run_dir = latest.parent.parent if latest else None
    metrics, params = {}, {}
    if run_dir:
        for path in (run_dir / "metrics").glob("*"):
            metrics[path.name] = float(path.read_text(encoding="utf-8").split()[0])
        for path in (run_dir / "params").glob("*"):
            params[path.name] = path.read_text(encoding="utf-8")
    ece = {}
    if evaluation:
        for item in evaluation["test"]["reliability_bins"]:
            count = sum(row["count"] for row in item["bins"])
            ece[item["outcome"]] = sum(row["count"] * abs(row["mean_probability"] - row["observed_frequency"]) for row in item["bins"]) / count
    snapshot = run_dir / "artifacts" / "reproducibility" / "fresh_feature_dataset.csv" if run_dir else None
    runtime_manifest = ROOT / "runtime" / "fresh_model_manifest.json"
    prior = json.loads(runtime_manifest.read_text(encoding="utf-8")) if runtime_manifest.exists() else {}
    metrics = prior.get("metrics", metrics)
    params = prior.get("params", params)
    fault_path = ROOT / "runtime" / "live_fault_matrix.json"
    live_faults = json.loads(fault_path.read_text(encoding="utf-8")) if fault_path.exists() else None
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True).stdout.strip()
    report = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": prior.get("git_commit", commit or None),
        "datasets": datasets,
        "config_sha256": {str(path.relative_to(ROOT)): digest(path) for path in CONFIGS if path.exists()},
        "mlflow_run_id": run_id,
        "dataset_sha256": prior.get("dataset_sha256"),
        "feature_snapshot": {"path": str(snapshot.relative_to(ROOT)), "sha256": digest(snapshot)} if snapshot and snapshot.exists() else None,
        "params": params,
        "metrics": metrics,
        "model_environment": prior.get("model_environment"),
        "live_fault_findings": live_faults,
        "evaluation": evaluation,
        "test_reliability_ece_one_vs_rest": ece,
        "test_macro_ece": sum(ece.values()) / len(ece) if ece else None,
        "limitations": ["Two chains; low effective sample size for some parameters.", "Potential-energy overflow warning during sampling.", "Elite calibration audit reported violations; it is not a reliability metric."],
    }
    (ROOT / "docs" / "reproducibility_manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    metrics_text = "No fresh evaluation artifact found."
    if evaluation:
        metrics_text = (
            f"MLflow run `{run_id}`. Validation log loss {metrics.get('validation_log_loss', float('nan')):.4f}, "
            f"Brier {metrics.get('validation_multiclass_brier_score', float('nan')):.4f}; test log loss "
            f"{metrics.get('posterior_log_loss', float('nan')):.4f}, Brier {metrics.get('multiclass_brier_score', float('nan')):.4f}; "
            f"macro one-vs-rest ECE {report['test_macro_ece']:.4f} over {params.get('num_test_samples', 'unknown')} test rows."
        )
    OUT.write_text(
        "# Flagship reproducibility and evaluation report\n\n"
        f"Generated: {report['measured_at']}\n\nGit commit: `{report['git_commit'] or 'unavailable'}`\n\n"
        "## Data lineage\n\nRaw CSV landing files → Airflow ingestion → PostgreSQL raw tables → dbt staging/intermediate models → `fct_underdog_feature_mart` → Bayesian model/MLflow → API and simulation worker inference.\n\n"
        "The manifest records source and config hashes, schema fingerprints, MLflow run identity, evaluation metrics, and the feature snapshot hash when available. Historical inference helpers apply pre-year cutoffs when called with the prediction year.\n\n"
        "## Contract validation\n\n" + "\n".join(f"- `{name}`: {item['rows']:,} rows; source SHA-256 `{item['sha256']}`; schema SHA-256 `{item['schema_sha256']}`" for name, item in datasets.items())
        + "\n\n## Fresh ML evaluation\n\n" + metrics_text
        + "\n\n## Temporal protocol\n\nTraining before 2018-01-01; validation 2018-01-01 through 2019-12-31; test 2020-01-01 onward. Ranking features retain the existing as-of-match-date dbt join. Team-rank priors use training rows only.\n\n"
        "## Limitations\n\nThe latest model run used two chains and reported low effective sample size for some parameters plus a potential-energy overflow warning. Live fault findings and causal-analysis scope are in `docs/FINAL_VALIDATION_REPORT.md`.\n",
        encoding="utf-8",
    )
    print(json.dumps({"datasets": {name: item["rows"] for name, item in datasets.items()}, "mlflow_run_id": run_id, "report": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
