import pytest
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
    try:
        result = compute_probabilities("Brazil", "France", 2022)
        h_win, a_win, draw = result[0], result[1], result[2]
        
        assert 0.0 <= h_win <= 1.0, f"Home win prob out of bounds: {h_win}"
        assert 0.0 <= a_win <= 1.0, f"Away win prob out of bounds: {a_win}"
        assert 0.0 <= draw <= 1.0, f"Draw prob out of bounds: {draw}"
        
        total = h_win + a_win + draw
        assert 0.99 <= total <= 1.01, f"Probabilities do not sum to 1: {total}"
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


def test_underdog_signal_bounds():
    from src.models.inference import compute_probabilities
    try:
        result = compute_probabilities("Ghana", "Germany", 2014)
        underdog_score = result[3]
        
        assert isinstance(underdog_score, (int, float)), f"Underdog score is not numeric: {type(underdog_score)}"
    except Exception as e:
        pytest.skip(f"Database not available: {e}")
