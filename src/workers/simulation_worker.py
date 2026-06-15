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

def get_standard_team_name(name):
    mapping = {
        "USA": "United States",
        "IR Iran": "Iran",
        "Korea Republic": "South Korea",
        "Türkiye": "Turkey",
        "Czechia": "Czech Republic",
        "Côte d'Ivoire": "Ivory Coast",
        "Congo DR": "DR Congo",
        "Cabo Verde": "Cape Verde",
        "Brunei Darussalam": "Brunei",
        "The Gambia": "Gambia",
        "Hong Kong, China": "Hong Kong",
        "China PR": "China",
    }
    return mapping.get(name, name)

def get_fifa_rankings_name(name):
    mapping = {
        "United States": "USA",
        "Iran": "IR Iran",
        "South Korea": "Korea Republic",
        "Turkey": "Türkiye",
        "Czech Republic": "Czechia",
        "Ivory Coast": "Côte d'Ivoire",
        "DR Congo": "Congo DR",
        "Cape Verde": "Cabo Verde",
        "Brunei": "Brunei Darussalam",
        "Gambia": "The Gambia",
        "Hong Kong": "Hong Kong, China",
        "China": "China PR",
    }
    return mapping.get(name, name)

def fetch_tournament_teams(conn, year):
    query = """
        WITH team_matches AS (
            SELECT match_date, home_team AS team, home_rolling_point_velocity_5 AS velocity, home_rank_volatility_12m AS volatility
            FROM fct_underdog_feature_mart
            WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = %s
            UNION ALL
            SELECT match_date, away_team AS team, away_rolling_point_velocity_5 AS velocity, away_rank_volatility_12m AS volatility
            FROM fct_underdog_feature_mart
            WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = %s
        ),
        ranked_teams AS (
            SELECT team, velocity, volatility,
                   ROW_NUMBER() OVER (PARTITION BY team ORDER BY match_date DESC) as rn
            FROM team_matches
        )
        SELECT r.team, r.velocity, r.volatility
        FROM ranked_teams r
        WHERE r.rn = 1
    """
    raw_teams = []
    with conn.cursor() as cur:
        cur.execute(query, (year, year))
        raw_teams = cur.fetchall()
    teams = []
    team_features = {}
    for row in raw_teams:
        team_name = row[0]
        vel = float(row[1]) if row[1] is not None else 1.0
        vol = float(row[2]) if row[2] is not None else 0.0
        std_name = get_standard_team_name(team_name)
        fifa_name = get_fifa_rankings_name(std_name)
        rank = None
        conf = None
        rank_query = """
            SELECT rank, confederation FROM raw_fifa_rankings
            WHERE TRIM(country_full) = TRIM(%s)
              AND rank_date <= MAKE_DATE(%s, 1, 1)
            ORDER BY rank_date DESC
            LIMIT 1
        """
        with conn.cursor() as cur:
            cur.execute(rank_query, (fifa_name, int(year)))
            row_rank = cur.fetchone()
            if row_rank:
                rank = float(row_rank[0]) if row_rank[0] is not None else None
                conf = row_rank[1]
        if rank is None:
            fallback_query = """
                SELECT rank, confederation FROM raw_fifa_rankings
                WHERE TRIM(country_full) = TRIM(%s)
                ORDER BY ABS(EXTRACT(EPOCH FROM (rank_date - MAKE_DATE(%s, 1, 1)))) ASC
                LIMIT 1
            """
            with conn.cursor() as cur:
                cur.execute(fallback_query, (fifa_name, int(year)))
                row_fallback = cur.fetchone()
                if row_fallback:
                    rank = float(row_fallback[0]) if row_fallback[0] is not None else 100.0
                    conf = row_fallback[1] if conf is None else conf
                else:
                    rank = 100.0
        teams.append(std_name)
        team_features[std_name] = {
            "rank": rank,
            "vel": vel,
            "vol": vol,
            "conf": conf
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

def simulate_match(team_a, team_b, team_strengths, team_features, intercept, home_adv, beta_diff, beta_vel, beta_vol, beta_rank_prior, hosts):
    a_std = get_standard_team_name(team_a)
    a_fifa = get_fifa_rankings_name(a_std)
    a_feat = team_features.get(a_std, {"rank": 100.0, "vel": 1.0, "vol": 0.0})
    b_std = get_standard_team_name(team_b)
    b_fifa = get_fifa_rankings_name(b_std)
    b_feat = team_features.get(b_std, {"rank": 100.0, "vel": 1.0, "vol": 0.0})
    a_est = team_strengths.get(a_std, team_strengths.get(a_fifa, beta_rank_prior * a_feat["rank"]))
    a_str = a_est * 0.1 + (-0.008 * a_feat["rank"])
    b_est = team_strengths.get(b_std, team_strengths.get(b_fifa, beta_rank_prior * b_feat["rank"]))
    b_str = b_est * 0.1 + (-0.008 * b_feat["rank"])
    conf_weights = {
        "UEFA": 1.5,
        "CONMEBOL": 1.4,
        "CAF": 0.9,
        "CONCACAF": 0.8,
        "AFC": 0.7,
        "OFC": 0.4
    }
    a_conf = a_feat.get("conf")
    a_weight = conf_weights.get(a_conf, 1.0) if a_conf else 1.0
    a_str = a_str + math.log(a_weight)
    b_conf = b_feat.get("conf")
    b_weight = conf_weights.get(b_conf, 1.0) if b_conf else 1.0
    b_str = b_str + math.log(b_weight)
    tuned_home_adv = home_adv * 0.1
    tuned_beta_diff = -0.002
    a_adv_val = tuned_home_adv if a_fifa in hosts else 0.0
    b_adv_val = tuned_home_adv if b_fifa in hosts else 0.0
    rank_diff = a_feat["rank"] - b_feat["rank"]
    lambda_a = math.exp(
        intercept + a_adv_val + a_str - b_str
        + tuned_beta_diff * rank_diff
        + beta_vel * a_feat["vel"]
        + beta_vol * a_feat["vol"]
    )
    lambda_b = math.exp(
        intercept + b_adv_val + b_str - a_str
        - tuned_beta_diff * rank_diff
        + beta_vel * b_feat["vel"]
        + beta_vol * b_feat["vol"]
    )
    goals_a = sample_poisson(lambda_a)
    goals_b = sample_poisson(lambda_b)
    if goals_a > goals_b:
        return a_std
    elif goals_b > goals_a:
        return b_std
    else:
        p_a_win = lambda_a / (lambda_a + lambda_b) if (lambda_a + lambda_b) > 0 else 0.5
        return a_std if random.random() < p_a_win else b_std

def run_tournament_simulation(teams, team_features, team_strengths, intercept, home_adv, beta_diff, beta_vel, beta_vol, beta_rank_prior, runs, year, r_conn, task_id):
    win_counts = {t: 0 for t in teams}
    if not teams:
        return {}
    host_map = {
        1970: {"Mexico"},
        2018: {"Russia"},
        2022: {"Qatar"},
        2026: {"USA", "Canada", "Mexico"}
    }
    hosts = host_map.get(year, set()) if year is not None else set()
    step = max(1, runs // 20)
    for i in range(runs):
        active_teams = list(teams)
        random.shuffle(active_teams)
        while len(active_teams) > 1:
            next_round = []
            for j in range(0, len(active_teams), 2):
                if j + 1 < len(active_teams):
                    winner = simulate_match(
                        active_teams[j], active_teams[j+1],
                        team_strengths, team_features,
                        intercept, home_adv, beta_diff, beta_vel, beta_vol, beta_rank_prior, hosts
                    )
                    next_round.append(winner)
                else:
                    next_round.append(active_teams[j])
            active_teams = next_round
        if active_teams:
            win_counts[active_teams[0]] += 1
        if (i + 1) % step == 0 or (i + 1) == runs:
            progress_pct = ((i + 1) / runs) * 100.0
            r_conn.set(f"task:{task_id}:progress", str(progress_pct))
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
            
            intercept, home_adv, beta_diff, beta_vel, beta_vol, beta_rank_prior, team_strengths = get_latest_model_params()
            
            results = run_tournament_simulation(
                teams, team_features, team_strengths,
                intercept, home_adv, beta_diff, beta_vel, beta_vol, beta_rank_prior, runs, year, r, task_id
            )
            
            r.set(task_id, json.dumps(results), ex=3600)
        except Exception as e:
            sys.stderr.write(str(e) + "\n")

if __name__ == "__main__":
    main()
