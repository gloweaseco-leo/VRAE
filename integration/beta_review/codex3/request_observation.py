"""Opt-in per-request legacy latency profile; never records request arguments."""

import cProfile
import json
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit


def observe_legacy_review(app, output):
    """Delegate unchanged app.handle; inspect only one signed legacy 200 GET."""
    original = app.handle
    lock = threading.Lock()
    claimed = False
    output = Path(output)

    def handle(method, target, headers, raw):
        nonlocal claimed
        selected = method == "GET" and urlsplit(target).path in (
            "/b5a/tasks/task-200/review",
            "/b5a/tasks/task-200/rehearsal",
        )
        with lock:
            selected = selected and not claimed
            if selected:
                claimed = True
        if not selected:
            return original(method, target, headers, raw)
        profiler = cProfile.Profile()
        begin, cpu = time.perf_counter_ns(), time.thread_time_ns()
        response = None
        try:
            profiler.enable()
            response = original(method, target, headers, raw)
            return response
        finally:
            profiler.disable()
            entries = []
            for entry in sorted(profiler.getstats(), key=lambda e: e.totaltime, reverse=True)[:40]:
                code = entry.code
                entries.append(
                    {
                        "function": code if isinstance(code, str) else code.co_name,
                        "file": None if isinstance(code, str) else Path(code.co_filename).name,
                        "line": None if isinstance(code, str) else code.co_firstlineno,
                        "calls": entry.callcount,
                        "recursive_calls": entry.reccallcount,
                        "cumulative_seconds": entry.totaltime,
                        "self_seconds": entry.inlinetime,
                    }
                )
            value = {
                "scope": "OPT_IN_ONE_LEGACY_200_REVIEW_DIAGNOSTIC_NOT_NEW_JOB",
                "wall_ms": (time.perf_counter_ns() - begin) / 1e6,
                "thread_cpu_ms": (time.thread_time_ns() - cpu) / 1e6,
                "status": getattr(getattr(response, "response", None), "status", None),
                "observer_overhead_not_subtracted": True,
                "request_arguments_recorded": False,
                "entries": entries,
            }
            temporary = output.with_suffix(".tmp")
            temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
            temporary.replace(output)

    app.handle = handle
