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
from sklearn.metrics import log_loss
from scipy.optimize import minimize
import src.models.inference as inference

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
    train_neutral = train_df["neutral"].values.astype(float)
    
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
        idata = pm.sample(draws=1000, tune=500, chains=2, cores=1, random_seed=42)
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
    
    matches_to_calibrate = []
    unique_years = test_df["match_date"].apply(lambda d: d.year).unique()
    for yr in unique_years:
        yr_df = test_df[test_df["match_date"].apply(lambda d: d.year) == yr]
        yr_teams = list(set(yr_df["home_team"].unique()) | set(yr_df["away_team"].unique()))
        h2h_biases = inference.precompute_h2h_biases(conn, yr_teams, yr)
        tier_similarity = inference.precompute_tier_similarity(conn, yr_teams, yr)
        team_features = {}
        for t in yr_teams:
            team_features[t] = inference.get_team_features(conn, t, yr)
            
        for idx, row in yr_df.iterrows():
            h = row["home_team"]
            a = row["away_team"]
            h_score = int(row["home_score"])
            a_score = int(row["away_score"])
            
            h_feats = team_features[h]
            a_feats = team_features[a]
            h_rank = h_feats["rank"]
            a_rank = a_feats["rank"]
            h_tier = inference.get_tier_from_rank(h_rank)
            a_tier = inference.get_tier_from_rank(a_rank)
            
            h_tier_vel = tier_similarity.get(h, {}).get(a_tier, {}).get("vel", 1.0)
            h_tier_gm = tier_similarity.get(h, {}).get(a_tier, {}).get("gm", 0.0)
            a_tier_vel = tier_similarity.get(a, {}).get(h_tier, {}).get("vel", 1.0)
            a_tier_gm = tier_similarity.get(a, {}).get(h_tier, {}).get("gm", 0.0)
            
            h2h_entry = h2h_biases.get((h, a), (0.0, False))
            if isinstance(h2h_entry, tuple):
                h2h_val = h2h_entry[0]
            else:
                h2h_val = h2h_entry
            
            h_std = inference.get_standard_team_name(h)
            h_fifa = inference.get_fifa_rankings_name(h_std)
            h_est = team_strengths_mean.get(h_std, team_strengths_mean.get(h_fifa, beta_rank_prior_mean * h_rank))
            h_str = h_est + 0.5 * h2h_val
            
            a_std = inference.get_standard_team_name(a)
            a_fifa = inference.get_fifa_rankings_name(a_std)
            a_est = team_strengths_mean.get(a_std, team_strengths_mean.get(a_fifa, beta_rank_prior_mean * a_rank))
            a_str = a_est - 0.5 * h2h_val
            
            conf_weights = {
                "UEFA": 1.45,
                "CONMEBOL": 1.40,
                "CAF": 0.95,
                "CONCACAF": 0.85,
                "AFC": 0.75,
                "OFC": 0.40
            }
            h_conf = h_feats.get("conf")
            h_weight = conf_weights.get(h_conf, 1.0) if h_conf else 1.0
            h_str = h_str + math.log(h_weight)
            
            a_conf = a_feats.get("conf")
            a_weight = conf_weights.get(a_conf, 1.0) if a_conf else 1.0
            a_str = a_str + math.log(a_weight)
            
            neutral_val = bool(row["neutral"])
            host_map = {
                1970: {"Mexico"},
                2018: {"Russia"},
                2022: {"Qatar"},
                2026: {"USA", "Canada", "Mexico"}
            }
            hosts = host_map.get(yr, set())
            home_adv_applied_to_home = (not neutral_val) or (inference.get_fifa_rankings_name(h) in hosts)
            home_adv_applied_to_away = (inference.get_fifa_rankings_name(a) in hosts)
            
            h_adv_val = home_adv_mean if home_adv_applied_to_home else (home_adv_neutral_mean if neutral_val else 0.0)
            a_adv_val = home_adv_mean if home_adv_applied_to_away else (home_adv_neutral_mean if neutral_val else 0.0)
            
            base_h = intercept_mean + h_adv_val + h_str - a_str
            base_a = intercept_mean + a_adv_val + a_str - h_str
            
            matches_to_calibrate.append({
                "base_h": base_h,
                "base_a": base_a,
                "h_tier_vel": h_tier_vel,
                "h_tier_gm": h_tier_gm,
                "a_tier_vel": a_tier_vel,
                "a_tier_gm": a_tier_gm,
                "home_score": h_score,
                "away_score": a_score
            })
        
    def neg_log_loss(params):
        beta_tier_vel, beta_tier_gm = params
        loss = 0.0
        for m in matches_to_calibrate:
            log_lam_h = m["base_h"] + beta_tier_vel * m["h_tier_vel"] + beta_tier_gm * m["h_tier_gm"]
            log_lam_a = m["base_a"] + beta_tier_vel * m["a_tier_vel"] + beta_tier_gm * m["a_tier_gm"]
            lam_h = np.exp(log_lam_h)
            lam_a = np.exp(log_lam_a)
            loss += -(m["home_score"] * log_lam_h - lam_h) - (m["away_score"] * log_lam_a - lam_a)
        return loss
        
    result_opt = minimize(neg_log_loss, x0=np.array([0.0, 0.0]), method="Nelder-Mead")
    calibrated_beta_vel, calibrated_beta_vol = result_opt.x
    
    summary.at["beta_vel", "mean"] = calibrated_beta_vel
    summary.at["beta_vol", "mean"] = calibrated_beta_vol
    
    with mlflow.start_run():
        mlflow.log_params({
            "draws": 1000,
            "tune": 500,
            "chains": 2,
            "num_teams": len(teams),
            "num_train_samples": len(train_df),
            "num_test_samples": len(test_df),
            "calibrated_beta_vel": calibrated_beta_vel,
            "calibrated_beta_vol": calibrated_beta_vol
        })
        mlflow.log_metrics({
            "posterior_log_loss": test_log_loss,
            "brier_calibration_error": brier_score,
            "upset_count": upsets,
            "upset_rate": upset_rate
        })
        summary.to_csv("model_summary.csv")
        mlflow.log_artifact("model_summary.csv")
        
        # Run elite calibration audit
        violations = audit_elite_calibration(conn, 2022)
        print("Elite Calibration Violations:", violations)
        
        conn.close()
        if os.path.exists("model_summary.csv"):
            os.remove("model_summary.csv")
