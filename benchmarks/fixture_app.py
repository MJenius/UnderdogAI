"""Deterministic inference fixture for repeatable gateway load tests."""

import os
import time

from src.api import gateway


def controlled_inference(*_args, **_kwargs):
    time.sleep(float(os.getenv("BENCHMARK_INFERENCE_DELAY", "0.02")))
    return (0.45, 0.30, 0.25, 0.61, "medium", "benchmark", 1.0, 1.0, 0.0)


gateway.inference.compute_probabilities = controlled_inference
app = gateway.app
