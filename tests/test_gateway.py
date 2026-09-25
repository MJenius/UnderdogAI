import os
import time
import uuid

os.environ["GRPC_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient

from src.api import gateway


PREDICTION = (0.45, 0.30, 0.25, 0.61, "medium", "test", 1.0, 1.0, 0.0)


@pytest.fixture
def client():
    gateway.clear_prediction_cache()
    with TestClient(gateway.app) as test_client:
        yield test_client


def test_predict_is_cached_and_bounded(client, monkeypatch):
    calls = []
    monkeypatch.setattr(gateway.inference, "compute_probabilities", lambda *args: calls.append(args) or PREDICTION)

    first = client.get("/api/v1/predict?home=Brazil&away=France&year=2022")
    second = client.get("/api/v1/predict?home=Brazil&away=France&year=2022")

    assert first.status_code == second.status_code == 200
    assert len(calls) == 1
    assert 0 <= first.json()["home_win_prob"] <= 1


def test_predict_failure_does_not_leak_internal_error(client, monkeypatch):
    monkeypatch.setattr(gateway.inference, "compute_probabilities", lambda *_: 1 / 0)

    response = client.get("/api/v1/predict?home=Brazil&away=France")

    assert response.status_code == 500
    assert response.json() == {"detail": "Prediction failed"}


def test_request_id_is_preserved(client):
    response = client.get("/health/live", headers={"x-request-id": "trace-123"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "trace-123"


def test_simulation_request_validation_and_enqueue(client, monkeypatch):
    events = []
    monkeypatch.setattr(gateway, "enqueue_simulation", lambda task_id, event: events.append((task_id, event)))
    payload = {"tournament_year": 2022, "simulation_runs": 100, "progression_mode": "winner"}

    response = client.post("/api/v1/simulate", json=payload)

    assert response.status_code == 202
    assert uuid.UUID(response.json()["task_id"])
    assert events[0][1]["simulation_runs"] == 100
    assert client.post("/api/v1/simulate", json={**payload, "simulation_runs": 0}).status_code == 422


def test_unknown_simulation_is_404(client, monkeypatch):
    class Redis:
        def get(self, _key):
            return None

    monkeypatch.setattr(gateway, "get_redis_client", Redis)
    response = client.get(f"/api/v1/simulate/status/{uuid.uuid4()}")

    assert response.status_code == 404

    class RetryingRedis:
        def get(self, key):
            if key.endswith(":status"):
                return "RETRYING"
            return "50.0" if key.endswith(":progress") else None

    monkeypatch.setattr(gateway, "get_redis_client", RetryingRedis)
    response = client.get(f"/api/v1/simulate/status/{uuid.uuid4()}")
    assert response.json()["status"] == "RETRYING"


def test_redis_failure_fails_readiness_and_simulation_requests_fast(client, monkeypatch):
    class UnavailableRedis:
        def ping(self): raise ConnectionError("redis unavailable")
        def pipeline(self, **_kwargs): raise ConnectionError("redis unavailable")

    monkeypatch.setattr(gateway, "get_redis_client", UnavailableRedis)
    monkeypatch.setattr(gateway.inference, "get_db_connection", lambda: HealthyConnection())
    monkeypatch.setattr(gateway, "get_kafka_producer", lambda: HealthyKafka())
    started = time.monotonic()
    ready = client.get("/health/ready")
    submitted = client.post("/api/v1/simulate", json={
        "tournament_year": 2022, "simulation_runs": 10, "progression_mode": "winner"
    })

    assert ready.status_code == 503
    assert ready.json()["checks"]["redis"] is False
    assert submitted.status_code == 503
    assert submitted.json()["detail"] == "Simulation queue is temporarily unavailable"
    assert time.monotonic() - started < 1


def test_redis_status_request_fails_explicitly_and_readiness_recovers(client, monkeypatch):
    class ToggleRedis:
        available = False
        def ping(self):
            if not self.available: raise ConnectionError("redis unavailable")
            return True
        def get(self, _key):
            if not self.available: raise ConnectionError("redis unavailable")
            return "PENDING" if _key.endswith(":status") else None

    redis_client = ToggleRedis()
    monkeypatch.setattr(gateway, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(gateway.inference, "get_db_connection", lambda: HealthyConnection())
    monkeypatch.setattr(gateway, "get_kafka_producer", lambda: HealthyKafka())
    task_id = uuid.uuid4()

    assert client.get(f"/api/v1/simulate/status/{task_id}").status_code == 503
    assert client.get("/health/ready").status_code == 503
    redis_client.available = True
    assert client.get(f"/api/v1/simulate/status/{task_id}").status_code == 200
    assert client.get("/health/ready").status_code == 200


class HealthyConnection:
    def cursor(self): return self
    def execute(self, *_args): pass
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self, *_args): pass


class HealthyKafka:
    def list_topics(self, **_kwargs): return {}


def test_metrics_expose_requests_and_cache(client, monkeypatch):
    monkeypatch.setattr(gateway.inference, "compute_probabilities", lambda *_: PREDICTION)
    client.get("/api/v1/predict?home=Brazil&away=France")
    client.get("/api/v1/predict?home=Brazil&away=France")

    metrics = client.get("/metrics").text

    assert "underdog_http_requests_total" in metrics
    assert "underdog_http_request_duration_seconds_bucket" in metrics
    assert "underdog_prediction_cache_hits_total 1" in metrics


def test_missing_prediction_parameters_are_rejected(client):
    assert client.get("/api/v1/predict?home=Brazil").status_code == 422
    assert client.get("/api/v1/predict?home=%20%20&away=France").status_code == 422
