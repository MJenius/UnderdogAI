import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import pytensor
pytensor.config.cxx = ""
import datetime
import psycopg2
import pandas as pd
import numpy as np
# pyrefly: ignore [missing-import]
import pymc as pm
import arviz as az
import mlflow
import math
import hashlib
import subprocess
import time
from sklearn.metrics import log_loss
from scipy.optimize import minimize
import src.models.inference as inference
from src.temporal import split_temporally

def audit_elite_calibration(conn, year):
    query = """
        SELECT home_team, away_team
        FROM fct_underdog_feature_mart
        WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = %s
    """
    with conn.cursor() as cur:
        cur.execute(query, (year,))
        rows = cur.fetchall()
    violations = []
    for home, away in rows:
        h_win, a_win, draw, *_ = inference.compute_probabilities(home, away, year, conn)
        for team, prob in ((home, h_win), (away, a_win)):
            feats = inference.get_team_features(conn, team, year)
            if feats["rank"] <= 15 and not (0.12 <= prob <= 0.25):
                violations.append((team, prob))
    return violations

if __name__ == "__main__":
    print("Connecting to DB...", flush=True)
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5433)),
        database=os.getenv("POSTGRES_DB", "analytical_sandbox"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres")
    )
    print("Fetching data from DB...", flush=True)
    df = pd.read_sql("SELECT * FROM fct_underdog_feature_mart", conn)
    conn.close()
    print("Closing connection, data fetched.", flush=True)
    
    print("Processing data...", flush=True)
    df = df.dropna(subset=["home_rank", "away_rank"])
    df["match_date"] = pd.to_datetime(df["match_date"]).dt.date
    df = df.sort_values("match_date")
    
    teams = sorted(list(set(df["home_team"].unique()) | set(df["away_team"].unique())))
    team_to_idx = {t: i for i, t in enumerate(teams)}
    
    train_rows, validation_rows, test_rows = split_temporally(
        df.to_dict("records"), "2018-01-01", "2020-01-01"
    )
    train_df = pd.DataFrame(train_rows)
    validation_df = pd.DataFrame(validation_rows)
    test_df = pd.DataFrame(test_rows)
    if train_df.empty or validation_df.empty or test_df.empty:
        raise ValueError("temporal train, validation, and test windows must all contain matches")
    team_ranks = {}
    for team in teams:
        ranks = pd.concat([
            train_df.loc[train_df["home_team"] == team, "home_rank"],
            train_df.loc[train_df["away_team"] == team, "away_rank"],
        ]).dropna()
        team_ranks[team] = float(ranks.mean()) if len(ranks) else 100.0
    baseline_ranks = np.array([team_ranks[team] for team in teams])
    
    train_home_idx = train_df["home_team"].map(team_to_idx).values
    train_away_idx = train_df["away_team"].map(team_to_idx).values
    train_h_score = train_df["home_score"].values.astype(int)
    train_a_score = train_df["away_score"].values.astype(int)
    train_rank_diff = train_df["rank_differential"].values.astype(float)
    train_h_vel = train_df["home_rolling_point_velocity_5"].values.astype(float)
    train_a_vel = train_df["away_rolling_point_velocity_5"].values.astype(float)
    train_h_vol = train_df["home_rank_volatility_12m"].values.astype(float)
    train_a_vol = train_df["away_rank_volatility_12m"].values.astype(float)
    train_neutral = train_df["neutral"].values.astype(float)

    validation_home_idx = validation_df["home_team"].map(team_to_idx).values
    validation_away_idx = validation_df["away_team"].map(team_to_idx).values
    validation_y = np.select(
        [validation_df["home_score"] > validation_df["away_score"], validation_df["home_score"] == validation_df["away_score"]],
        [0, 1], default=2,
    )

    test_home_idx = test_df["home_team"].map(team_to_idx).values
    test_away_idx = test_df["away_team"].map(team_to_idx).values
    test_rank_diff = test_df["rank_differential"].values.astype(float)
    test_h_vel = test_df["home_rolling_point_velocity_5"].values.astype(float)
    test_a_vel = test_df["away_rolling_point_velocity_5"].values.astype(float)
    test_h_vol = test_df["home_rank_volatility_12m"].values.astype(float)
    test_a_vol = test_df["away_rank_volatility_12m"].values.astype(float)
    test_neutral = test_df["neutral"].values.astype(float)
    
    print("Defining PyMC model...", flush=True)
    coords = {"team": teams}
    with pm.Model(coords=coords) as model:
        home_idx = pm.Data("home_idx", train_home_idx)
        away_idx = pm.Data("away_idx", train_away_idx)
        h_vel = pm.Data("h_vel", train_h_vel)
        a_vel = pm.Data("a_vel", train_a_vel)
        h_vol = pm.Data("h_vol", train_h_vol)
        a_vol = pm.Data("a_vol", train_a_vol)
        neutral_flag = pm.Data("neutral_flag", train_neutral)
        
        observed_home_goals = pm.Data("observed_home_goals", train_h_score)
        observed_away_goals = pm.Data("observed_away_goals", train_a_score)
        
        intercept = pm.Normal("intercept", mu=0.0, sigma=1.0)
        home_adv = pm.Normal("home_adv", mu=0.0, sigma=1.0)
        home_adv_neutral = pm.Normal("home_adv_neutral", mu=0.0, sigma=0.3)
        
        beta_vel = pm.Normal("beta_vel", mu=0.0, sigma=0.5)
        beta_vol = pm.Normal("beta_vol", mu=0.0, sigma=0.5)
        
        beta_rank_prior = pm.Normal("beta_rank_prior", mu=-0.01, sigma=0.01)
        sigma_epsilon = pm.HalfNormal("sigma_epsilon", sigma=0.3)
        
        team_mu = beta_rank_prior * baseline_ranks
        epsilon = pm.Normal("epsilon", mu=0.0, sigma=sigma_epsilon, dims="team")
        team_strength = pm.Deterministic("team_strength", team_mu + epsilon, dims="team")
        
        effective_home_adv = home_adv * (1.0 - neutral_flag) + home_adv_neutral * neutral_flag
        effective_away_adv = home_adv_neutral * neutral_flag
        
        lambda_home = pm.math.exp(
            intercept + effective_home_adv + team_strength[home_idx] - team_strength[away_idx]
            + beta_vel * h_vel
            + beta_vol * h_vol
        )
        lambda_away = pm.math.exp(
            intercept + effective_away_adv + team_strength[away_idx] - team_strength[home_idx]
            + beta_vel * a_vel
            + beta_vol * a_vol
        )
        
        home_goals = pm.Poisson("home_goals", mu=lambda_home, observed=observed_home_goals)
        away_goals = pm.Poisson("away_goals", mu=lambda_away, observed=observed_away_goals)
    
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
    try:
        mlflow.set_experiment("underdog_ai_intelligence")
    except Exception:
        mlflow.set_tracking_uri("sqlite:///mlflow.db")
        mlflow.set_experiment("underdog_ai_intelligence")
        
    with model:
        training_started = time.perf_counter()
        idata = pm.sample(draws=1000, tune=500, chains=2, cores=1, random_seed=42)
        training_seconds = time.perf_counter() - training_started
        pm.set_data({
            "home_idx": validation_home_idx, "away_idx": validation_away_idx,
            "h_vel": validation_df["home_rolling_point_velocity_5"].values.astype(float),
            "a_vel": validation_df["away_rolling_point_velocity_5"].values.astype(float),
            "h_vol": validation_df["home_rank_volatility_12m"].values.astype(float),
            "a_vol": validation_df["away_rank_volatility_12m"].values.astype(float),
            "neutral_flag": validation_df["neutral"].values.astype(float),
            "observed_home_goals": np.zeros(len(validation_df), dtype=int),
            "observed_away_goals": np.zeros(len(validation_df), dtype=int),
        })
        validation_pred = pm.sample_posterior_predictive(idata, random_seed=42)
        validation_home = np.stack(validation_pred.posterior_predictive["home_goals"]).reshape(-1, len(validation_df))
        validation_away = np.stack(validation_pred.posterior_predictive["away_goals"]).reshape(-1, len(validation_df))
        validation_probs = np.column_stack([
            np.mean(validation_home > validation_away, axis=0),
            np.mean(validation_home == validation_away, axis=0),
            np.mean(validation_home < validation_away, axis=0),
        ])
        validation_log_loss = log_loss(validation_y, validation_probs, labels=[0, 1, 2])
        validation_one_hot = np.eye(3)[validation_y]
        validation_brier = np.mean(np.sum((validation_probs - validation_one_hot) ** 2, axis=1))
        pm.set_data({
            "home_idx": test_home_idx,
            "away_idx": test_away_idx,
            "h_vel": test_h_vel,
            "a_vel": test_a_vel,
            "h_vol": test_h_vol,
            "a_vol": test_a_vol,
            "neutral_flag": test_neutral,
            "observed_home_goals": np.zeros(len(test_df), dtype=int),
            "observed_away_goals": np.zeros(len(test_df), dtype=int)
        })
        inference_started = time.perf_counter()
        post_pred = pm.sample_posterior_predictive(idata, random_seed=42)
        inference_seconds = time.perf_counter() - inference_started
        
    home_samples = np.stack(post_pred.posterior_predictive["home_goals"]).reshape(-1, len(test_df))
    away_samples = np.stack(post_pred.posterior_predictive["away_goals"]).reshape(-1, len(test_df))
    
    p_h = np.mean(home_samples > away_samples, axis=0)
    p_d = np.mean(home_samples == away_samples, axis=0)
    p_a = np.mean(home_samples < away_samples, axis=0)
    probs = np.column_stack([p_h, p_d, p_a])
    
    y_true = []
    for h, a in zip(test_df["home_score"], test_df["away_score"]):
        if h > a:
            y_true.append(0)
        elif h == a:
            y_true.append(1)
        else:
            y_true.append(2)
    y_true = np.array(y_true)
    
    test_log_loss = log_loss(y_true, probs, labels=[0, 1, 2])
    
    y_true_oh = np.zeros_like(probs)
    y_true_oh[np.arange(len(y_true)), y_true] = 1.0
    brier_score = np.mean(np.sum((probs - y_true_oh) ** 2, axis=1))
    reliability = []
    for outcome in range(3):
        confidence = probs[:, outcome]
        observed = (y_true == outcome).astype(float)
        bins = []
        for low in np.linspace(0, 0.9, 10):
            mask = (confidence >= low) & (confidence < low + 0.1 if low < 0.9 else confidence <= 1.0)
            if np.any(mask):
                bins.append({"lower": round(float(low), 1), "count": int(mask.sum()),
                             "mean_probability": float(confidence[mask].mean()),
                             "observed_frequency": float(observed[mask].mean())})
        reliability.append({"outcome": ["home_win", "draw", "away_win"][outcome], "bins": bins})
    
    upsets = 0
    non_draws = 0
    for idx, val in enumerate(y_true):
        ph = probs[idx, 0]
        pa = probs[idx, 2]
        if val == 0:
            non_draws += 1
            if ph < pa:
                upsets += 1
        elif val == 2:
            non_draws += 1
            if pa < ph:
                upsets += 1
    upset_rate = upsets / non_draws if non_draws > 0 else 0.0
    
    summary = az.summary(idata)
    
    intercept_mean = float(summary.loc["intercept", "mean"])
    home_adv_mean = float(summary.loc["home_adv", "mean"])
    home_adv_neutral_mean = float(summary.loc["home_adv_neutral", "mean"])
    beta_rank_prior_mean = float(summary.loc["beta_rank_prior", "mean"])
    
    team_strengths_mean = {}
    for t in teams:
        row_name = f"team_strength[{t}]"
        if row_name in summary.index:
            team_strengths_mean[t] = float(summary.loc[row_name, "mean"])
            
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5433)),
        database=os.getenv("POSTGRES_DB", "analytical_sandbox"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres")
    )
    
    with mlflow.start_run():
        mlflow.log_params({
            "draws": 1000,
            "tune": 500,
            "chains": 2,
            "num_teams": len(teams),
            "num_train_samples": len(train_df),
            "num_validation_samples": len(validation_df),
            "num_test_samples": len(test_df),
            "train_end_exclusive": "2018-01-01",
            "validation_end_exclusive": "2020-01-01",
            "validation_samples_reserved": len(validation_df),
        })
        mlflow.log_metrics({
            "posterior_log_loss": test_log_loss,
            "multiclass_brier_score": brier_score,
            "validation_log_loss": validation_log_loss,
            "validation_multiclass_brier_score": validation_brier,
            "upset_count": upsets,
            "upset_rate": upset_rate,
            "training_seconds": training_seconds,
            "posterior_predictive_seconds": inference_seconds,
            "posterior_predictive_rows_per_second": len(test_df) / inference_seconds
        })
        mlflow.set_tags({
            "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "dataset_sha256": hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest(),
        })
        mlflow.log_dict({
            "features": ["rank_differential", "rolling_point_velocity_5", "rank_volatility_12m", "neutral"],
            "train": {"start": str(train_df["match_date"].min()), "end_exclusive": "2018-01-01"},
            "validation": {"start": "2018-01-01", "end_exclusive": "2020-01-01"},
            "test": {"start": "2020-01-01", "end": str(test_df["match_date"].max())},
        }, "lineage.json")
        mlflow.log_dict({"test": {"multiclass_log_loss": float(test_log_loss), "multiclass_brier_score": float(brier_score),
                                   "reliability_bins": reliability},
                         "validation": {"multiclass_log_loss": float(validation_log_loss),
                                        "multiclass_brier_score": float(validation_brier)}},
                        "evaluation.json")
        summary.to_csv("model_summary.csv")
        mlflow.log_artifact("model_summary.csv")
        
        # Run elite calibration audit
        violations = audit_elite_calibration(conn, 2022)
        print("Elite Calibration Violations:", violations)
        
        conn.close()
        if os.path.exists("model_summary.csv"):
            os.remove("model_summary.csv")
