import os
import sys
import json
import math
import random
import psycopg2
import redis
from confluent_kafka import Consumer, KafkaError
import src.models.inference as inference
import src.models.shootout_resilience as shootout_mod

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
        std_name = inference.get_standard_team_name(team_name)
        fifa_name = inference.get_fifa_rankings_name(std_name)
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

def get_match_lambdas(team_a, team_b, team_strengths, team_features, intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior, hosts, tier_similarity, h2h_biases, neutral=True):
    a_std = inference.get_standard_team_name(team_a)
    a_fifa = inference.get_fifa_rankings_name(a_std)
    a_feat = team_features.get(a_std, {"rank": 100.0, "vel": 1.0, "vol": 0.0, "conf": None})
    
    b_std = inference.get_standard_team_name(team_b)
    b_fifa = inference.get_fifa_rankings_name(b_std)
    b_feat = team_features.get(b_std, {"rank": 100.0, "vel": 1.0, "vol": 0.0, "conf": None})
    
    h2h_entry = h2h_biases.get((a_std, b_std), (0.0, False))
    if isinstance(h2h_entry, tuple):
        h2h_val = h2h_entry[0]
    else:
        h2h_val = h2h_entry
    
    a_est = team_strengths.get(a_std, team_strengths.get(a_fifa, beta_rank_prior * a_feat["rank"]))
    a_str = a_est + 0.5 * h2h_val
    
    b_est = team_strengths.get(b_std, team_strengths.get(b_fifa, beta_rank_prior * b_feat["rank"]))
    b_str = b_est - 0.5 * h2h_val
    
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
    
    a_adv_applied = a_fifa in hosts
    b_adv_applied = b_fifa in hosts
    
    a_adv_val = home_adv if a_adv_applied else (home_adv_neutral if neutral else 0.0)
    b_adv_val = home_adv if b_adv_applied else (home_adv_neutral if neutral else 0.0)
    
    b_tier = inference.get_tier_from_rank(b_feat["rank"])
    a_tier = inference.get_tier_from_rank(a_feat["rank"])
    
    a_tier_vel = tier_similarity.get(a_std, {}).get(b_tier, {}).get("vel", 1.0)
    a_tier_gm = tier_similarity.get(a_std, {}).get(b_tier, {}).get("gm", 0.0)
    b_tier_vel = tier_similarity.get(b_std, {}).get(a_tier, {}).get("vel", 1.0)
    b_tier_gm = tier_similarity.get(b_std, {}).get(a_tier, {}).get("gm", 0.0)
    
    lambda_a = math.exp(
        intercept + a_adv_val + a_str - b_str
        + beta_vel * a_tier_vel
        + beta_vol * a_tier_gm
    )
    lambda_b = math.exp(
        intercept + b_adv_val + b_str - a_str
        + beta_vel * b_tier_vel
        + beta_vol * b_tier_gm
    )
    return lambda_a, lambda_b

def simulate_match_scores(team_a, team_b, team_strengths, team_features, intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior, hosts, tier_similarity, h2h_biases, neutral=True):
    lambda_a, lambda_b = get_match_lambdas(
        team_a, team_b, team_strengths, team_features,
        intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
        hosts, tier_similarity, h2h_biases, neutral
    )
    goals_a = sample_poisson(lambda_a)
    goals_b = sample_poisson(lambda_b)
    return goals_a, goals_b

def simulate_match(team_a, team_b, team_strengths, team_features, intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior, hosts, tier_similarity, h2h_biases, shootout_stats=None, neutral=True):
    goals_a, goals_b = simulate_match_scores(
        team_a, team_b, team_strengths, team_features,
        intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
        hosts, tier_similarity, h2h_biases, neutral
    )
    if goals_a > goals_b:
        return team_a
    elif goals_b > goals_a:
        return team_b
    else:
        lambda_a, lambda_b = get_match_lambdas(
            team_a, team_b, team_strengths, team_features,
            intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
            hosts, tier_similarity, h2h_biases, neutral
        )
        p_a_win = lambda_a / (lambda_a + lambda_b) if (lambda_a + lambda_b) > 0 else 0.5
        if shootout_stats is not None:
            a_std = inference.get_standard_team_name(team_a)
            b_std = inference.get_standard_team_name(team_b)
            a_sr = shootout_stats.get(a_std, {"win_rate": 0.5})
            b_sr = shootout_stats.get(b_std, {"win_rate": 0.5})
            sr_diff = (a_sr["win_rate"] - b_sr["win_rate"]) * 0.15
            p_a_win = min(max(p_a_win + sr_diff, 0.05), 0.95)
        return team_a if random.random() < p_a_win else team_b

def reconstruct_groups(teams, conn, year):
    query = """
        SELECT home_team, away_team
        FROM fct_underdog_feature_mart
        WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = %s
        ORDER BY match_date ASC, match_id ASC
    """
    with conn.cursor() as cur:
        cur.execute(query, (year,))
        rows = cur.fetchall()
    if not rows:
        return []
    num_group_matches = int(len(teams) * 1.5)
    group_matches = rows[:num_group_matches]
    adj = {}
    for h, a in group_matches:
        h_std = inference.get_standard_team_name(h)
        a_std = inference.get_standard_team_name(a)
        if h_std not in adj:
            adj[h_std] = set()
        if a_std not in adj:
            adj[a_std] = set()
        adj[h_std].add(a_std)
        adj[a_std].add(h_std)
    visited = set()
    groups = []
    for team in adj:
        if team not in visited and team in teams:
            comp = set()
            q = [team]
            visited.add(team)
            while q:
                curr = q.pop(0)
                comp.add(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited and neighbor in teams:
                        visited.add(neighbor)
                        q.append(neighbor)
            groups.append(sorted(list(comp)))
    return groups

def simulate_group_stage(groups, team_strengths, team_features, intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior, hosts, tier_similarity, h2h_biases):
    winners = []
    runners_up = []
    for group_teams in groups:
        standings = {t: {"pts": 0, "gd": 0} for t in group_teams}
        for i in range(len(group_teams)):
            for j in range(i + 1, len(group_teams)):
                goals_a, goals_b = simulate_match_scores(
                    group_teams[i], group_teams[j],
                    team_strengths, team_features,
                    intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
                    hosts, tier_similarity, h2h_biases, neutral=True
                )
                standings[group_teams[i]]["gd"] += goals_a - goals_b
                standings[group_teams[j]]["gd"] += goals_b - goals_a
                if goals_a > goals_b:
                    standings[group_teams[i]]["pts"] += 3
                elif goals_b > goals_a:
                    standings[group_teams[j]]["pts"] += 3
                else:
                    standings[group_teams[i]]["pts"] += 1
                    standings[group_teams[j]]["pts"] += 1
        ranked = sorted(group_teams, key=lambda t: (standings[t]["pts"], standings[t]["gd"], t), reverse=True)
        winners.append(ranked[0])
        runners_up.append(ranked[1])
    return winners, runners_up

def simulate_48_team_bracket(winners_g, runners_g, team_strengths, team_features, intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior, hosts, tier_similarity, h2h_biases, shootout_stats, progression_mode):
    milestone_reached = set()
    qualifiers = list(winners_g) + list(runners_g)
    if progression_mode == "reach_knockouts":
        for t in qualifiers:
            milestone_reached.add(t)
    r32_winners = []
    r32_pairings = []
    for i in range(0, len(winners_g), 2):
        if i + 1 < len(winners_g):
            r32_pairings.append((winners_g[i], runners_g[i + 1]))
            r32_pairings.append((winners_g[i + 1], runners_g[i]))
    while len(r32_pairings) < 16:
        remaining_w = [w for w in winners_g if not any(w in p for p in r32_pairings)]
        remaining_r = [r for r in runners_g if not any(r in p for p in r32_pairings)]
        if remaining_w and remaining_r:
            r32_pairings.append((remaining_w[0], remaining_r[0]))
        else:
            break
    for t_a, t_b in r32_pairings:
        winner = simulate_match(
            t_a, t_b, team_strengths, team_features,
            intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
            hosts, tier_similarity, h2h_biases, shootout_stats, neutral=True
        )
        r32_winners.append(winner)
    if progression_mode == "reach_round_of_16":
        for t in r32_winners:
            milestone_reached.add(t)
    r16_winners = []
    for i in range(0, len(r32_winners) - 1, 2):
        winner = simulate_match(
            r32_winners[i], r32_winners[i + 1], team_strengths, team_features,
            intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
            hosts, tier_similarity, h2h_biases, shootout_stats, neutral=True
        )
        r16_winners.append(winner)
    if progression_mode == "reach_quarterfinals":
        for t in r16_winners:
            milestone_reached.add(t)
    qf_winners = []
    for i in range(0, len(r16_winners) - 1, 2):
        winner = simulate_match(
            r16_winners[i], r16_winners[i + 1], team_strengths, team_features,
            intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
            hosts, tier_similarity, h2h_biases, shootout_stats, neutral=True
        )
        qf_winners.append(winner)
    if progression_mode == "reach_semifinals":
        for t in qf_winners:
            milestone_reached.add(t)
    sf_winners = []
    for i in range(0, len(qf_winners) - 1, 2):
        winner = simulate_match(
            qf_winners[i], qf_winners[i + 1], team_strengths, team_features,
            intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
            hosts, tier_similarity, h2h_biases, shootout_stats, neutral=True
        )
        sf_winners.append(winner)
    if progression_mode == "reach_finals":
        for t in sf_winners:
            milestone_reached.add(t)
    if len(sf_winners) >= 2:
        champion = simulate_match(
            sf_winners[0], sf_winners[1], team_strengths, team_features,
            intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
            hosts, tier_similarity, h2h_biases, shootout_stats, neutral=True
        )
        if not progression_mode or progression_mode == "winner":
            milestone_reached.add(champion)
    return milestone_reached

def run_tournament_simulation(teams, team_features, team_strengths, intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior, runs, year, r_conn, task_id, progression_mode, tier_similarity, h2h_biases, groups, shootout_stats):
    win_counts = {t: 0 for t in teams}
    if not teams:
        return {}
    host_map = {
        1970: {"Mexico"},
        2018: {"Russia"},
        2022: {"Qatar"},
        2026: {"USA", "Canada", "Mexico"}
    }
    hosts = host_map.get(year, set())
    step_5 = math.ceil(runs * 0.05)
    
    use_group_stage = len(groups) > 0 and all(len(g) == 4 for g in groups)
    is_48_team = len(teams) == 48 or len(groups) == 12
    is_32_team = len(teams) == 32 or len(groups) == 8
    is_16_team = len(teams) == 16 or len(groups) == 4
    
    for i in range(runs):
        milestone_reached = set()
        
        if use_group_stage:
            winners_g, runners_g = simulate_group_stage(
                groups, team_strengths, team_features,
                intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
                hosts, tier_similarity, h2h_biases
            )
            
            if is_48_team:
                milestone_reached = simulate_48_team_bracket(
                    winners_g, runners_g, team_strengths, team_features,
                    intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
                    hosts, tier_similarity, h2h_biases, shootout_stats, progression_mode
                )
            elif is_32_team:
                for w in winners_g:
                    if progression_mode == "reach_knockouts":
                         milestone_reached.add(w)
                for r in runners_g:
                    if progression_mode == "reach_knockouts":
                         milestone_reached.add(r)
                
                r16_winners = []
                pairings = [
                    (winners_g[0], runners_g[1]),
                    (winners_g[2], runners_g[3]),
                    (winners_g[4], runners_g[5]),
                    (winners_g[6], runners_g[7]),
                    (winners_g[1], runners_g[0]),
                    (winners_g[3], runners_g[2]),
                    (winners_g[5], runners_g[4]),
                    (winners_g[7], runners_g[6]),
                ]
                for t_a, t_b in pairings:
                    winner = simulate_match(
                        t_a, t_b, team_strengths, team_features,
                        intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
                        hosts, tier_similarity, h2h_biases, shootout_stats, neutral=True
                    )
                    r16_winners.append(winner)
                    if progression_mode == "reach_quarterfinals":
                        milestone_reached.add(winner)
                        
                qf_winners = []
                qf_pairings = [
                    (r16_winners[0], r16_winners[1]),
                    (r16_winners[2], r16_winners[3]),
                    (r16_winners[4], r16_winners[5]),
                    (r16_winners[6], r16_winners[7]),
                ]
                for t_a, t_b in qf_pairings:
                    winner = simulate_match(
                        t_a, t_b, team_strengths, team_features,
                        intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
                        hosts, tier_similarity, h2h_biases, shootout_stats, neutral=True
                    )
                    qf_winners.append(winner)
                    if progression_mode == "reach_semifinals":
                        milestone_reached.add(winner)
                        
                sf_winners = []
                sf_pairings = [
                    (qf_winners[0], qf_winners[1]),
                    (qf_winners[2], qf_winners[3]),
                ]
                for t_a, t_b in sf_pairings:
                    winner = simulate_match(
                        t_a, t_b, team_strengths, team_features,
                        intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
                        hosts, tier_similarity, h2h_biases, shootout_stats, neutral=True
                    )
                    sf_winners.append(winner)
                    if progression_mode == "reach_finals":
                        milestone_reached.add(winner)
                        
                champion = simulate_match(
                    sf_winners[0], sf_winners[1], team_strengths, team_features,
                    intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
                    hosts, tier_similarity, h2h_biases, shootout_stats, neutral=True
                )
                if not progression_mode or progression_mode == "winner":
                    milestone_reached.add(champion)
                    
            elif is_16_team:
                for w in winners_g:
                    if progression_mode == "reach_knockouts":
                         milestone_reached.add(w)
                for r in runners_g:
                    if progression_mode == "reach_knockouts":
                         milestone_reached.add(r)
                         
                qf_winners = []
                qf_pairings = [
                    (winners_g[0], runners_g[1]),
                    (winners_g[2], runners_g[3]),
                    (winners_g[1], runners_g[0]),
                    (winners_g[3], runners_g[2]),
                ]
                for t_a, t_b in qf_pairings:
                    winner = simulate_match(
                        t_a, t_b, team_strengths, team_features,
                        intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
                        hosts, tier_similarity, h2h_biases, shootout_stats, neutral=True
                    )
                    qf_winners.append(winner)
                    if progression_mode == "reach_quarterfinals" or progression_mode == "reach_semifinals":
                        milestone_reached.add(winner)
                        
                sf_winners = []
                sf_pairings = [
                    (qf_winners[0], qf_winners[1]),
                    (qf_winners[2], qf_winners[3]),
                ]
                for t_a, t_b in sf_pairings:
                    winner = simulate_match(
                        t_a, t_b, team_strengths, team_features,
                        intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
                        hosts, tier_similarity, h2h_biases, shootout_stats, neutral=True
                    )
                    sf_winners.append(winner)
                    if progression_mode == "reach_finals":
                        milestone_reached.add(winner)
                        
                champion = simulate_match(
                    sf_winners[0], sf_winners[1], team_strengths, team_features,
                    intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
                    hosts, tier_similarity, h2h_biases, shootout_stats, neutral=True
                )
                if not progression_mode or progression_mode == "winner":
                    milestone_reached.add(champion)
                    
            else:
                use_group_stage = False
                
        if not use_group_stage:
            active_teams = list(teams)
            random.shuffle(active_teams)
            
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
                            intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior,
                            hosts, tier_similarity, h2h_biases, shootout_stats, neutral=True
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
            r_conn.set(f"task:{task_id}:progress", f"{progress_pct:.1f}", ex=3600)
            
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
            
            conn = inference.get_db_connection()
            teams, team_features = fetch_tournament_teams(conn, year)
            h2h_biases = inference.precompute_h2h_biases(conn, teams, year)
            tier_similarity = inference.precompute_tier_similarity(conn, teams, year)
            groups = reconstruct_groups(teams, conn, year)
            s_stats = shootout_mod.precompute_shootout_stats(conn, teams, year)
            conn.close()
            
            intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior, team_strengths = inference.get_latest_model_params()
            results = run_tournament_simulation(
                teams, team_features, team_strengths,
                intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior, runs, year, r, task_id,
                progression_mode, tier_similarity, h2h_biases, groups, s_stats
            )
            r.set(task_id, json.dumps(results), ex=3600)
            r.set(f"task:{task_id}:status", "COMPLETED", ex=3600)
        except Exception as e:
            try:
                task_id = event["task_id"]
                r.set(f"task:{task_id}:status", "ERROR", ex=3600)
            except Exception:
                pass
            sys.stderr.write(str(e) + "\n")

if __name__ == "__main__":
    main()
