import time
import sys
import os
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.inference import compute_probabilities, get_db_connection, get_latest_model_params
from src.workers.simulation_worker import fetch_tournament_teams, get_match_lambdas, sample_poisson

def profile_db_and_prediction():
    print("--- Profiling Database Connection ---")
    start = time.perf_counter()
    try:
        conn = get_db_connection()
        db_time = (time.perf_counter() - start) * 1000
        print(f"PostgreSQL Connection Latency: {db_time:.2f} ms")
        conn.close()
    except Exception as e:
        print(f"Could not connect to PostgreSQL database: {e}")
        return False

    print("\n--- Profiling Single-Match Prediction (compute_probabilities) ---")
    latencies = []
    # Run a few warmup rounds
    for _ in range(5):
        try:
            compute_probabilities("Brazil", "France", 2022)
        except Exception:
            pass

    for i in range(30):
        t0 = time.perf_counter()
        try:
            compute_probabilities("Brazil", "France", 2022)
            latencies.append((time.perf_counter() - t0) * 1000)
        except Exception as e:
            print(f"Prediction failed at iteration {i}: {e}")
            break

    if latencies:
        print(f"Min Latency: {np.min(latencies):.2f} ms")
        print(f"Max Latency: {np.max(latencies):.2f} ms")
        print(f"Mean Latency: {np.mean(latencies):.2f} ms")
        print(f"Median Latency: {np.median(latencies):.2f} ms")
        print(f"90th Percentile: {np.percentile(latencies, 90):.2f} ms")
    return True

def profile_simulation():
    print("\n--- Profiling Simulation Worker ---")
    try:
        conn = get_db_connection()
        # Fetch actual tournament teams for 2022 World Cup
        teams, team_features = fetch_tournament_teams(conn, 2022)
        conn.close()
    except Exception as e:
        print(f"Failed to fetch tournament teams from DB: {e}")
        return

    print(f"Loaded {len(teams)} teams for 2022 World Cup simulation.")
    
    # Load model parameters
    intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior, team_strengths = get_latest_model_params()
    
    # Let's benchmark a mock simulation run of a 32-team tournament
    # (Group stages + Knockout stages)
    # Total matches in a 32-team World Cup = 48 group stage + 15 knockout stage = 63 matches.
    num_runs = 1000
    
    print(f"Simulating a 32-team tournament ({num_runs} Monte Carlo runs)...")
    
    # We will simulate 63 matches per run, so total 63,000 matches.
    t0 = time.perf_counter()
    
    total_matches = 0
    for run in range(num_runs):
        # Mock group stage: 48 matches
        # Group stage consists of 8 groups of 4 teams -> each group has 6 matches. Total 48 matches.
        for g in range(8):
            g_teams = teams[g*4 : (g+1)*4]
            if len(g_teams) < 4:
                continue
            # Each pair plays once: 6 combinations
            for i in range(4):
                for j in range(i+1, 4):
                    # Compute lambdas and sample goals
                    try:
                        lam_a, lam_b = get_match_lambdas(
                            g_teams[i], g_teams[j], team_strengths, team_features,
                            intercept, home_adv, home_adv_neutral, beta_diff,
                            beta_vel, beta_vol, beta_rank_prior, hosts=[],
                            tier_similarity={}, h2h_biases={}, neutral=True
                        )
                        sample_poisson(lam_a)
                        sample_poisson(lam_b)
                        total_matches += 1
                    except Exception:
                        pass
        
        # Mock knockout stage: 16 teams -> 8 matches -> 4 matches -> 2 matches -> 1 match = 15 matches total
        ko_teams = list(teams[:16])
        while len(ko_teams) > 1:
            next_round = []
            for i in range(0, len(ko_teams), 2):
                if i+1 < len(ko_teams):
                    try:
                        lam_a, lam_b = get_match_lambdas(
                            ko_teams[i], ko_teams[i+1], team_strengths, team_features,
                            intercept, home_adv, home_adv_neutral, beta_diff,
                            beta_vel, beta_vol, beta_rank_prior, hosts=[],
                            tier_similarity={}, h2h_biases={}, neutral=True
                        )
                        goals_a = sample_poisson(lam_a)
                        goals_b = sample_poisson(lam_b)
                        total_matches += 1
                        # Decider
                        if goals_a >= goals_b:
                            next_round.append(ko_teams[i])
                        else:
                            next_round.append(ko_teams[i+1])
                    except Exception:
                        next_round.append(ko_teams[i])
                else:
                    next_round.append(ko_teams[i])
            ko_teams = next_round
            
    dur = time.perf_counter() - t0
    print(f"Simulated {total_matches} matches across {num_runs} tournaments in {dur:.4f} seconds.")
    print(f"Throughput: {total_matches / dur:.2f} simulated matches / second")
    print(f"Average time per tournament (1,000 matches equivalents): {dur * 1000 / num_runs:.2f} ms")

if __name__ == "__main__":
    db_success = profile_db_and_prediction()
    if db_success:
        profile_simulation()
