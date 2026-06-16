import math

def get_shootout_stats(conn, team_name, year=None):
    from src.models.inference import get_standard_team_name
    std_name = get_standard_team_name(team_name)
    if year is not None:
        query = """
            SELECT s.winner, s.first_shooter, s.home_team, s.away_team
            FROM raw_shootouts s
            WHERE (TRIM(s.home_team) = TRIM(%s) OR TRIM(s.away_team) = TRIM(%s))
              AND s.date < MAKE_DATE(%s, 1, 1)
        """
        params = (std_name, std_name, int(year))
    else:
        query = """
            SELECT s.winner, s.first_shooter, s.home_team, s.away_team
            FROM raw_shootouts s
            WHERE (TRIM(s.home_team) = TRIM(%s) OR TRIM(s.away_team) = TRIM(%s))
        """
        params = (std_name, std_name)
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    total = len(rows)
    if total == 0:
        return {"win_rate": 0.5, "first_shooter_adv": 0.5, "total_shootouts": 0}
    wins = 0
    times_first_shooter = 0
    first_shooter_wins = 0
    for row in rows:
        winner = row[0].strip() if row[0] else ""
        first_shooter = row[1].strip() if row[1] else ""
        home = row[2].strip() if row[2] else ""
        away = row[3].strip() if row[3] else ""
        is_team_home = (get_standard_team_name(home) == std_name)
        is_team_away = (get_standard_team_name(away) == std_name)
        team_won = (get_standard_team_name(winner) == std_name)
        team_shot_first = (get_standard_team_name(first_shooter) == std_name)
        if team_won:
            wins += 1
        if team_shot_first:
            times_first_shooter += 1
            if team_won:
                first_shooter_wins += 1
    win_rate = wins / total if total > 0 else 0.5
    first_adv = first_shooter_wins / times_first_shooter if times_first_shooter > 0 else 0.5
    return {"win_rate": win_rate, "first_shooter_adv": first_adv, "total_shootouts": total}

def get_shootout_draw_modifier(conn, team_a, team_b, year=None):
    stats_a = get_shootout_stats(conn, team_a, year)
    stats_b = get_shootout_stats(conn, team_b, year)
    if stats_a["total_shootouts"] == 0 and stats_b["total_shootouts"] == 0:
        return 0.0
    experience_weight_a = min(stats_a["total_shootouts"] / 10.0, 1.0)
    experience_weight_b = min(stats_b["total_shootouts"] / 10.0, 1.0)
    effective_a = 0.5 + (stats_a["win_rate"] - 0.5) * experience_weight_a
    effective_b = 0.5 + (stats_b["win_rate"] - 0.5) * experience_weight_b
    if (effective_a + effective_b) == 0:
        return 0.0
    modifier = 0.10 * (effective_a - effective_b)
    return max(min(modifier, 0.15), -0.15)

def precompute_shootout_stats(conn, teams, year=None):
    stats = {}
    for team in teams:
        stats[team] = get_shootout_stats(conn, team, year)
    return stats
