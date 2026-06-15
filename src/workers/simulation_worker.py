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
        "United States": "United States",
        "IR Iran": "Iran",
        "Iran": "Iran",
        "Korea Republic": "South Korea",
        "South Korea": "South Korea",
        "Türkiye": "Turkey",
        "Turkey": "Turkey",
        "Czechia": "Czech Republic",
        "Czech Republic": "Czech Republic",
        "Côte d'Ivoire": "Ivory Coast",
        "Ivory Coast": "Ivory Coast",
        "Congo DR": "DR Congo",
        "DR Congo": "DR Congo",
        "Cabo Verde": "Cape Verde",
        "Cape Verde": "Cape Verde",
        "Brunei Darussalam": "Brunei",
        "Brunei": "Brunei",
        "The Gambia": "Gambia",
        "Gambia": "Gambia",
        "Hong Kong, China": "Hong Kong",
        "Hong Kong": "Hong Kong",
        "China PR": "China",
        "China": "China",
    }
    return mapping.get(name, name)

def get_fifa_rankings_name(name):
    mapping = {
        "United States": "USA",
        "USA": "USA",
        "Iran": "IR Iran",
        "IR Iran": "IR Iran",
        "South Korea": "Korea Republic",
        "Korea Republic": "Korea Republic",
        "Turkey": "Türkiye",
        "Türkiye": "Türkiye",
        "Czech Republic": "Czechia",
        "Czechia": "Czechia",
        "Ivory Coast": "Côte d'Ivoire",
        "Côte d'Ivoire": "Côte d'Ivoire",
        "DR Congo": "Congo DR",
        "Congo DR": "Congo DR",
        "Cape Verde": "Cabo Verde",
        "Cabo Verde": "Cabo Verde",
        "Brunei": "Brunei Darussalam",
        "Brunei Darussalam": "Brunei Darussalam",
        "Gambia": "The Gambia",
        "The Gambia": "The Gambia",
        "Hong Kong": "Hong Kong, China",
        "Hong Kong, China": "Hong Kong, China",
        "China": "China PR",
        "China PR": "China PR",
    }
    return mapping.get(name, name)

def get_tier_from_rank(rank):
    if rank <= 15:
        return "Elite"
    elif rank <= 45:
        return "Competitive"
    elif rank <= 80:
        return "Mid-Tier"
    else:
        return "Developing"

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

def precompute_h2h_biases(conn, teams, year):
    biases = {}
    if not teams:
        return biases
    std_teams = [get_standard_team_name(t) for t in teams]
    query = """
        SELECT 
            EXTRACT(YEAR FROM match_date) as match_year,
            home_team,
            away_team,
            home_score,
            away_score
        FROM fct_underdog_feature_mart
        WHERE home_team IN %s AND away_team IN %s
          AND match_date < MAKE_DATE(%s, 1, 1);
    """
    with conn.cursor() as cur:
        cur.execute(query, (tuple(std_teams), tuple(std_teams), int(year)))
        rows = cur.fetchall()
    pairings = {}
    for row in rows:
        match_year = int(row[0]) if row[0] is not None else int(year)
        h_team = get_standard_team_name(row[1])
        a_team = get_standard_team_name(row[2])
        h_score = int(row[3]) if row[3] is not None else 0
        a_score = int(row[4]) if row[4] is not None else 0
        key = (h_team, a_team) if h_team < a_team else (a_team, h_team)
        if key not in pairings:
            pairings[key] = []
        pairings[key].append((match_year, h_team, a_team, h_score, a_score))
    for key, matches in pairings.items():
        std_a, std_b = key
        sum_w_pts_a = 0.0
        sum_w_pts_b = 0.0
        for match_year, h_team, a_team, h_score, a_score in matches:
            years_ago = max(0, int(year) - match_year)
            weight = math.exp(-0.05 * years_ago)
            is_home_a = (h_team == std_a)
            if h_score > a_score:
                if is_home_a:
                    sum_w_pts_a += 1.0 * weight
                else:
                    sum_w_pts_b += 1.0 * weight
            elif a_score > h_score:
                if is_home_a:
                    sum_w_pts_b += 1.0 * weight
                else:
                    sum_w_pts_a += 1.0 * weight
            else:
                sum_w_pts_a += 0.5 * weight
                sum_w_pts_b += 0.5 * weight
        total = sum_w_pts_a + sum_w_pts_b
        if total > 0.0:
            h2h_diff = (sum_w_pts_a - sum_w_pts_b) / total
            bias = 0.15 * h2h_diff
            biases[(std_a, std_b)] = bias
            biases[(std_b, std_a)] = -bias
    return biases

def precompute_tier_similarity(conn, teams, year):
    tier_similarity = {}
    std_teams = [get_standard_team_name(t) for t in teams]
    for t in std_teams:
        tier_similarity[t] = {
            "Elite": {"vel": 1.0, "gm": 0.0},
            "Competitive": {"vel": 1.0, "gm": 0.0},
            "Mid-Tier": {"vel": 1.0, "gm": 0.0},
            "Developing": {"vel": 1.0, "gm": 0.0}
        }
    if not teams:
        return tier_similarity
    query = """
        SELECT 
            home_team,
            away_team,
            home_score,
            away_score,
            COALESCE(home_rank, 100) as home_rank,
            COALESCE(away_rank, 100) as away_rank,
            EXTRACT(YEAR FROM match_date) as match_year
        FROM fct_underdog_feature_mart
        WHERE (home_team IN %s OR away_team IN %s)
          AND match_date < MAKE_DATE(%s, 1, 1)
          AND match_date >= MAKE_DATE(%s - 4, 1, 1);
    """
    with conn.cursor() as cur:
        cur.execute(query, (tuple(std_teams), tuple(std_teams), int(year), int(year)))
        rows = cur.fetchall()
    raw_metrics = {}
    for row in rows:
        h_team = get_standard_team_name(row[0])
        a_team = get_standard_team_name(row[1])
        h_score = int(row[2]) if row[2] is not None else 0
        a_score = int(row[3]) if row[3] is not None else 0
        h_rank = int(row[4])
        a_rank = int(row[5])
        if h_team in tier_similarity:
            opp_tier = get_tier_from_rank(a_rank)
            pts = 3 if h_score > a_score else 1 if h_score == a_score else 0
            gm = h_score - a_score
            key = (h_team, opp_tier)
            if key not in raw_metrics:
                raw_metrics[key] = []
            raw_metrics[key].append((pts, gm))
        if a_team in tier_similarity:
            opp_tier = get_tier_from_rank(h_rank)
            pts = 3 if a_score > h_score else 1 if a_score == h_score else 0
            gm = a_score - h_score
            key = (a_team, opp_tier)
            if key not in raw_metrics:
                raw_metrics[key] = []
            raw_metrics[key].append((pts, gm))
    for key, match_list in raw_metrics.items():
        team, tier = key
        avg_pts = sum(m[0] for m in match_list) / len(match_list)
        avg_gm = sum(m[1] for m in match_list) / len(match_list)
        tier_similarity[team][tier] = {"vel": avg_pts, "gm": avg_gm}
    return tier_similarity

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

def simulate_match(team_a, team_b, team_strengths, team_features, intercept, home_adv, beta_diff, beta_vel, beta_vol, beta_rank_prior, hosts, tier_similarity, h2h_biases):
    a_std = get_standard_team_name(team_a)
    a_fifa = get_fifa_rankings_name(a_std)
    a_feat = team_features.get(a_std, {"rank": 100.0})
    b_std = get_standard_team_name(team_b)
    b_fifa = get_fifa_rankings_name(b_std)
    b_feat = team_features.get(b_std, {"rank": 100.0})
    h2h_val = h2h_biases.get((a_std, b_std), 0.0)
    a_est = team_strengths.get(a_std, team_strengths.get(a_fifa, beta_rank_prior * a_feat["rank"]))
    a_str = a_est * 0.1 + (-0.008 * a_feat["rank"]) + h2h_val
    b_est = team_strengths.get(b_std, team_strengths.get(b_fifa, beta_rank_prior * b_feat["rank"]))
    b_str = b_est * 0.1 + (-0.008 * b_feat["rank"]) - h2h_val
    conf_weights = {
        "UEFA": 1.45,
        "CONMEBOL": 1.40,
        "CAF": 0.95,
        "CONCACAF": 0.85,
        "AFC": 0.75,
        "OFC": 0.40
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
    b_tier = get_tier_from_rank(b_feat["rank"])
    a_tier = get_tier_from_rank(a_feat["rank"])
    a_tier_vel = tier_similarity.get(a_std, {}).get(b_tier, {}).get("vel", 1.0)
    a_tier_gm = tier_similarity.get(a_std, {}).get(b_tier, {}).get("gm", 0.0)
    b_tier_vel = tier_similarity.get(b_std, {}).get(a_tier, {}).get("vel", 1.0)
    b_tier_gm = tier_similarity.get(b_std, {}).get(a_tier, {}).get("gm", 0.0)
    lambda_a = math.exp(
        intercept + a_adv_val + a_str - b_str
        + tuned_beta_diff * rank_diff
        + beta_vel * a_tier_vel
        + beta_vol * a_tier_gm
    )
    lambda_b = math.exp(
        intercept + b_adv_val + b_str - a_str
        - tuned_beta_diff * rank_diff
        + beta_vel * b_tier_vel
        + beta_vol * b_tier_gm
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

def run_tournament_simulation(teams, team_features, team_strengths, intercept, home_adv, beta_diff, beta_vel, beta_vol, beta_rank_prior, runs, year, r_conn, task_id, progression_mode, tier_similarity, h2h_biases):
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
    step_5 = max(1, runs // 20)
    for i in range(runs):
        active_teams = list(teams)
        random.shuffle(active_teams)
        milestone_reached = set()
        
        def check_milestones(teams_list):
            n = len(teams_list)
            if progression_mode == "reach_knockouts" and n <= 16:
                for t in teams_list:
                    milestone_reached.add(t)
            elif progression_mode == "reach_quarterfinals" and n <= 8:
                for t in teams_list:
                    milestone_reached.add(t)
            elif progression_mode == "reach_semifinals" and n <= 4:
                for t in teams_list:
                    milestone_reached.add(t)
            elif progression_mode == "reach_finals" and n <= 2:
                for t in teams_list:
                    milestone_reached.add(t)

        check_milestones(active_teams)
        while len(active_teams) > 1:
            next_round = []
            for j in range(0, len(active_teams), 2):
                if j + 1 < len(active_teams):
                    winner = simulate_match(
                        active_teams[j], active_teams[j+1],
                        team_strengths, team_features,
                        intercept, home_adv, beta_diff, beta_vel, beta_vol, beta_rank_prior, hosts,
                        tier_similarity, h2h_biases
                    )
                    next_round.append(winner)
                else:
                    next_round.append(active_teams[j])
            active_teams = next_round
            check_milestones(active_teams)
        if not progression_mode or progression_mode == "winner":
            if active_teams:
                milestone_reached.add(active_teams[0])
        for t in milestone_reached:
            win_counts[t] += 1
        if (i + 1) % step_5 == 0 or (i + 1) == runs:
            progress_pct = ((i + 1) / runs) * 100.0
            r_conn.set(f"task:{task_id}:progress", f"{progress_pct:.1f}")
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
            progression_mode = event.get("progression_mode", "")
            conn = get_db_connection()
            teams, team_features = fetch_tournament_teams(conn, year)
            h2h_biases = precompute_h2h_biases(conn, teams, year)
            tier_similarity = precompute_tier_similarity(conn, teams, year)
            conn.close()
            intercept, home_adv, beta_diff, beta_vel, beta_vol, beta_rank_prior, team_strengths = get_latest_model_params()
            results = run_tournament_simulation(
                teams, team_features, team_strengths,
                intercept, home_adv, beta_diff, beta_vel, beta_vol, beta_rank_prior, runs, year, r, task_id,
                progression_mode, tier_similarity, h2h_biases
            )
            r.set(task_id, json.dumps(results), ex=3600)
        except Exception as e:
            sys.stderr.write(str(e) + "\n")

if __name__ == "__main__":
    main()
