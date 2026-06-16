import os
import glob
import csv
import math
import psycopg2

def get_latest_model_params():
    files = glob.glob(os.path.join("mlruns", "**", "model_summary.csv"), recursive=True)
    if not files:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.01, {}
    latest_file = max(files, key=os.path.getmtime)
    intercept = 0.0
    home_adv = 0.0
    home_adv_neutral = 0.0
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
            elif name == "home_adv_neutral":
                home_adv_neutral = val
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
    return intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior, team_strengths

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

def poisson_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam**k * math.exp(-lam)) / math.factorial(k)

def compute_probabilities(home_team, away_team, year=None, conn=None, h2h_biases=None, tier_similarity=None, team_features=None, model_params=None):
    if model_params is None:
        intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior, team_strengths = get_latest_model_params()
    else:
        intercept, home_adv, home_adv_neutral, beta_diff, beta_vel, beta_vol, beta_rank_prior, team_strengths = model_params

    close_conn = False
    if conn is None and (team_features is None or h2h_biases is None or tier_similarity is None):
        conn = get_db_connection()
        close_conn = True

    try:
        if team_features is not None:
            home_feats = team_features.get(home_team)
            if home_feats is None:
                home_feats = {"rank": 100.0, "vel": 1.0, "vol": 0.0, "underdog_score": 0.0, "conf": None}
            away_feats = team_features.get(away_team)
            if away_feats is None:
                away_feats = {"rank": 100.0, "vel": 1.0, "vol": 0.0, "underdog_score": 0.0, "conf": None}
        else:
            home_feats = get_team_features(conn, home_team, year)
            away_feats = get_team_features(conn, away_team, year)

        h_rank = home_feats["rank"]
        a_rank = away_feats["rank"]
        h_tier = get_tier_from_rank(h_rank)
        a_tier = get_tier_from_rank(a_rank)

        if tier_similarity is not None:
            home_tier_vel = tier_similarity.get(home_team, {}).get(a_tier, {}).get("vel", 1.0)
            home_tier_gm = tier_similarity.get(home_team, {}).get(a_tier, {}).get("gm", 0.0)
            away_tier_vel = tier_similarity.get(away_team, {}).get(h_tier, {}).get("vel", 1.0)
            away_tier_gm = tier_similarity.get(away_team, {}).get(h_tier, {}).get("gm", 0.0)
        else:
            home_tier_vel, home_tier_gm = get_tier_similarity_features(conn, home_team, a_tier, year)
            away_tier_vel, away_tier_gm = get_tier_similarity_features(conn, away_team, h_tier, year)

        if h2h_biases is not None:
            h2h_val = h2h_biases.get((home_team, away_team), 0.0)
        else:
            h2h_val = get_h2h_bias(conn, home_team, away_team, year)

    finally:
        if close_conn:
            conn.close()

    h_std = get_standard_team_name(home_team)
    h_fifa = get_fifa_rankings_name(h_std)
    h_est = team_strengths.get(h_std, team_strengths.get(h_fifa, beta_rank_prior * h_rank))
    h_str = h_est + (-0.008 * h_rank) + 0.5 * h2h_val

    a_std = get_standard_team_name(away_team)
    a_fifa = get_fifa_rankings_name(a_std)
    a_est = team_strengths.get(a_std, team_strengths.get(a_fifa, beta_rank_prior * a_rank))
    a_str = a_est + (-0.008 * a_rank) - 0.5 * h2h_val

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
        conn_local = conn if conn is not None else get_db_connection()
        close_local = conn is None
        try:
            with conn_local.cursor() as cur:
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
            if close_local:
                conn_local.close()

    host_map = {
        1970: {"Mexico"},
        2018: {"Russia"},
        2022: {"Qatar"},
        2026: {"USA", "Canada", "Mexico"}
    }
    hosts = host_map.get(year, set()) if year is not None else set()
    home_adv_applied_to_home = (not neutral) or (get_fifa_rankings_name(home_team) in hosts)
    home_adv_applied_to_away = (get_fifa_rankings_name(away_team) in hosts)

    h_adv_val = home_adv if home_adv_applied_to_home else (home_adv_neutral if neutral else 0.0)
    a_adv_val = home_adv if home_adv_applied_to_away else (home_adv_neutral if neutral else 0.0)

    rank_diff = h_rank - a_rank
    lambda_home = math.exp(
        intercept + h_adv_val + h_str - a_str
        + beta_diff * rank_diff
        + beta_vel * home_tier_vel
        + beta_vol * home_tier_gm
    )
    lambda_away = math.exp(
        intercept + a_adv_val + a_str - h_str
        - beta_diff * rank_diff
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

def fixtures_endpoint_batched(conn, year):
    query = """
        SELECT DISTINCT match_date, home_team, away_team
        FROM fct_underdog_feature_mart
        WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = %s
        ORDER BY match_date ASC
    """
    with conn.cursor() as cur:
        cur.execute(query, (year,))
        rows = cur.fetchall()
    
    fixtures = []
    if not rows:
        return fixtures
        
    teams = sorted({r[1] for r in rows} | {r[2] for r in rows})
    
    h2h_biases = precompute_h2h_biases(conn, teams, year)
    tier_similarity = precompute_tier_similarity(conn, teams, year)
    
    team_features = {}
    for t in teams:
        team_features[t] = get_team_features(conn, t, year)
        
    model_params = get_latest_model_params()
    
    for row in rows:
        match_date = str(row[0])
        home = row[1]
        away = row[2]
        h_win, a_win, draw, u_score, risk, narrative, h_form, a_form, h2h = compute_probabilities(
            home, away, year, conn, h2h_biases, tier_similarity, team_features, model_params
        )
        h_feats = team_features[home]
        a_feats = team_features[away]
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
    fixtures.sort(key=lambda x: x["upset_probability"], reverse=True)
    return fixtures
