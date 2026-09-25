"""Build a reproducibility report from local inputs and stored MLflow runs."""

import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import sys

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
    runs = []
    for summary_path in ROOT.glob("mlruns/**/artifacts/model_summary.csv"):
        params = {}
        with summary_path.open(encoding="utf-8", newline="") as file:
            reader = csv.reader(file)
            header = next(reader)
            name_column = 0 if not header[0] else header.index("")
            for row in reader:
                params[row[name_column]] = row[header.index("mean")]
        runs.append({"summary": str(summary_path.relative_to(ROOT)), "sha256": digest(summary_path), "parameter_count": len(params)})
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True).stdout.strip()
    report = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit or None,
        "datasets": datasets,
        "config_sha256": {str(path.relative_to(ROOT)): digest(path) for path in CONFIGS if path.exists()},
        "stored_model_summaries": runs,
        "evaluation_metrics": None,
        "limitation": "No prediction-level outcomes are stored with the available MLflow artifacts; Brier, log loss, and calibration cannot be independently reconstructed from parameter summaries alone.",
    }
    (ROOT / "benchmarks" / "reproducibility_manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    OUT.write_text(
        "# Flagship reproducibility and evaluation report\n\n"
        f"Generated: {report['measured_at']}\n\n"
        f"Git commit: `{commit or 'unavailable'}`\n\n"
        "## Data lineage\n\n"
        "Raw CSV landing files → Airflow ingestion → PostgreSQL raw tables → dbt staging/intermediate models → `fct_underdog_feature_mart` → Bayesian model/MLflow → API and simulation worker inference.\n\n"
        "The manifest records source and config SHA-256 hashes and schema fingerprints. MLflow training records dataset hash, Git commit, features, and temporal bounds. Historical inference records are not persisted as a prediction dataset; year-scoped inference helpers apply pre-year cutoffs, so reproducible historical calls must pass the prediction year.\n\n"
        "## Contract validation\n\n"
        + "\n".join(f"- `{name}`: {item['rows']:,} rows; SHA-256 `{item['sha256']}`; schema `{item['schema_sha256']}`" for name, item in datasets.items())
        + "\n\n## Model evaluation\n\n"
        "No prediction-level stored outcomes were available for metric re-calculation. Brier score, log loss, and reliability values are therefore omitted here; historical MLflow parameter summaries do not contain enough information to reproduce them. Run the training job against a provisioned feature mart to regenerate current metrics.\n\n"
        "## Temporal protocol\n\n"
        "Training: before 2018-01-01; validation: 2018-01-01 through 2019-12-31; test: 2020-01-01 onward. Ranking features retain the existing as-of-match-date dbt join. Team-rank priors are computed from training rows only.\n\n"
        "## Limitations\n\n"
        "No fresh database, dbt, model training, or real broker/cache fault runs were possible without local services. Historical operational benchmark values remain labeled as historical in README; controlled failure tests run independently of cloud infrastructure. Causal estimates remain observational and depend on the stated adjustment and refutation assumptions.\n",
        encoding="utf-8",
    )
    print(json.dumps({"datasets": {name: item["rows"] for name, item in datasets.items()}, "model_summaries": len(runs), "report": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
