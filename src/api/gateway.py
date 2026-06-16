import os
import sys
import uuid
import json
import glob
import math
import csv
import psycopg2
import redis
import logging
import time
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from confluent_kafka import Producer
import grpc
from concurrent import futures

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "proto")))

import simulation_pb2
import simulation_pb2_grpc

app = FastAPI()

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    response = await call_next(request)
    
    elapsed_ms = (time.time() - start_time) * 1000
    log_entry = {
        "request_id": request_id,
        "method": request.method,
        "endpoint": request.url.path,
        "status": response.status_code,
        "latency_ms": round(elapsed_ms, 2)
    }
    print(json.dumps(log_entry))
    
    response.headers["X-Request-ID"] = request_id
    return response

class TournamentRequest(BaseModel):
    tournament_year: int
    simulation_runs: int
    progression_mode: str

import src.models.inference as inference
import src.models.shootout_resilience as shootout_mod
import src.models.tournament_weights as tournament_weights

def get_db_connection():
    return inference.get_db_connection()

@app.get("/api/v1/predict")
def predict_endpoint(home: str, away: str, year: int = None):
    try:
        result = inference.compute_probabilities(home, away, year)
        h_win, a_win, draw, u_score, risk, narrative, h_form, a_form, h2h = result[:9]
        shootout_h = result[9] if len(result) > 9 else 0.5
        shootout_a = result[10] if len(result) > 10 else 0.5
        momentum_h = result[11] if len(result) > 11 else 0.0
        momentum_a = result[12] if len(result) > 12 else 0.0
        bogey = result[13] if len(result) > 13 else False
        return {
            "home_win_prob": h_win,
            "away_win_prob": a_win,
            "draw_prob": draw,
            "underdog_signal_score": u_score,
            "risk_label": risk,
            "explainability_narrative": narrative,
            "home_tier_form": h_form,
            "away_tier_form": a_form,
            "h2h_bias": h2h,
            "shootout_resilience_home": shootout_h,
            "shootout_resilience_away": shootout_a,
            "momentum_home": momentum_h,
            "momentum_away": momentum_a,
            "bogey_team_flag": bogey
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/features")
def features_endpoint(team: str, year: int = None):
    try:
        conn = inference.get_db_connection()
        feats = inference.get_team_features(conn, team, year)
        conn.close()
        return feats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/teams")
def teams_endpoint(year: int):
    try:
        if year < 1993:
            if year == 1970:
                return [
                    "Belgium", "Brazil", "Bulgaria", "Czechoslovakia", "El Salvador",
                    "England", "Israel", "Italy", "Mexico", "Morocco", "Peru",
                    "Romania", "Soviet Union", "Sweden", "Uruguay", "West Germany"
                ]
            return []
        conn = inference.get_db_connection()
        try:
            query = """
                SELECT DISTINCT country_full AS team
                FROM public.raw_fifa_rankings
                WHERE rank_date = (
                    SELECT MAX(rank_date)
                    FROM public.raw_fifa_rankings
                    WHERE rank_date <= MAKE_DATE(%s, 1, 1)
                )
                ORDER BY team ASC;
            """
            with conn.cursor() as cur:
                cur.execute(query, (year,))
                rows = cur.fetchall()
            teams = sorted(list({inference.get_standard_team_name(r[0]) for r in rows}))
            return teams
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/dark-horses")
def dark_horses_endpoint(year: int):
    try:
        conn = inference.get_db_connection()
        try:
            query = """
                WITH team_stats AS (
                    SELECT 
                        home_team AS team,
                        home_rank AS rank,
                        home_rolling_point_velocity_5 AS velocity,
                        home_rank_volatility_12m AS volatility,
                        home_underdog_signal_score AS underdog_score,
                        match_date
                    FROM fct_underdog_feature_mart
                    WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = %s
                    UNION ALL
                    SELECT 
                        away_team AS team,
                        away_rank AS rank,
                        away_rolling_point_velocity_5 AS velocity,
                        away_rank_volatility_12m AS volatility,
                        away_underdog_signal_score AS underdog_score,
                        match_date
                    FROM fct_underdog_feature_mart
                    WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = %s
                ),
                ranked_stats AS (
                    SELECT 
                        team,
                        rank,
                        velocity,
                        volatility,
                        underdog_score,
                        ROW_NUMBER() OVER (PARTITION BY team ORDER BY match_date ASC) as rn
                    FROM team_stats
                )
                SELECT 
                    team,
                    rank,
                    velocity,
                    volatility,
                    underdog_score
                FROM ranked_stats
                WHERE rn = 1
                ORDER BY underdog_score DESC;
            """
            with conn.cursor() as cur:
                cur.execute(query, (year, year))
                rows = cur.fetchall()
            dark_horses = []
            for r in rows:
                dark_horses.append({
                    "team": r[0],
                    "rank": float(r[1]) if r[1] is not None else 100.0,
                    "velocity": float(r[2]) if r[2] is not None else 1.0,
                    "volatility": float(r[3]) if r[3] is not None else 0.0,
                    "underdog_score": float(r[4]) if r[4] is not None else 0.0
                })
            return dark_horses
        finally:
            conn.close()
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
        r.set(f"task:{task_id}:progress", "0.0", ex=3600)
        r.set(f"task:{task_id}:status", "PENDING", ex=3600)
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
        status = r.get(f"task:{task_id}:status")
        if status == "ERROR":
            return {"task_id": task_id, "status": "ERROR"}
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
        conn = inference.get_db_connection()
        fixtures = inference.fixtures_endpoint_batched(conn, year)
        conn.close()
        return fixtures
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/shootout-stats")
def shootout_stats_endpoint(team: str, year: int = None):
    try:
        conn = inference.get_db_connection()
        stats = shootout_mod.get_shootout_stats(conn, team, year)
        conn.close()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/momentum")
def momentum_endpoint(team: str, year: int = None):
    try:
        conn = inference.get_db_connection()
        momentum = inference.get_rank_momentum(conn, team, year)
        conn.close()
        return momentum
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/h2h")
def h2h_endpoint(team_a: str, team_b: str, year: int = None):
    try:
        conn = inference.get_db_connection()
        bias, bogey = inference.get_h2h_bias(conn, team_a, team_b, year)
        conn.close()
        return {"h2h_bias": bias, "bogey_team_flag": bogey}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sparkline")
def sparkline_endpoint(team: str):
    try:
        conn = inference.get_db_connection()
        std_name = inference.get_standard_team_name(team)
        fifa_name = inference.get_fifa_rankings_name(std_name)
        query = """
            SELECT rank_date, rank, total_points, rank_change
            FROM raw_fifa_rankings
            WHERE TRIM(country_full) = TRIM(%s)
            ORDER BY rank_date DESC
            LIMIT 24
        """
        with conn.cursor() as cur:
            cur.execute(query, (fifa_name,))
            rows = cur.fetchall()
        conn.close()
        points = []
        for row in reversed(rows):
            points.append({
                "date": str(row[0]),
                "rank": int(row[1]) if row[1] is not None else 100,
                "points": float(row[2]) if row[2] is not None else 0.0,
                "rank_change": int(row[3]) if row[3] is not None else 0
            })
        return points
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sensitivity")
def sensitivity_endpoint(home: str, away: str, year: int = None):
    try:
        base_result = inference.compute_probabilities(home, away, year)
        base_h, base_a, base_d = base_result[0], base_result[1], base_result[2]
        features = {}
        conn = inference.get_db_connection()
        home_feats = inference.get_team_features(conn, home, year)
        away_feats = inference.get_team_features(conn, away, year)
        conn.close()
        features["rank_differential"] = {
            "home_rank": home_feats["rank"],
            "away_rank": away_feats["rank"],
            "gap": abs(home_feats["rank"] - away_feats["rank"])
        }
        features["base_prediction"] = {
            "home_win": base_h,
            "away_win": base_a,
            "draw": base_d
        }
        momentum_h = base_result[11] if len(base_result) > 11 else 0.0
        momentum_a = base_result[12] if len(base_result) > 12 else 0.0
        shootout_h = base_result[9] if len(base_result) > 9 else 0.5
        shootout_a = base_result[10] if len(base_result) > 10 else 0.5
        bogey = base_result[13] if len(base_result) > 13 else False
        h2h = base_result[8] if len(base_result) > 8 else 0.0
        features["contributing_factors"] = [
            {"name": "Rank Differential", "value": home_feats["rank"] - away_feats["rank"], "impact": "high" if abs(home_feats["rank"] - away_feats["rank"]) > 30 else "moderate"},
            {"name": "Home Momentum", "value": momentum_h, "impact": "high" if abs(momentum_h) > 50 else "low"},
            {"name": "Away Momentum", "value": momentum_a, "impact": "high" if abs(momentum_a) > 50 else "low"},
            {"name": "Home Shootout Rate", "value": shootout_h, "impact": "moderate" if shootout_h > 0.6 else "low"},
            {"name": "Away Shootout Rate", "value": shootout_a, "impact": "moderate" if shootout_a > 0.6 else "low"},
            {"name": "H2H Bias", "value": h2h, "impact": "high" if abs(h2h) > 0.05 else "low"},
            {"name": "Bogey Team", "value": bogey, "impact": "high" if bogey else "none"},
        ]
        return features
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/calibration")
def calibration_endpoint():
    try:
        files = glob.glob(os.path.join("mlruns", "**", "model_summary.csv"), recursive=True)
        if not files:
            return {"status": "no_model_found"}
        latest_file = max(files, key=os.path.getmtime)
        params = {}
        with open(latest_file, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if not row:
                    continue
                params[row[0]] = float(row[1])
        return {
            "model_file": latest_file,
            "intercept": params.get("intercept", 0.0),
            "home_adv": params.get("home_adv", 0.0),
            "beta_diff": params.get("beta_diff", 0.0),
            "beta_vel": params.get("beta_vel", 0.0),
            "beta_vol": params.get("beta_vol", 0.0),
            "status": "loaded"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/seeding")
def seeding_endpoint(year: int):
    try:
        conn = inference.get_db_connection()
        result = inference.simulate_seeding_draw(conn, year)
        conn.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/historical-upsets")
def historical_upsets_endpoint(year: int):
    try:
        conn = inference.get_db_connection()
        query = """
            SELECT match_date, home_team, away_team, home_score, away_score,
                   COALESCE(home_rank, 100) as home_rank, COALESCE(away_rank, 100) as away_rank
            FROM fct_underdog_feature_mart
            WHERE tournament = 'FIFA World Cup'
              AND EXTRACT(YEAR FROM match_date) = %s
              AND (
                  (home_score > away_score AND COALESCE(home_rank, 100) > COALESCE(away_rank, 100))
                  OR
                  (away_score > home_score AND COALESCE(away_rank, 100) > COALESCE(home_rank, 100))
              )
            ORDER BY ABS(COALESCE(home_rank, 100) - COALESCE(away_rank, 100)) DESC
        """
        with conn.cursor() as cur:
            cur.execute(query, (year,))
            rows = cur.fetchall()
        conn.close()
        upsets = []
        for r in rows:
            h_rank = int(r[5])
            a_rank = int(r[6])
            upsets.append({
                "match_date": str(r[0]),
                "home_team": r[1],
                "away_team": r[2],
                "home_score": int(r[3]),
                "away_score": int(r[4]),
                "home_rank": h_rank,
                "away_rank": a_rank,
                "rank_gap": abs(h_rank - a_rank),
                "upset_winner": r[1] if int(r[3]) > int(r[4]) else r[2]
            })
        return upsets
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SimulationService(simulation_pb2_grpc.SimulationServiceServicer):
    def PredictMatch(self, request, context):
        try:
            result = inference.compute_probabilities(request.home_team, request.away_team)
            h_win, a_win, draw, u_score, risk, narrative, h_form, a_form, h2h = result[:9]
            shootout_h = result[9] if len(result) > 9 else 0.5
            shootout_a = result[10] if len(result) > 10 else 0.5
            momentum_h = result[11] if len(result) > 11 else 0.0
            momentum_a = result[12] if len(result) > 12 else 0.0
            bogey = result[13] if len(result) > 13 else False
            return simulation_pb2.MatchPredictionResponse(
                home_win_prob=h_win,
                away_win_prob=a_win,
                draw_prob=draw,
                underdog_signal_score=u_score,
                risk_label=risk,
                explainability_narrative=narrative,
                home_tier_form=h_form,
                away_tier_form=a_form,
                h2h_bias=h2h,
                shootout_resilience_home=shootout_h,
                shootout_resilience_away=shootout_a,
                momentum_home=momentum_h,
                momentum_away=momentum_a,
                bogey_team_flag=bogey
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
            r.set(f"task:{task_id}:progress", "0.0", ex=3600)
            r.set(f"task:{task_id}:status", "PENDING", ex=3600)
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
                progress=0.0,
                progression_mode=request.progression_mode
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return simulation_pb2.SimulationTaskStatus()

    def GetSimulationStatus(self, request, context):
        try:
            r_host = os.getenv("REDIS_HOST", "localhost")
            r_port = int(os.getenv("REDIS_PORT", 6379))
            r = redis.Redis(host=r_host, port=r_port, decode_responses=True)
            task_id = request.task_id
            status = r.get(f"task:{task_id}:status") or "PENDING"
            progress = float(r.get(f"task:{task_id}:progress") or 0.0)
            res = r.get(task_id)
            result_map = {}
            if res:
                result_map = json.loads(res)
                status = "COMPLETED"
                progress = 100.0
            return simulation_pb2.SimulationTaskStatus(
                task_id=task_id,
                status=status,
                redis_key=task_id,
                progress=progress,
                result=result_map,
                progression_mode=""
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return simulation_pb2.SimulationTaskStatus()

    def GetFixtures(self, request, context):
        try:
            conn = inference.get_db_connection()
            fixtures_list = inference.fixtures_endpoint_batched(conn, request.tournament_year)
            conn.close()
            
            grpc_fixtures = []
            for f in fixtures_list:
                home_lookback = simulation_pb2.TierLookbackStats(
                    trailing_point_velocity=f.get("home_tier_form", 1.0),
                    trailing_goal_margin=0.0,
                    opponent_tier=""
                )
                away_lookback = simulation_pb2.TierLookbackStats(
                    trailing_point_velocity=f.get("away_tier_form", 1.0),
                    trailing_goal_margin=0.0,
                    opponent_tier=""
                )
                grpc_fixtures.append(simulation_pb2.TournamentFixture(
                    home_team=f["home_team"],
                    away_team=f["away_team"],
                    match_date=f["match_date"],
                    home_win_prob=f["home_win_prob"],
                    away_win_prob=f["away_win_prob"],
                    draw_prob=f["draw_prob"],
                    upset_probability=f["upset_probability"],
                    risk_label=f["risk_label"],
                    explainability_narrative=f["explainability_narrative"],
                    home_lookback=home_lookback,
                    away_lookback=away_lookback,
                    h2h_bias=f["h2h_bias"]
                ))
            return simulation_pb2.FixtureListResponse(fixtures=grpc_fixtures)
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
