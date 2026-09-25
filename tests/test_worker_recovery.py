from src.workers import simulation_worker


class Message:
    def topic(self): return "tasks"
    def partition(self): return 0
    def offset(self): return 7


class Redis:
    def __init__(self, attempts=0): self.attempts = attempts; self.values = {}; self.options = {}
    def incr(self, key):
        self.attempts += 1
        self.values[key] = self.attempts
        return self.attempts
    def expire(self, *_args): pass
    def set(self, key, value, **_kwargs):
        self.values[key] = value
        self.options[key] = _kwargs
        if key.endswith(":attempts"):
            self.attempts = value


class Consumer:
    def __init__(self): self.seeked = False; self.committed = False
    def seek(self, _partition): self.seeked = True
    def commit(self, **_kwargs): self.committed = True


def test_short_database_interruption_retries_without_committing(monkeypatch):
    consumer, redis = Consumer(), Redis(1)
    monkeypatch.setattr(simulation_worker.time, "sleep", lambda _seconds: None)

    simulation_worker.recover_or_fail(consumer, redis, Message(), "job")

    assert redis.values["task:job:status"] == "RETRYING"
    assert consumer.seeked and not consumer.committed


def test_exhausted_retries_remain_recoverable_and_uncommitted(monkeypatch):
    consumer, redis = Consumer(), Redis(2)
    monkeypatch.setattr(simulation_worker.time, "sleep", lambda _seconds: None)

    attempts = simulation_worker.recover_or_fail(consumer, redis, Message(), "job")

    assert attempts == 3
    assert redis.values["task:job:status"] == "RECOVERABLE"
    assert redis.options["task:job:status"] == {}
    assert redis.values["task:job:attempts"] == 0
    assert consumer.seeked and not consumer.committed


def test_prolonged_outage_cycles_back_to_retrying_without_losing_offset(monkeypatch):
    consumer, redis = Consumer(), Redis()
    monkeypatch.setattr(simulation_worker.time, "sleep", lambda _seconds: None)

    for _ in range(7):
        simulation_worker.recover_or_fail(consumer, redis, Message(), "job")

    assert redis.values["task:job:status"] in {"RETRYING", "RECOVERABLE"}
    assert consumer.seeked and not consumer.committed


def test_redis_failure_still_seeks_uncommitted_message(monkeypatch):
    class UnavailableRedis:
        def incr(self, _key): raise ConnectionError("redis unavailable")

    consumer = Consumer()
    monkeypatch.setattr(simulation_worker.time, "sleep", lambda _seconds: None)

    assert simulation_worker.recover_or_fail(consumer, UnavailableRedis(), Message(), "job") is None
    assert consumer.seeked and not consumer.committed
