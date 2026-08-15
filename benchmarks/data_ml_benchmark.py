"""Reproducible local data/ML benchmark; writes only measurements it executes."""
import csv
import hashlib
import json
import os
import subprocess
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks" / "data_ml_results.json"
DB = dict(host="localhost", port=5433, dbname="analytical_sandbox", user="postgres", password="postgres")


def timed(fn):
    tracemalloc.start()
    started = time.perf_counter()
    value = fn()
    seconds = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return value, seconds, peak / 1_048_576


def rows(name, columns):
    integers = {"home_score", "away_score", "rank", "rank_change"}
    with (ROOT / "data" / "landing" / name).open(encoding="utf-8-sig", newline="") as handle:
        result = []
        for row in csv.DictReader(handle):
            values = [None if not row[c] or row[c].upper() in {"NA", "NULL"} else row[c] for c in columns]
            result.append(tuple(int(float(v)) if v is not None and c in integers else v for c, v in zip(columns, values)))
        return result


def load_table(conn, table, columns, values, full):
    with conn.cursor() as cur:
        if full:
            cur.execute(f"TRUNCATE {table}")
        execute_values(cur, f"INSERT INTO {table} ({','.join(columns)}) VALUES %s ON CONFLICT DO NOTHING", values, page_size=5000)
    conn.commit()
    return len(values)


def dbt(*args):
    env = os.environ | {"DBT_HOST": "localhost", "DBT_PORT": "5433"}
    started = time.perf_counter()
    run = subprocess.run(
        [str(ROOT / "venv" / "Scripts" / "dbt.exe"), *args], cwd=ROOT / "dbt", env=env,
        text=True, capture_output=True, check=False,
    )
    return {"seconds": time.perf_counter() - started, "passed": run.returncode == 0, "output": (run.stdout + run.stderr)[-3000:]}


def main():
    conn = psycopg2.connect(**DB)
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS raw_match_results (
          date date, home_team text, away_team text, home_score integer, away_score integer,
          tournament text, city text, country text, neutral boolean,
          UNIQUE(date, home_team, away_team, tournament));
        CREATE TABLE IF NOT EXISTS raw_shootouts (
          date date, home_team text, away_team text, winner text, first_shooter text,
          UNIQUE(date, home_team, away_team));
        CREATE TABLE IF NOT EXISTS raw_fifa_rankings (
          id integer, rank integer, country_full text, country_abrv text, total_points numeric,
          previous_points numeric, rank_change integer, confederation text, rank_date date,
          UNIQUE(country_full, rank_date));
        """)
        conn.commit()

    specs = [
        ("raw_match_results", "results.csv", ["date", "home_team", "away_team", "home_score", "away_score", "tournament", "city", "country", "neutral"]),
        ("raw_shootouts", "shootouts.csv", ["date", "home_team", "away_team", "winner", "first_shooter"]),
        ("raw_fifa_rankings", "fifa_ranking-2026-01-19.csv", ["rank", "country_full", "country_abrv", "total_points", "previous_points", "rank_change", "confederation", "rank_date"]),
    ]
    prepared = [(table, cols, rows(file, cols)) for table, file, cols in specs]

    def load(full, fraction=1.0):
        return sum(load_table(conn, table, cols, vals[:max(1, int(len(vals) * fraction))], full) for table, cols, vals in prepared)

    records = sum(len(x[2]) for x in prepared)
    _, full_s, full_mem = timed(lambda: load(True))
    incremental_input = sum(max(1, int(len(x[2]) * .01)) for x in prepared)
    _, inc_s, inc_mem = timed(lambda: load(False, .01))
    full_dbt = dbt("run", "--full-refresh")
    incremental_dbt = dbt("run")
    tests = dbt("test")

    with conn.cursor() as cur:
        cur.execute("SELECT count(*), count(*) FILTER (WHERE home_rank IS NOT NULL AND away_rank IS NOT NULL) FROM fct_underdog_feature_mart")
        mart_rows, ranked_rows = cur.fetchone()
        cur.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='fct_underdog_feature_mart'")
        feature_count = cur.fetchone()[0]
        query = "SELECT home_team, avg(home_underdog_signal_score) FROM fct_underdog_feature_mart WHERE match_date >= DATE '2018-01-01' GROUP BY home_team ORDER BY 2 DESC LIMIT 20"
        samples = []
        for _ in range(20):
            start = time.perf_counter(); cur.execute(query); cur.fetchall(); samples.append(time.perf_counter() - start)
        cur.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query)
        plan = cur.fetchone()[0][0]
        quality_sql = {
            "null_required": "SELECT count(*) FROM fct_underdog_feature_mart WHERE match_id IS NULL OR match_date IS NULL OR home_team IS NULL OR away_team IS NULL",
            "duplicate_match_ids": "SELECT count(*) FROM (SELECT match_id FROM fct_underdog_feature_mart GROUP BY 1 HAVING count(*) > 1) x",
            "missing_rank_features": "SELECT count(*) FROM fct_underdog_feature_mart WHERE home_rank IS NULL OR away_rank IS NULL",
            "invalid_values_or_timestamps": "SELECT count(*) FROM fct_underdog_feature_mart WHERE match_date > current_date OR home_score < 0 OR away_score < 0 OR home_team = away_team",
            "temporal_leakage": "SELECT count(*) FROM int_match_historical_rankings WHERE home_rank_date > match_date OR away_rank_date > match_date",
            "stale_source": "SELECT count(*) FROM (SELECT max(date) latest FROM raw_match_results) x WHERE latest < current_date - interval '18 months'",
        }
        quality = {}
        for name, sql in quality_sql.items():
            cur.execute(sql); quality[name] = cur.fetchone()[0]
    conn.close()

    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "data" / "landing").glob("*.csv")}
    result = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True).stdout.strip(),
        "dataset_sha256": hashes,
        "ingestion": {
            "full": {"records": records, "seconds": full_s, "records_per_second": records / full_s, "peak_python_mb": full_mem},
            "incremental_noop": {"records_examined": incremental_input, "records_inserted": 0, "seconds": inc_s, "records_per_second": incremental_input / inc_s, "peak_python_mb": inc_mem},
        },
        "dbt": {"full": full_dbt, "incremental": incremental_dbt, "tests": tests},
        "feature_mart": {"records": mart_rows, "ranked_records": ranked_rows, "column_count": feature_count},
        "postgres_query": {"runs": 20, "median_ms": sorted(samples)[len(samples)//2] * 1000, "execution_ms": plan["Execution Time"], "shared_hit_blocks": plan["Plan"].get("Shared Hit Blocks", 0)},
        "data_quality": quality,
    }
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
