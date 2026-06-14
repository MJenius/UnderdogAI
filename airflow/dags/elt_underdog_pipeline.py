import os
import csv
import io
from datetime import datetime
import boto3
from botocore.client import Config
import psycopg2
from psycopg2.extras import execute_values
from airflow import DAG
from airflow.operators.python import PythonOperator

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "db"),
        database=os.getenv("POSTGRES_DB", "analytical_sandbox"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", 5432))
    )

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url="http://minio:9000",
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin",
        config=Config(signature_version="s3v4"),
        region_name="us-east-1"
    )

def parse_int(val):
    if not val or val.strip().upper() in ("NA", "NULL", ""):
        return None
    try:
        return int(val)
    except ValueError:
        try:
            return int(float(val))
        except ValueError:
            return None

def parse_float(val):
    if not val or val.strip().upper() in ("NA", "NULL", ""):
        return None
    try:
        return float(val)
    except ValueError:
        return None

def parse_date(val):
    if not val or val.strip().upper() in ("NA", "NULL", ""):
        return None
    try:
        return datetime.strptime(val.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None

def parse_bool(val):
    if not val or val.strip().upper() in ("NA", "NULL", ""):
        return None
    return val.strip().upper() == "TRUE"

def bootstrap_s3(s3, bucket, key, local_path):
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        try:
            s3.create_bucket(Bucket=bucket)
        except Exception as e:
            if "BucketAlreadyOwnedByYou" not in str(e) and "BucketAlreadyExists" not in str(e):
                raise
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except Exception:
        s3.upload_file(local_path, bucket, key)

def ingest_results():
    s3 = get_s3_client()
    bootstrap_s3(s3, "landing", "results.csv", "/data/landing/results.csv")
    obj = s3.get_object(Bucket="landing", Key="results.csv")
    csv_data = io.StringIO(obj["Body"].read().decode("utf-8"))
    reader = csv.DictReader(csv_data)
    records = []
    for row in reader:
        records.append((
            parse_date(row["date"]),
            row["home_team"],
            row["away_team"],
            parse_int(row["home_score"]),
            parse_int(row["away_score"]),
            row["tournament"],
            row["city"],
            row["country"],
            parse_bool(row["neutral"])
        ))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS raw_match_results (
                    date DATE,
                    home_team VARCHAR(100),
                    away_team VARCHAR(100),
                    home_score INTEGER,
                    away_score INTEGER,
                    tournament VARCHAR(150),
                    city VARCHAR(100),
                    country VARCHAR(100),
                    neutral BOOLEAN
                );
            """)
            cur.execute("TRUNCATE TABLE raw_match_results;")
            execute_values(
                cur,
                "INSERT INTO raw_match_results (date, home_team, away_team, home_score, away_score, tournament, city, country, neutral) VALUES %s",
                records
            )
            conn.commit()
    finally:
        conn.close()

def ingest_shootouts():
    s3 = get_s3_client()
    bootstrap_s3(s3, "landing", "shootouts.csv", "/data/landing/shootouts.csv")
    obj = s3.get_object(Bucket="landing", Key="shootouts.csv")
    csv_data = io.StringIO(obj["Body"].read().decode("utf-8"))
    reader = csv.DictReader(csv_data)
    records = []
    for row in reader:
        records.append((
            parse_date(row["date"]),
            row["home_team"],
            row["away_team"],
            row["winner"],
            row["first_shooter"] if row["first_shooter"] else None
        ))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS raw_shootouts (
                    date DATE,
                    home_team VARCHAR(100),
                    away_team VARCHAR(100),
                    winner VARCHAR(100),
                    first_shooter VARCHAR(100)
                );
            """)
            cur.execute("TRUNCATE TABLE raw_shootouts;")
            execute_values(
                cur,
                "INSERT INTO raw_shootouts (date, home_team, away_team, winner, first_shooter) VALUES %s",
                records
            )
            conn.commit()
    finally:
        conn.close()

def ingest_fifa_rankings():
    s3 = get_s3_client()
    bootstrap_s3(s3, "landing", "fifa_ranking-2026-01-19.csv", "/data/landing/fifa_ranking-2026-01-19.csv")
    obj = s3.get_object(Bucket="landing", Key="fifa_ranking-2026-01-19.csv")
    csv_data = io.StringIO(obj["Body"].read().decode("utf-8"))
    reader = csv.DictReader(csv_data)
    records = []
    for row in reader:
        id_val = None
        if "Unnamed: 0" in row:
            id_val = parse_int(row["Unnamed: 0"])
        elif "" in row:
            id_val = parse_int(row[""])
        elif None in row:
            id_val = parse_int(row[None][0] if isinstance(row[None], list) else row[None])
        records.append((
            id_val,
            parse_int(row["rank"]),
            row["country_full"],
            row["country_abrv"],
            parse_float(row["total_points"]),
            parse_float(row["previous_points"]),
            parse_int(row["rank_change"]),
            row["confederation"],
            parse_date(row["rank_date"])
        ))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS raw_fifa_rankings (
                    id INTEGER,
                    rank INTEGER,
                    country_full VARCHAR(100),
                    country_abrv VARCHAR(10),
                    total_points NUMERIC,
                    previous_points NUMERIC,
                    rank_change INTEGER,
                    confederation VARCHAR(50),
                    rank_date DATE
                );
            """)
            cur.execute("TRUNCATE TABLE raw_fifa_rankings;")
            execute_values(
                cur,
                "INSERT INTO raw_fifa_rankings (id, rank, country_full, country_abrv, total_points, previous_points, rank_change, confederation, rank_date) VALUES %s",
                records
            )
            conn.commit()
    finally:
        conn.close()

default_args = {
    "owner": "airflow",
    "start_date": datetime(2026, 1, 1),
    "retries": 0
}

with DAG(
    dag_id="elt_underdog_pipeline",
    default_args=default_args,
    schedule=None,
    catchup=False
) as dag:

    t1 = PythonOperator(
        task_id="ingest_match_results",
        python_callable=ingest_results
    )

    t2 = PythonOperator(
        task_id="ingest_shootouts",
        python_callable=ingest_shootouts
    )

    t3 = PythonOperator(
        task_id="ingest_fifa_rankings",
        python_callable=ingest_fifa_rankings
    )

    t1
    t2
    t3
