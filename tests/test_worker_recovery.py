from src.workers import simulation_worker


class Message:
    def topic(self): return "tasks"
    def partition(self): return 0
    def offset(self): return 7


class Redis:
    def __init__(self, attempts): self.attempts = attempts; self.values = {}
    def incr(self, _key): return self.attempts
    def expire(self, *_args): pass
    def set(self, key, value, **_kwargs): self.values[key] = value


class Consumer:
    def __init__(self): self.seeked = False; self.committed = False
    def seek(self, _partition): self.seeked = True
    def commit(self, **_kwargs): self.committed = True


def test_transient_failure_retries_without_committing(monkeypatch):
    consumer, redis = Consumer(), Redis(1)
    monkeypatch.setattr(simulation_worker.time, "sleep", lambda _seconds: None)

    simulation_worker.recover_or_fail(consumer, redis, Message(), "job")

    assert redis.values["task:job:status"] == "RETRYING"
    assert consumer.seeked and not consumer.committed


def test_poison_message_fails_after_three_attempts(monkeypatch):
    consumer, redis = Consumer(), Redis(3)
    monkeypatch.setattr(simulation_worker.time, "sleep", lambda _seconds: None)

    simulation_worker.recover_or_fail(consumer, redis, Message(), "job")

    assert redis.values["task:job:status"] == "ERROR"
    assert consumer.committed and not consumer.seeked
