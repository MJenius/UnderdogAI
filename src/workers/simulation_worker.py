import os
import sys
import json
import glob
import math
import csv
import random
import psycopg2
import redis
from confluent_kafka import Consumer, KafkaError

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "proto")))

def get_latest_model_params():
    files = glob.glob(os.path.join("mlruns", "**", "model_summary.csv"), recursive=True)
    if not files:
        return 0.0, 0.0, 0.0, 0.0, 0.0, -0.01, {}
    latest_file = max(files, key=os.path.getmtime)
    intercept = 0.0
    home_adv = 0.0
    beta_diff = 0.0
    beta_vel = 0.0
    beta_vol = 0.0
    beta_rank_prior = -0.01
    team_strengths = {}
    with open(latest_file, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if not row:
                continue
            name = row[0]
            val = float(row[1])
            if name == "intercept":
                intercept = val
            elif name == "home_adv":
                home_adv = val
            elif name == "beta_diff":
                beta_diff = val
            elif name == "beta_vel":
                beta_vel = val
            elif name == "beta_vol":
                beta_vol = val
            elif name == "beta_rank_prior":
                beta_rank_prior = val
            elif name.startswith("team_strength[") and name.endswith("]"):
                team_name = name[len("team_strength["):-1]
                team_strengths[team_name] = val
    return intercept, home_adv, beta_diff, beta_vel, beta_vol, beta_rank_prior, team_strengths

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5433)),
        database=os.getenv("POSTGRES_DB", "analytical_sandbox"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres")
    )

def fetch_tournament_teams(conn, year):
    query = """
        WITH team_matches AS (
            SELECT match_date, home_team AS team, home_rank AS rank, home_rolling_point_velocity_5 AS velocity, home_rank_volatility_12m AS volatility
            FROM fct_underdog_feature_mart
            WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = %s
            UNION ALL
            SELECT match_date, away_team AS team, away_rank AS rank, away_rolling_point_velocity_5 AS velocity, away_rank_volatility_12m AS volatility
            FROM fct_underdog_feature_mart
            WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = %s
        ),
        ranked_teams AS (
            SELECT team, rank, velocity, volatility,
                   ROW_NUMBER() OVER (PARTITION BY team ORDER BY match_date DESC) as rn
            FROM team_matches
        )
        SELECT team, rank, velocity, volatility
        FROM ranked_teams
        WHERE rn = 1
    """
    teams = []
    team_features = {}
    with conn.cursor() as cur:
        cur.execute(query, (year, year))
        for row in cur.fetchall():
            team_name = row[0]
            teams.append(team_name)
            team_features[team_name] = {
                "rank": float(row[1]) if row[1] is not None else 100.0,
                "vel": float(row[2]) if row[2] is not None else 1.0,
                "vol": float(row[3]) if row[3] is not None else 0.0
            }
    return teams, team_features

def sample_poisson(lam):
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1

def simulate_match(team_a, team_b, team_strengths, team_features, intercept, beta_diff, beta_vel, beta_vol, beta_rank_prior):
    a_str = team_strengths.get(team_a, beta_rank_prior * team_features.get(team_a, {}).get("rank", 100.0))
    b_str = team_strengths.get(team_b, beta_rank_prior * team_features.get(team_b, {}).get("rank", 100.0))
    
    a_feat = team_features.get(team_a, {"rank": 100.0, "vel": 1.0, "vol": 0.0})
    b_feat = team_features.get(team_b, {"rank": 100.0, "vel": 1.0, "vol": 0.0})
    
    rank_diff = a_feat["rank"] - b_feat["rank"]
    
    lambda_a = math.exp(
        intercept + a_str - b_str
        + beta_diff * rank_diff
        + beta_vel * a_feat["vel"]
        + beta_vol * a_feat["vol"]
    )
    lambda_b = math.exp(
        intercept + b_str - a_str
        - beta_diff * rank_diff
        + beta_vel * b_feat["vel"]
        + beta_vol * b_feat["vol"]
    )
    
    goals_a = sample_poisson(lambda_a)
    goals_b = sample_poisson(lambda_b)
    
    if goals_a > goals_b:
        return team_a
    elif goals_b > goals_a:
        return team_b
    else:
        p_a_win = lambda_a / (lambda_a + lambda_b) if (lambda_a + lambda_b) > 0 else 0.5
        return team_a if random.random() < p_a_win else team_b

def run_tournament_simulation(teams, team_features, team_strengths, intercept, beta_diff, beta_vel, beta_vol, beta_rank_prior, runs):
    win_counts = {t: 0 for t in teams}
    if not teams:
        return {}
        
    for _ in range(runs):
        active_teams = list(teams)
        random.shuffle(active_teams)
        while len(active_teams) > 1:
            next_round = []
            for i in range(0, len(active_teams), 2):
                if i + 1 < len(active_teams):
                    winner = simulate_match(
                        active_teams[i], active_teams[i+1],
                        team_strengths, team_features,
                        intercept, beta_diff, beta_vel, beta_vol, beta_rank_prior
                    )
                    next_round.append(winner)
                else:
                    next_round.append(active_teams[i])
            active_teams = next_round
        if active_teams:
            win_counts[active_teams[0]] += 1
            
    return {t: count / runs for t, count in win_counts.items()}

def main():
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    
    conf = {
        "bootstrap.servers": kafka_servers,
        "group.id": "underdog_simulation_workers",
        "auto.offset.reset": "earliest"
    }
    
    consumer = Consumer(conf)
    consumer.subscribe(["underdog_simulation_tasks"])
    
    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                continue
                
        try:
            event = json.loads(msg.value().decode("utf-8"))
            task_id = event["task_id"]
            year = event["tournament_year"]
            runs = event["simulation_runs"]
            
            conn = get_db_connection()
            teams, team_features = fetch_tournament_teams(conn, year)
            conn.close()
            
            intercept, _, beta_diff, beta_vel, beta_vol, beta_rank_prior, team_strengths = get_latest_model_params()
            
            results = run_tournament_simulation(
                teams, team_features, team_strengths,
                intercept, beta_diff, beta_vel, beta_vol, beta_rank_prior, runs
            )
            
            r.set(task_id, json.dumps(results), ex=3600)
        except Exception as e:
            sys.stderr.write(str(e) + "\n")

if __name__ == "__main__":
    main()
