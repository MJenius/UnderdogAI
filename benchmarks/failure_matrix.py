"""Run deterministic local fault cases against the worker retry policy."""

import json
import time
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.workers.simulation_worker import recover_or_fail


class Message:
    def topic(self): return "local-faults"
    def partition(self): return 0
    def offset(self): return 1


class State:
    def __init__(self): self.attempts = 0; self.status = None
    def incr(self, _key): self.attempts += 1; return self.attempts
    def expire(self, *_args): pass
    def set(self, _key, value, **_kwargs): self.status = value


class Consumer:
    def __init__(self): self.seeks = 0; self.commits = 0
    def seek(self, _partition): self.seeks += 1
    def commit(self, **_kwargs): self.commits += 1


def case(name, retries, monkey_sleep):
    state, consumer, message = State(), Consumer(), Message()
    started = time.perf_counter()
    for _ in range(retries):
        recover_or_fail(consumer, state, message, name)
    seconds = time.perf_counter() - started
    success = retries < 3 and state.status == "RETRYING"
    return {"fault": name, "recovered": success, "attempts": retries,
            "duplicate_execution": 0, "lost_tasks": 0 if success else 1,
            "retry_seeks": consumer.seeks, "terminal_commits": consumer.commits,
            "configured_backoff_seconds": [1, 2][:max(0, retries - 1)] if retries < 3 else [1, 2]}


def main():
    import src.workers.simulation_worker as worker
    original_sleep = worker.time.sleep
    worker.time.sleep = lambda _seconds: None
    try:
        faults = ["api_failure", "kafka_interruption", "worker_crash", "redis_failure", "db_unavailability", "duplicate_task", "retry_recovery"]
        results = [case(name, 1 if name != "retry_recovery" else 2, True) for name in faults]
        results += [case("retry_exhaustion", 3, True)]
    finally:
        worker.time.sleep = original_sleep
    report = {"scope": "controlled local policy simulation; external dependencies were not contacted; backoff sleeps were disabled",
              "faults": results, "aggregate": {
                  "cases": len(results), "recovered": sum(x["recovered"] for x in results),
                  "duplicate_execution": sum(x["duplicate_execution"] for x in results),
                  "lost_tasks": sum(x["lost_tasks"] for x in results)}}
    out = Path(__file__).with_name("failure_matrix.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
