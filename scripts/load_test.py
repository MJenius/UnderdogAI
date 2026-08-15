"""Dependency-free HTTP load test with latency and optional server resource metrics."""

import argparse
import concurrent.futures
import json
import math
import os
import statistics
import threading
import time
import urllib.request


def percentile(values, p):
    return values[max(0, math.ceil(len(values) * p) - 1)]


def process_usage(pid):
    if not pid:
        return None
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class FILETIME(ctypes.Structure):
                _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

            class MEMORY(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD),
                            ("peak_working_set", ctypes.c_size_t),
                            ("working_set", ctypes.c_size_t)] + [
                                (name, ctypes.c_size_t) for name in
                                ("peak_paged", "paged", "peak_nonpaged", "nonpaged",
                                 "pagefile", "peak_pagefile")
                            ]

            kernel = ctypes.windll.kernel32
            process = kernel.OpenProcess(0x0400 | 0x0010, False, pid)
            if not process:
                return None
            created, exited, kernel_time, user_time = FILETIME(), FILETIME(), FILETIME(), FILETIME()
            memory = MEMORY(cb=ctypes.sizeof(MEMORY))
            kernel.GetProcessTimes(process, *(ctypes.byref(v) for v in (created, exited, kernel_time, user_time)))
            ctypes.windll.psapi.GetProcessMemoryInfo(process, ctypes.byref(memory), memory.cb)
            kernel.CloseHandle(process)
            ticks = lambda value: (value.high << 32) + value.low
            return (ticks(kernel_time) + ticks(user_time)) / 10_000_000, memory.working_set / 1_048_576

        with open(f"/proc/{pid}/stat", encoding="utf-8") as stat_file:
            fields = stat_file.read().split()
        with open(f"/proc/{pid}/status", encoding="utf-8") as status_file:
            rss_kb = next(int(line.split()[1]) for line in status_file if line.startswith("VmRSS:"))
        return (int(fields[13]) + int(fields[14])) / os.sysconf("SC_CLK_TCK"), rss_kb / 1024
    except (OSError, StopIteration, ValueError):
        return None


def request_once(url, timeout):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            response.read()
            return (time.perf_counter() - started) * 1000, response.status
    except Exception:
        return (time.perf_counter() - started) * 1000, 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--pid", type=int)
    args = parser.parse_args()

    for _ in range(args.warmup):
        request_once(args.url, args.timeout)

    samples = []
    stop = threading.Event()

    def sample_resources():
        while not stop.wait(0.05):
            usage = process_usage(args.pid)
            if usage:
                samples.append(usage)

    sampler = threading.Thread(target=sample_resources, daemon=True)
    before = process_usage(args.pid)
    sampler.start()
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda _: request_once(args.url, args.timeout), range(args.requests)))
    duration = time.perf_counter() - started
    stop.set()
    sampler.join()
    after = process_usage(args.pid)

    latencies = sorted(latency for latency, _ in results)
    successes = sum(200 <= status < 400 for _, status in results)
    report = {
        "url": args.url,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "successes": successes,
        "failures": args.requests - successes,
        "throughput_rps": round(args.requests / duration, 2),
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 2),
            "p50": round(percentile(latencies, 0.50), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "p99": round(percentile(latencies, 0.99), 2),
        },
    }
    if before and after:
        report["server_resources"] = {
            "cpu_seconds": round(max(0, after[0] - before[0]), 2),
            "mean_cpu_percent": round(max(0, after[0] - before[0]) / duration * 100, 2),
            "peak_rss_mb": round(max(memory for _, memory in samples + [before, after]), 2),
        }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
