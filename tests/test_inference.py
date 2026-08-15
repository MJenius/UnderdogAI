import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.inference import get_standard_team_name, get_tier_from_rank


def test_team_name_cleaning_usa():
    assert get_standard_team_name("USA") == "United States"


def test_team_name_cleaning_iran():
    assert get_standard_team_name("IR Iran") == "Iran"


def test_team_name_cleaning_korea():
    assert get_standard_team_name("Korea Republic") == "South Korea"


def test_team_name_cleaning_turkey():
    assert get_standard_team_name("Türkiye") == "Turkey"


def test_team_name_cleaning_identity():
    assert get_standard_team_name("England") == "England"


def test_tier_from_rank_elite():
    tier = get_tier_from_rank(1.0)
    assert tier == "elite"


def test_tier_from_rank_established():
    tier = get_tier_from_rank(20.0)
    assert tier == "established"


def test_tier_from_rank_rising():
    tier = get_tier_from_rank(50.0)
    assert tier == "rising"


def test_tier_from_rank_emerging():
    tier = get_tier_from_rank(100.0)
    assert tier == "emerging"


def test_probability_bounds():
    from src.models.inference import compute_probabilities
    result = compute_probabilities("Brazil", "France", **_in_memory_context())
    h_win, a_win, draw = result[0], result[1], result[2]

    assert 0.0 <= h_win <= 1.0
    assert 0.0 <= a_win <= 1.0
    assert 0.0 <= draw <= 1.0
    assert 0.99 <= h_win + a_win + draw <= 1.01


def test_underdog_signal_bounds():
    from src.models.inference import compute_probabilities
    result = compute_probabilities("Brazil", "France", **_in_memory_context())

    assert isinstance(result[3], (int, float))


def _in_memory_context():
    features = {
        "Brazil": {"rank": 1.0, "vel": 2.0, "vol": 0.1, "underdog_score": 0.2, "conf": "CONMEBOL"},
        "France": {"rank": 4.0, "vel": 1.8, "vol": 0.2, "underdog_score": 0.1, "conf": "UEFA"},
    }
    tiers = {
        "Brazil": {"elite": {"vel": 2.0, "gm": 0.5}},
        "France": {"elite": {"vel": 1.8, "gm": 0.4}},
    }
    shootouts = {
        team: {"win_rate": 0.5, "first_shooter_adv": 0.5, "total_shootouts": 0}
        for team in features
    }
    return {
        "team_features": features,
        "h2h_biases": {("Brazil", "France"): (0.0, False)},
        "tier_similarity": tiers,
        "shootout_stats": shootouts,
        "model_params": (0.0, 0.1, 0.0, 0.0, 0.1, -0.1, -0.01, {}),
    }
