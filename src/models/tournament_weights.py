import re

TOURNAMENT_WEIGHT_MAP = {
    "FIFA World Cup": 1.0,
    "FIFA World Cup qualification": 0.6,
    "Confederations Cup": 0.85,
    "Copa América": 0.8,
    "UEFA Euro": 0.8,
    "UEFA Euro qualification": 0.6,
    "African Cup of Nations": 0.75,
    "AFC Asian Cup": 0.75,
    "AFC Asian Cup qualification": 0.55,
    "Gold Cup": 0.7,
    "CONCACAF Nations League": 0.6,
    "UEFA Nations League": 0.65,
    "Arab Cup": 0.4,
    "Kirin Cup": 0.3,
    "Friendly": 0.2,
}

_PATTERN_WEIGHTS = [
    (re.compile(r"FIFA World Cup$", re.IGNORECASE), 1.0),
    (re.compile(r"FIFA World Cup qualification", re.IGNORECASE), 0.6),
    (re.compile(r"Confederations Cup", re.IGNORECASE), 0.85),
    (re.compile(r"Copa Am[eé]rica", re.IGNORECASE), 0.8),
    (re.compile(r"UEFA Euro qualification", re.IGNORECASE), 0.6),
    (re.compile(r"UEFA Euro$", re.IGNORECASE), 0.8),
    (re.compile(r"African Cup of Nations", re.IGNORECASE), 0.75),
    (re.compile(r"Africa Cup of Nations", re.IGNORECASE), 0.75),
    (re.compile(r"AFC Asian Cup qualification", re.IGNORECASE), 0.55),
    (re.compile(r"AFC Asian Cup", re.IGNORECASE), 0.75),
    (re.compile(r"Gold Cup", re.IGNORECASE), 0.7),
    (re.compile(r"CONCACAF Nations League", re.IGNORECASE), 0.6),
    (re.compile(r"UEFA Nations League", re.IGNORECASE), 0.65),
    (re.compile(r"Nations League", re.IGNORECASE), 0.6),
    (re.compile(r"qualification", re.IGNORECASE), 0.55),
    (re.compile(r"Friendly", re.IGNORECASE), 0.2),
]

def get_tournament_weight(tournament_name):
    if not tournament_name:
        return 0.3
    exact = TOURNAMENT_WEIGHT_MAP.get(tournament_name.strip())
    if exact is not None:
        return exact
    for pattern, weight in _PATTERN_WEIGHTS:
        if pattern.search(tournament_name):
            return weight
    return 0.3

def compute_weighted_form(conn, team_name, year=None, window_matches=10):
    from src.models.inference import get_standard_team_name
    std_name = get_standard_team_name(team_name)
    if year is not None:
        query = """
            SELECT
                tournament,
                CASE WHEN TRIM(home_team) = TRIM(%s) THEN
                    CASE WHEN home_score > away_score THEN 3 WHEN home_score = away_score THEN 1 ELSE 0 END
                ELSE
                    CASE WHEN away_score > home_score THEN 3 WHEN away_score = home_score THEN 1 ELSE 0 END
                END as points
            FROM fct_underdog_feature_mart
            WHERE (TRIM(home_team) = TRIM(%s) OR TRIM(away_team) = TRIM(%s))
              AND match_date < MAKE_DATE(%s, 1, 1)
            ORDER BY match_date DESC
            LIMIT %s
        """
        params = (std_name, std_name, std_name, int(year), window_matches)
    else:
        query = """
            SELECT
                tournament,
                CASE WHEN TRIM(home_team) = TRIM(%s) THEN
                    CASE WHEN home_score > away_score THEN 3 WHEN home_score = away_score THEN 1 ELSE 0 END
                ELSE
                    CASE WHEN away_score > home_score THEN 3 WHEN away_score = home_score THEN 1 ELSE 0 END
                END as points
            FROM fct_underdog_feature_mart
            WHERE (TRIM(home_team) = TRIM(%s) OR TRIM(away_team) = TRIM(%s))
            ORDER BY match_date DESC
            LIMIT %s
        """
        params = (std_name, std_name, std_name, window_matches)
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    if not rows:
        return 1.0
    weighted_sum = 0.0
    weight_sum = 0.0
    for row in rows:
        tournament = row[0] if row[0] else ""
        points = float(row[1]) if row[1] is not None else 0.0
        tw = get_tournament_weight(tournament)
        weighted_sum += points * tw
        weight_sum += tw
    if weight_sum > 0:
        return weighted_sum / weight_sum
    return 1.0
