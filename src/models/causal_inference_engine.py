import os
import datetime
import psycopg2
import pandas as pd
import numpy as np
import mlflow
from dowhy import CausalModel

conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=int(os.getenv("POSTGRES_PORT", 5433)),
    database=os.getenv("POSTGRES_DB", "analytical_sandbox"),
    user=os.getenv("POSTGRES_USER", "postgres"),
    password=os.getenv("POSTGRES_PASSWORD", "postgres")
)
df = pd.read_sql("SELECT * FROM fct_underdog_feature_mart", conn)
conn.close()

df["match_date"] = pd.to_datetime(df["match_date"]).dt.date
df = df.sort_values("match_date")

df_wc = df[df["tournament"] == "FIFA World Cup"].copy()
df_wc["match_year"] = pd.to_datetime(df_wc["match_date"]).dt.year
wc_years = sorted(df_wc["match_year"].unique())

records = []
for Y in wc_years:
    df_year = df_wc[df_wc["match_year"] == Y]
    cycle_start = pd.to_datetime(df_year["match_date"].min()).date()
    treatment_start = cycle_start - pd.Timedelta(days=730)
    treatment_end = cycle_start - pd.Timedelta(days=1)
    
    df_past = df[df["match_date"] <= treatment_start]
    df_past_home = df_past[["match_date", "home_team", "home_rank", "home_rank_volatility_12m"]].rename(
        columns={"home_team": "team", "home_rank": "rank", "home_rank_volatility_12m": "vol"}
    )
    df_past_away = df_past[["match_date", "away_team", "away_rank", "away_rank_volatility_12m"]].rename(
        columns={"away_team": "team", "away_rank": "rank", "away_rank_volatility_12m": "vol"}
    )
    df_past_all = pd.concat([df_past_home, df_past_away]).dropna(subset=["rank"])
    if len(df_past_all) > 0:
        df_latest_past = df_past_all.sort_values("match_date").groupby("team").last()
        snapped_ranks = df_latest_past["rank"].to_dict()
        snapped_vols = df_latest_past["vol"].to_dict()
    else:
        snapped_ranks = {}
        snapped_vols = {}
        
    df_friendlies = df[(df["tournament"] == "Friendly") & (df["match_date"] >= treatment_start) & (df["match_date"] <= treatment_end)]
    
    team_friendly_avg = {}
    if len(df_friendlies) > 0:
        h_pts = np.where(df_friendlies["home_score"] > df_friendlies["away_score"], 3.0, np.where(df_friendlies["home_score"] == df_friendlies["away_score"], 1.0, 0.0))
        a_pts = np.where(df_friendlies["away_score"] > df_friendlies["home_score"], 3.0, np.where(df_friendlies["home_score"] == df_friendlies["away_score"], 1.0, 0.0))
        df_f_home = pd.DataFrame({"match_date": df_friendlies["match_date"], "team": df_friendlies["home_team"], "points": h_pts})
        df_f_away = pd.DataFrame({"match_date": df_friendlies["match_date"], "team": df_friendlies["away_team"], "points": a_pts})
        df_f_all = pd.concat([df_f_home, df_f_away])
        for team, group in df_f_all.sort_values("match_date").groupby("team"):
            team_friendly_avg[team] = np.mean(group["points"].values[-5:])
            
    for _, row in df_year.iterrows():
        H = row["home_team"]
        A = row["away_team"]
        H_score = row["home_score"]
        A_score = row["away_score"]
        
        h_rank = snapped_ranks.get(H, row["home_rank"])
        h_vol = snapped_vols.get(H, row["home_rank_volatility_12m"])
        a_rank = snapped_ranks.get(A, row["away_rank"])
        a_vol = snapped_vols.get(A, row["away_rank_volatility_12m"])
        
        h_rank = float(h_rank) if pd.notna(h_rank) else 100.0
        h_vol = float(h_vol) if pd.notna(h_vol) else 0.0
        a_rank = float(a_rank) if pd.notna(a_rank) else 100.0
        a_vol = float(a_vol) if pd.notna(a_vol) else 0.0
        
        h_form = team_friendly_avg.get(H, 1.0)
        a_form = team_friendly_avg.get(A, 1.0)
        
        records.append({
            "treatment": int(h_form >= 1.5),
            "outcome": int(H_score > A_score),
            "team_rank": h_rank,
            "team_volatility": h_vol,
            "opponent_rank": a_rank,
            "opponent_volatility": a_vol
        })
        records.append({
            "treatment": int(a_form >= 1.5),
            "outcome": int(A_score > H_score),
            "team_rank": a_rank,
            "team_volatility": a_vol,
            "opponent_rank": h_rank,
            "opponent_volatility": h_vol
        })

df_causal = pd.DataFrame(records)

model = CausalModel(
    data=df_causal,
    treatment="treatment",
    outcome="outcome",
    common_causes=[
        "team_rank",
        "opponent_rank",
        "team_volatility",
        "opponent_volatility"
    ]
)

identified_estimand = model.identify_effect()

estimate = model.estimate_effect(
    identified_estimand,
    method_name="backdoor.linear_regression"
)

ate = float(estimate.value)

refute_placebo = model.refute_estimate(
    identified_estimand,
    estimate,
    method_name="placebo_treatment_refuter"
)

refute_random = model.refute_estimate(
    identified_estimand,
    estimate,
    method_name="random_common_cause"
)

placebo_new_effect = float(refute_placebo.new_effect)
random_new_effect = float(refute_random.new_effect)

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
try:
    mlflow.set_experiment("underdog_ai_intelligence")
except Exception:
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("underdog_ai_intelligence")

with mlflow.start_run():
    mlflow.log_params({
        "treatment_threshold": 1.5,
        "treatment_window_days": 730,
        "num_causal_records": len(df_causal)
    })
    mlflow.log_metrics({
        "average_treatment_effect": ate,
        "refutation_placebo_new_effect": placebo_new_effect,
        "refutation_random_new_effect": random_new_effect
    })
