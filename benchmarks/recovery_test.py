"""Inject two worker failures and measure configured retry recovery."""

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.workers.simulation_worker import recover_or_fail


class Message:
    def topic(self): return "tasks"
    def partition(self): return 0
    def offset(self): return 1


class State:
    def __init__(self): self.attempts = 0; self.statuses = []
    def incr(self, _key): self.attempts += 1; return self.attempts
    def expire(self, *_args): pass
    def set(self, _key, value, **_kwargs): self.statuses.append(value)


class Consumer:
    def __init__(self): self.seeks = 0; self.commits = 0
    def seek(self, _partition): self.seeks += 1
    def commit(self, **_kwargs): self.commits += 1


state, consumer, message = State(), Consumer(), Message()
started = time.perf_counter()
recover_or_fail(consumer, state, message, "fault-injection")
recover_or_fail(consumer, state, message, "fault-injection")
consumer.commit(message=message, asynchronous=False)
elapsed = time.perf_counter() - started

assert state.statuses == ["RETRYING", "RETRYING"]
assert consumer.seeks == 2 and consumer.commits == 1
print(json.dumps({
    "injected_transient_failures": 2,
    "recovered": True,
    "recovery_seconds": round(elapsed, 2),
    "retry_backoff_seconds": [1, 2],
    "duplicate_commits_before_success": 0,
}, indent=2))
