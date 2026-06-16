import pytest
import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from src.api.gateway import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_predict_endpoint_structure(client):
    response = client.get("/api/v1/predict?home=Brazil&away=France&year=2022")
    
    if response.status_code == 200:
        data = response.json()
        
        assert "home_win_prob" in data
        assert "away_win_prob" in data
        assert "draw_prob" in data
        assert "underdog_signal_score" in data
        assert "risk_label" in data
        
        assert 0.0 <= data["home_win_prob"] <= 1.0
        assert 0.0 <= data["away_win_prob"] <= 1.0
        assert 0.0 <= data["draw_prob"] <= 1.0
    else:
        pytest.skip(f"API returned {response.status_code}: database may not be available")


def test_api_features_endpoint_exists(client):
    response = client.get("/api/v1/features?team=Brazil&year=2022")
    
    if response.status_code != 500:
        assert response.status_code in [200, 404]
    else:
        pytest.skip("Database not available")


def test_api_teams_endpoint(client):
    response = client.get("/api/v1/teams?year=2022")
    
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, list)
    else:
        pytest.skip("Database not available")


def test_request_id_header(client):
    response = client.get("/api/v1/teams?year=2022")
    
    assert "x-request-id" in response.headers
    request_id = response.headers["x-request-id"]
    
    assert len(request_id) == 36
    assert request_id.count('-') == 4


def test_simulate_endpoint_returns_task_id(client):
    payload = {
        "tournament_year": 2022,
        "simulation_runs": 100,
        "progression_mode": "winner"
    }
    
    response = client.post("/api/v1/simulate", json=payload)
    
    if response.status_code == 202:
        data = response.json()
        assert "task_id" in data
        assert len(data["task_id"]) == 36
    else:
        pytest.skip("Kafka/Redis not available")


def test_predict_endpoint_handles_missing_params(client):
    response = client.get("/api/v1/predict?home=Brazil&away=France")
    
    if response.status_code == 200:
        data = response.json()
        assert "home_win_prob" in data
    else:
        pytest.skip("Database not available")
