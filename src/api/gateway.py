import os
import sys
import uuid
import json
import glob
import math
import csv
import psycopg2
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from confluent_kafka import Producer
import grpc
from concurrent import futures

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "proto")))

import simulation_pb2
import simulation_pb2_grpc

app = FastAPI()

class TournamentRequest(BaseModel):
    tournament_year: int
    simulation_runs: int
    progression_mode: str

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

def get_tier_similarity_features(conn, team_name, opponent_tier, year=None):
    std_name = get_standard_team_name(team_name)
    if opponent_tier == "Elite":
        min_rank, max_rank = 1, 15
    elif opponent_tier == "Competitive":
        min_rank, max_rank = 16, 45
    elif opponent_tier == "Mid-Tier":
        min_rank, max_rank = 46, 80
    else:
        min_rank, max_rank = 81, 9999
    if year is not None:
        query = """
            WITH team_historical_matches AS (
                SELECT 
                    CASE WHEN TRIM(home_team) = TRIM(%s) THEN away_team ELSE home_team END as opponent,
                    CASE WHEN TRIM(home_team) = TRIM(%s) THEN COALESCE(away_rank, 100) ELSE COALESCE(home_rank, 100) END as opponent_rank,
                    CASE 
                        WHEN TRIM(home_team) = TRIM(%s) THEN 
                            CASE WHEN home_score > away_score THEN 3 WHEN home_score = away_score THEN 1 ELSE 0 END
                        ELSE 
                            CASE WHEN away_score > home_score THEN 3 WHEN away_score = home_score THEN 1 ELSE 0 END
                    END as points,
                    CASE 
                        WHEN TRIM(home_team) = TRIM(%s) THEN (home_score - away_score)
                        ELSE (away_score - home_score)
                    END as goal_margin
                FROM fct_underdog_feature_mart
                WHERE (TRIM(home_team) = TRIM(%s) OR TRIM(away_team) = TRIM(%s))
                  AND match_date < MAKE_DATE(%s, 1, 1)
                  AND match_date >= MAKE_DATE(%s - 4, 1, 1)
            )
            SELECT 
                COALESCE(AVG(points), 1.0) as avg_points,
                COALESCE(AVG(goal_margin), 0.0) as avg_goal_margin
            FROM team_historical_matches
            WHERE opponent_rank >= %s AND opponent_rank <= %s;
        """
        params = (std_name, std_name, std_name, std_name, std_name, std_name, int(year), int(year), min_rank, max_rank)
    else:
        query = """
            WITH team_historical_matches AS (
                SELECT 
                    CASE WHEN TRIM(home_team) = TRIM(%s) THEN away_team ELSE home_team END as opponent,
                    CASE WHEN TRIM(home_team) = TRIM(%s) THEN COALESCE(away_rank, 100) ELSE COALESCE(home_rank, 100) END as opponent_rank,
                    CASE 
                        WHEN TRIM(home_team) = TRIM(%s) THEN 
                            CASE WHEN home_score > away_score THEN 3 WHEN home_score = away_score THEN 1 ELSE 0 END
                        ELSE 
                            CASE WHEN away_score > home_score THEN 3 WHEN away_score = home_score THEN 1 ELSE 0 END
                    END as points,
                    CASE 
                        WHEN TRIM(home_team) = TRIM(%s) THEN (home_score - away_score)
                        ELSE (away_score - home_score)
                    END as goal_margin
                FROM fct_underdog_feature_mart
                WHERE (TRIM(home_team) = TRIM(%s) OR TRIM(away_team) = TRIM(%s))
                  AND match_date < CURRENT_DATE
                  AND match_date >= CURRENT_DATE - INTERVAL '4 years'
            )
            SELECT 
                COALESCE(AVG(points), 1.0) as avg_points,
                COALESCE(AVG(goal_margin), 0.0) as avg_goal_margin
            FROM team_historical_matches
            WHERE opponent_rank >= %s AND opponent_rank <= %s;
        """
        params = (std_name, std_name, std_name, std_name, std_name, std_name, min_rank, max_rank)
    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        if row:
            return float(row[0]) if row[0] is not None else 1.0, float(row[1]) if row[1] is not None else 0.0
        return 1.0, 0.0

def get_h2h_bias(conn, team_a, team_b, year=None):
    std_a = get_standard_team_name(team_a)
    std_b = get_standard_team_name(team_b)
    if year is not None:
        query = """
            SELECT 
                EXTRACT(YEAR FROM match_date) as match_year,
                home_team,
                away_team,
                home_score,
                away_score
            FROM fct_underdog_feature_mart
            WHERE ((TRIM(home_team) = TRIM(%s) AND TRIM(away_team) = TRIM(%s))
               OR (TRIM(home_team) = TRIM(%s) AND TRIM(away_team) = TRIM(%s)))
              AND match_date < MAKE_DATE(%s, 1, 1);
        """
        params = (std_a, std_b, std_b, std_a, int(year))
        eval_year = int(year)
    else:
        query = """
            SELECT 
                EXTRACT(YEAR FROM match_date) as match_year,
                home_team,
                away_team,
                home_score,
                away_score
            FROM fct_underdog_feature_mart
            WHERE ((TRIM(home_team) = TRIM(%s) AND TRIM(away_team) = TRIM(%s))
               OR (TRIM(home_team) = TRIM(%s) AND TRIM(away_team) = TRIM(%s)))
              AND match_date < CURRENT_DATE;
        """
        params = (std_a, std_b, std_b, std_a)
        import datetime
        eval_year = datetime.date.today().year
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    sum_w_pts_a = 0.0
    sum_w_pts_b = 0.0
    for row in rows:
        match_year = int(row[0]) if row[0] is not None else eval_year
        h_team = row[1]
        a_team = row[2]
        h_score = int(row[3]) if row[3] is not None else 0
        a_score = int(row[4]) if row[4] is not None else 0
        years_ago = max(0, eval_year - match_year)
        weight = math.exp(-0.05 * years_ago)
        is_home_a = (get_standard_team_name(h_team) == std_a)
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
        return 0.15 * h2h_diff
    return 0.0

def get_team_features(conn, team_name, year=None):
    std_name = get_standard_team_name(team_name)
    fifa_name = get_fifa_rankings_name(std_name)
    conf = None
    rank = None
    if year is not None:
        rank_query = """
            SELECT rank, confederation FROM raw_fifa_rankings
            WHERE TRIM(country_full) = TRIM(%s)
              AND rank_date <= MAKE_DATE(%s, 1, 1)
            ORDER BY rank_date DESC
            LIMIT 1
        """
        params = (fifa_name, int(year))
    else:
        rank_query = """
            SELECT rank, confederation FROM raw_fifa_rankings
            WHERE TRIM(country_full) = TRIM(%s)
            ORDER BY rank_date DESC
            LIMIT 1
        """
        params = (fifa_name,)
    with conn.cursor() as cur:
        cur.execute(rank_query, params)
        row_rank = cur.fetchone()
        if row_rank:
            rank = float(row_rank[0]) if row_rank[0] is not None else None
            conf = row_rank[1]
    if rank is None:
        if year is not None:
            fallback_query = """
                SELECT rank, confederation FROM raw_fifa_rankings
                WHERE TRIM(country_full) = TRIM(%s)
                ORDER BY ABS(EXTRACT(EPOCH FROM (rank_date - MAKE_DATE(%s, 1, 1)))) ASC
                LIMIT 1
            """
            fallback_params = (fifa_name, int(year))
        else:
            fallback_query = """
                SELECT rank, confederation FROM raw_fifa_rankings
                WHERE TRIM(country_full) = TRIM(%s)
                ORDER BY rank_date DESC
                LIMIT 1
            """
            fallback_params = (fifa_name,)
        with conn.cursor() as cur:
            cur.execute(fallback_query, fallback_params)
            row_fallback = cur.fetchone()
            if row_fallback:
                rank = float(row_fallback[0]) if row_fallback[0] is not None else 100.0
                conf = row_fallback[1] if conf is None else conf
            else:
                rank = 100.0
    if year is not None:
        query = """
            SELECT 
                CASE WHEN home_team = %s THEN home_rolling_point_velocity_5 ELSE away_rolling_point_velocity_5 END as velocity,
                CASE WHEN home_team = %s THEN home_rank_volatility_12m ELSE away_rank_volatility_12m END as volatility,
                CASE WHEN home_team = %s THEN home_underdog_signal_score ELSE away_underdog_signal_score END as underdog_score
            FROM fct_underdog_feature_mart
            WHERE (home_team = %s OR away_team = %s)
              AND match_date < MAKE_DATE(%s, 1, 1)
            ORDER BY match_date DESC
            LIMIT 1
        """
        params = (std_name, std_name, std_name, std_name, std_name, int(year))
    else:
        query = """
            SELECT 
                CASE WHEN home_team = %s THEN home_rolling_point_velocity_5 ELSE away_rolling_point_velocity_5 END as velocity,
                CASE WHEN home_team = %s THEN home_rank_volatility_12m ELSE away_rank_volatility_12m END as volatility,
                CASE WHEN home_team = %s THEN home_underdog_signal_score ELSE away_underdog_signal_score END as underdog_score
            FROM fct_underdog_feature_mart
            WHERE home_team = %s OR away_team = %s
            ORDER BY match_date DESC
            LIMIT 1
        """
        params = (std_name, std_name, std_name, std_name, std_name)
    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        if row:
            return {
                "rank": rank,
                "vel": float(row[0]) if row[0] is not None else 1.0,
                "vol": float(row[1]) if row[1] is not None else 0.0,
                "underdog_score": float(row[2]) if row[2] is not None else 0.0,
                "conf": conf
            }
        return {"rank": rank, "vel": 1.0, "vol": 0.0, "underdog_score": 0.0, "conf": conf}

def poisson_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam**k * math.exp(-lam)) / math.factorial(k)

def compute_probabilities(home_team, away_team, year=None):
    intercept, home_adv, beta_diff, beta_vel, beta_vol, beta_rank_prior, team_strengths = get_latest_model_params()
    conn = get_db_connection()
    try:
        home_feats = get_team_features(conn, home_team, year)
        away_feats = get_team_features(conn, away_team, year)
        h_rank = home_feats["rank"]
        a_rank = away_feats["rank"]
        h_tier = get_tier_from_rank(h_rank)
        a_tier = get_tier_from_rank(a_rank)
        home_tier_vel, home_tier_gm = get_tier_similarity_features(conn, home_team, a_tier, year)
        away_tier_vel, away_tier_gm = get_tier_similarity_features(conn, away_team, h_tier, year)
        h2h_val = get_h2h_bias(conn, home_team, away_team, year)
    finally:
        conn.close()
    h_std = get_standard_team_name(home_team)
    h_fifa = get_fifa_rankings_name(h_std)
    h_est = team_strengths.get(h_std, team_strengths.get(h_fifa, beta_rank_prior * h_rank))
    h_str = h_est * 0.1 + (-0.008 * h_rank) + h2h_val
    a_std = get_standard_team_name(away_team)
    a_fifa = get_fifa_rankings_name(a_std)
    a_est = team_strengths.get(a_std, team_strengths.get(a_fifa, beta_rank_prior * a_rank))
    a_str = a_est * 0.1 + (-0.008 * a_rank) - h2h_val
    conf_weights = {
        "UEFA": 1.45,
        "CONMEBOL": 1.40,
        "CAF": 0.95,
        "CONCACAF": 0.85,
        "AFC": 0.75,
        "OFC": 0.40
    }
    h_conf = home_feats.get("conf")
    h_weight = conf_weights.get(h_conf, 1.0) if h_conf else 1.0
    h_str = h_str + math.log(h_weight)
    a_conf = away_feats.get("conf")
    a_weight = conf_weights.get(a_conf, 1.0) if a_conf else 1.0
    a_str = a_str + math.log(a_weight)
    neutral = True
    if year is not None:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT neutral FROM fct_underdog_feature_mart
                    WHERE ((home_team = %s AND away_team = %s) OR (home_team = %s AND away_team = %s))
                      AND EXTRACT(YEAR FROM match_date) = %s
                    LIMIT 1
                """, (home_team, away_team, away_team, home_team, int(year)))
                row = cur.fetchone()
                if row is not None:
                    neutral = bool(row[0])
        except Exception:
            pass
        finally:
            conn.close()
    host_map = {
        1970: {"Mexico"},
        2018: {"Russia"},
        2022: {"Qatar"},
        2026: {"USA", "Canada", "Mexico"}
    }
    hosts = host_map.get(year, set()) if year is not None else set()
    home_adv_applied_to_home = (not neutral) or (get_fifa_rankings_name(home_team) in hosts)
    home_adv_applied_to_away = (get_fifa_rankings_name(away_team) in hosts)
    tuned_home_adv = home_adv * 0.1
    tuned_beta_diff = -0.002
    h_adv_val = tuned_home_adv if home_adv_applied_to_home else 0.0
    a_adv_val = tuned_home_adv if home_adv_applied_to_away else 0.0
    rank_diff = h_rank - a_rank
    lambda_home = math.exp(
        intercept + h_adv_val + h_str - a_str
        + tuned_beta_diff * rank_diff
        + beta_vel * home_tier_vel
        + beta_vol * home_tier_gm
    )
    lambda_away = math.exp(
        intercept + a_adv_val + a_str - h_str
        - tuned_beta_diff * rank_diff
        + beta_vel * away_tier_vel
        + beta_vol * away_tier_gm
    )
    home_win = 0.0
    away_win = 0.0
    draw = 0.0
    for h in range(13):
        p_h = poisson_pmf(h, lambda_home)
        for a in range(13):
            p_a = poisson_pmf(a, lambda_away)
            p_joint = p_h * p_a
            if h > a:
                home_win += p_joint
            elif h < a:
                away_win += p_joint
            else:
                draw += p_joint
    total = home_win + away_win + draw
    if total > 0:
        home_win /= total
        away_win /= total
        draw /= total
    underdog_score = home_feats["underdog_score"] if h_rank > a_rank else away_feats["underdog_score"]
    if h_rank > a_rank:
        upset_prob = home_win
    elif a_rank > h_rank:
        upset_prob = away_win
    else:
        upset_prob = 0.0
    if upset_prob < 0.15:
        risk_label = "Safe"
    elif upset_prob < 0.35:
        risk_label = "Moderate"
    else:
        risk_label = "High Upset Potential"
    explainability_narrative = (
        f"{home_team} (Rank {int(h_rank)}, {h_tier}) vs {away_team} (Rank {int(a_rank)}, {a_tier}). "
        f"{home_team}'s trailing 4-year point velocity against {a_tier} opponents is {home_tier_vel:.2f} with an average goal margin of {home_tier_gm:+.2f}. "
        f"{away_team}'s trailing 4-year point velocity against {h_tier} opponents is {away_tier_vel:.2f} with an average goal margin of {away_tier_gm:+.2f}."
    )
    return home_win, away_win, draw, underdog_score, risk_label, explainability_narrative, home_tier_vel, away_tier_vel, h2h_val

@app.get("/api/v1/predict")
def predict_endpoint(home: str, away: str, year: int = None):
    try:
        home_win, away_win, draw, underdog_score, risk_label, narrative, home_tier_form, away_tier_form, h2h_bias = compute_probabilities(home, away, year)
        return {
            "home_win_prob": home_win,
            "away_win_prob": away_win,
            "draw_prob": draw,
            "underdog_signal_score": underdog_score,
            "risk_label": risk_label,
            "explainability_narrative": narrative,
            "home_tier_form": home_tier_form,
            "away_tier_form": away_tier_form,
            "h2h_bias": h2h_bias
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/features")
def features_endpoint(team: str, year: int = None):
    try:
        conn = get_db_connection()
        feats = get_team_features(conn, team, year)
        conn.close()
        return feats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/simulate", status_code=202)
def simulate_endpoint(payload: TournamentRequest):
    task_id = str(uuid.uuid4())
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    try:
        r_host = os.getenv("REDIS_HOST", "localhost")
        r_port = int(os.getenv("REDIS_PORT", 6379))
        r = redis.Redis(host=r_host, port=r_port, decode_responses=True)
        r.set(f"task:{task_id}:progress", "0.0")
        producer = Producer({"bootstrap.servers": bootstrap_servers})
        event = {
            "task_id": task_id,
            "tournament_year": payload.tournament_year,
            "simulation_runs": payload.simulation_runs,
            "progression_mode": payload.progression_mode
        }
        producer.produce("underdog_simulation_tasks", key=task_id, value=json.dumps(event))
        producer.flush(timeout=5.0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"task_id": task_id}

@app.get("/api/v1/simulate/status/{task_id}")
def simulate_status_endpoint(task_id: str):
    r_host = os.getenv("REDIS_HOST", "localhost")
    r_port = int(os.getenv("REDIS_PORT", 6379))
    try:
        r = redis.Redis(host=r_host, port=r_port, decode_responses=True)
        res = r.get(task_id)
        prog = r.get(f"task:{task_id}:progress")
        progress_val = float(prog) if prog is not None else 0.0
        if res:
            return {"task_id": task_id, "status": "COMPLETED", "result": json.loads(res), "progress": 100.0}
        return {"task_id": task_id, "status": "PENDING", "progress": progress_val}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/fixtures")
def fixtures_endpoint(year: int):
    try:
        conn = get_db_connection()
        query = """
            SELECT DISTINCT match_date, home_team, away_team
            FROM fct_underdog_feature_mart
            WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = %s
            ORDER BY match_date ASC
        """
        fixtures = []
        with conn.cursor() as cur:
            cur.execute(query, (year,))
            rows = cur.fetchall()
            for row in rows:
                match_date = str(row[0])
                home = row[1]
                away = row[2]
                h_win, a_win, draw, u_score, risk, narrative, h_form, a_form, h2h = compute_probabilities(home, away, year)
                h_feats = get_team_features(conn, home, year)
                a_feats = get_team_features(conn, away, year)
                h_rank = h_feats["rank"]
                a_rank = a_feats["rank"]
                if h_rank > a_rank:
                    upset_prob = h_win
                elif a_rank > h_rank:
                    upset_prob = a_win
                else:
                    upset_prob = 0.0
                fixtures.append({
                    "home_team": home,
                    "away_team": away,
                    "match_date": match_date,
                    "home_win_prob": h_win,
                    "away_win_prob": a_win,
                    "draw_prob": draw,
                    "upset_probability": upset_prob,
                    "risk_label": risk,
                    "explainability_narrative": narrative,
                    "home_tier_form": h_form,
                    "away_tier_form": a_form,
                    "h2h_bias": h2h
                })
        conn.close()
        fixtures.sort(key=lambda x: x["upset_probability"], reverse=True)
        return fixtures
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SimulationService(simulation_pb2_grpc.SimulationServiceServicer):
    def PredictMatch(self, request, context):
        try:
            h_win, a_win, draw, u_score, risk, narrative, h_form, a_form, h2h = compute_probabilities(request.home_team, request.away_team)
            return simulation_pb2.MatchPredictionResponse(
                home_win_prob=h_win,
                away_win_prob=a_win,
                draw_prob=draw,
                underdog_signal_score=u_score,
                risk_label=risk,
                explainability_narrative=narrative,
                home_tier_form=h_form,
                away_tier_form=a_form,
                h2h_bias=h2h
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return simulation_pb2.MatchPredictionResponse()

    def SimulateTournament(self, request, context):
        task_id = str(uuid.uuid4())
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        try:
            r_host = os.getenv("REDIS_HOST", "localhost")
            r_port = int(os.getenv("REDIS_PORT", 6379))
            r = redis.Redis(host=r_host, port=r_port, decode_responses=True)
            r.set(f"task:{task_id}:progress", "0.0")
            producer = Producer({"bootstrap.servers": bootstrap_servers})
            event = {
                "task_id": task_id,
                "tournament_year": request.tournament_year,
                "simulation_runs": request.simulation_runs,
                "progression_mode": request.progression_mode
            }
            producer.produce("underdog_simulation_tasks", key=task_id, value=json.dumps(event))
            producer.flush(timeout=5.0)
            return simulation_pb2.SimulationTaskStatus(
                task_id=task_id,
                status="PENDING",
                redis_key=task_id,
                progress=0.0
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return simulation_pb2.SimulationTaskStatus()

    def GetFixtures(self, request, context):
        try:
            conn = get_db_connection()
            query = """
                SELECT DISTINCT match_date, home_team, away_team
                FROM fct_underdog_feature_mart
                WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = %s
                ORDER BY match_date ASC
            """
            fixtures = []
            with conn.cursor() as cur:
                cur.execute(query, (request.tournament_year,))
                rows = cur.fetchall()
                for row in rows:
                    match_date = str(row[0])
                    home = row[1]
                    away = row[2]
                    h_win, a_win, draw, u_score, risk, narrative, h_form, a_form, h2h = compute_probabilities(home, away, request.tournament_year)
                    h_feats = get_team_features(conn, home, request.tournament_year)
                    a_feats = get_team_features(conn, away, request.tournament_year)
                    h_rank = h_feats["rank"]
                    a_rank = a_feats["rank"]
                    if h_rank > a_rank:
                        upset_prob = h_win
                    elif a_rank > h_rank:
                        upset_prob = a_win
                    else:
                        upset_prob = 0.0
                    fixtures.append(simulation_pb2.TournamentFixture(
                        home_team=home,
                        away_team=away,
                        match_date=match_date,
                        home_win_prob=h_win,
                        away_win_prob=a_win,
                        draw_prob=draw,
                        upset_probability=upset_prob,
                        risk_label=risk,
                        explainability_narrative=narrative
                    ))
            conn.close()
            fixtures.sort(key=lambda x: x.upset_probability, reverse=True)
            return simulation_pb2.FixtureListResponse(fixtures=fixtures)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return simulation_pb2.FixtureListResponse()

def run_grpc_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    simulation_pb2_grpc.add_SimulationServiceServicer_to_server(SimulationService(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()

@app.on_event("startup")
def startup_event():
    import threading
    t = threading.Thread(target=run_grpc_server, daemon=True)
    t.start()
