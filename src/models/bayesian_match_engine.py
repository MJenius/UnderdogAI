import os
import pytensor
pytensor.config.cxx = ""
import datetime
import psycopg2
import pandas as pd
import numpy as np
import pymc as pm
import arviz as az
import mlflow
from sklearn.metrics import log_loss

if __name__ == "__main__":
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5433)),
        database=os.getenv("POSTGRES_DB", "analytical_sandbox"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres")
    )
    df = pd.read_sql("SELECT * FROM fct_underdog_feature_mart", conn)
    conn.close()
    
    df = df.dropna(subset=["home_rank", "away_rank"])
    df["match_date"] = pd.to_datetime(df["match_date"]).dt.date
    df = df.sort_values("match_date")
    
    teams = sorted(list(set(df["home_team"].unique()) | set(df["away_team"].unique())))
    team_to_idx = {t: i for i, t in enumerate(teams)}
    
    team_ranks = {}
    for t in teams:
        h_r = df[df["home_team"] == t]["home_rank"]
        a_r = df[df["away_team"] == t]["away_rank"]
        all_r = pd.concat([h_r, a_r]).dropna()
        if len(all_r) > 0:
            team_ranks[t] = all_r.mean()
        else:
            team_ranks[t] = 100.0
    baseline_ranks = np.array([team_ranks[t] for t in teams])
    
    train_df = df[df["match_date"] < datetime.date(2022, 1, 1)]
    test_df = df[df["match_date"] >= datetime.date(2022, 1, 1)]
    
    train_home_idx = train_df["home_team"].map(team_to_idx).values
    train_away_idx = train_df["away_team"].map(team_to_idx).values
    train_h_score = train_df["home_score"].values.astype(int)
    train_a_score = train_df["away_score"].values.astype(int)
    train_rank_diff = train_df["rank_differential"].values.astype(float)
    train_h_vel = train_df["home_rolling_point_velocity_5"].values.astype(float)
    train_a_vel = train_df["away_rolling_point_velocity_5"].values.astype(float)
    train_h_vol = train_df["home_rank_volatility_12m"].values.astype(float)
    train_a_vol = train_df["away_rank_volatility_12m"].values.astype(float)
    
    test_home_idx = test_df["home_team"].map(team_to_idx).values
    test_away_idx = test_df["away_team"].map(team_to_idx).values
    test_rank_diff = test_df["rank_differential"].values.astype(float)
    test_h_vel = test_df["home_rolling_point_velocity_5"].values.astype(float)
    test_a_vel = test_df["away_rolling_point_velocity_5"].values.astype(float)
    test_h_vol = test_df["home_rank_volatility_12m"].values.astype(float)
    test_a_vol = test_df["away_rank_volatility_12m"].values.astype(float)
    
    coords = {"team": teams}
    with pm.Model(coords=coords) as model:
        home_idx = pm.Data("home_idx", train_home_idx)
        away_idx = pm.Data("away_idx", train_away_idx)
        rank_diff = pm.Data("rank_diff", train_rank_diff)
        h_vel = pm.Data("h_vel", train_h_vel)
        a_vel = pm.Data("a_vel", train_a_vel)
        h_vol = pm.Data("h_vol", train_h_vol)
        a_vol = pm.Data("a_vol", train_a_vol)
        
        observed_home_goals = pm.Data("observed_home_goals", train_h_score)
        observed_away_goals = pm.Data("observed_away_goals", train_a_score)
        
        intercept = pm.Normal("intercept", mu=0.0, sigma=1.0)
        home_adv = pm.Normal("home_adv", mu=0.0, sigma=1.0)
        
        beta_diff = pm.Normal("beta_diff", mu=0.0, sigma=0.5)
        beta_vel = pm.Normal("beta_vel", mu=0.0, sigma=0.5)
        beta_vol = pm.Normal("beta_vol", mu=0.0, sigma=0.5)
        
        beta_rank_prior = pm.Normal("beta_rank_prior", mu=-0.01, sigma=0.01)
        sigma_epsilon = pm.HalfNormal("sigma_epsilon", sigma=1.0)
        
        team_mu = beta_rank_prior * baseline_ranks
        epsilon = pm.Normal("epsilon", mu=0.0, sigma=sigma_epsilon, dims="team")
        team_strength = pm.Deterministic("team_strength", team_mu + epsilon, dims="team")
        
        lambda_home = pm.math.exp(
            intercept + home_adv + team_strength[home_idx] - team_strength[away_idx]
            + beta_diff * rank_diff
            + beta_vel * h_vel
            + beta_vol * h_vol
        )
        lambda_away = pm.math.exp(
            intercept + team_strength[away_idx] - team_strength[home_idx]
            - beta_diff * rank_diff
            + beta_vel * a_vel
            + beta_vol * a_vol
        )
        
        home_goals = pm.Poisson("home_goals", mu=lambda_home, observed=observed_home_goals)
        away_goals = pm.Poisson("away_goals", mu=lambda_away, observed=observed_away_goals)
    
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    try:
        mlflow.set_experiment("underdog_ai_intelligence")
    except Exception:
        mlflow.set_tracking_uri("sqlite:///mlflow.db")
        mlflow.set_experiment("underdog_ai_intelligence")
        
    with model:
        idata = pm.sample(draws=1000, tune=500, chains=2, random_seed=42)
        pm.set_data({
            "home_idx": test_home_idx,
            "away_idx": test_away_idx,
            "rank_diff": test_rank_diff,
            "h_vel": test_h_vel,
            "a_vel": test_a_vel,
            "h_vol": test_h_vol,
            "a_vol": test_a_vol,
            "observed_home_goals": np.zeros(len(test_df), dtype=int),
            "observed_away_goals": np.zeros(len(test_df), dtype=int)
        })
        post_pred = pm.sample_posterior_predictive(idata, random_seed=42)
        
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
    
    with mlflow.start_run():
        mlflow.log_params({
            "draws": 1000,
            "tune": 500,
            "chains": 2,
            "num_teams": len(teams),
            "num_train_samples": len(train_df),
            "num_test_samples": len(test_df)
        })
        mlflow.log_metrics({
            "posterior_log_loss": test_log_loss,
            "brier_calibration_error": brier_score,
            "upset_count": upsets,
            "upset_rate": upset_rate
        })
        summary = az.summary(idata)
        summary.to_csv("model_summary.csv")
        mlflow.log_artifact("model_summary.csv")
        if os.path.exists("model_summary.csv"):
            os.remove("model_summary.csv")
