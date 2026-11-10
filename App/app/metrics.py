"""Application usage metrics in Prometheus text format (brief 0427 prep).

Four families, all PII-free (OPS-3): route *templates* and numeric
status codes, never a path, token, query string or user identifier.

- ubyhost_requests_total{method,route,status}         counter
- ubyhost_request_duration_seconds{method,route}     histogram (seconds)
- ubyhost_request_db_queries_total{method,route}     counter (statements run)
- ubyhost_request_db_seconds_total{method,route}     counter (seconds inside the db helpers)

Queries per request on a route = rate of the db_queries counter divided by
the rate of ubyhost_request_duration_seconds_count (brief 1065).

The registry is process-local; each uvicorn worker reports its own counts,
and Prometheus sums them. No dependency on prometheus_client on purpose:
the text format for two families is a few lines of code, and the app image
stays small.
"""
from __future__ import annotations

import threading

_lock = threading.Lock()

# route template -> method -> status -> count
_requests: dict[str, dict[str, dict[int, int]]] = {}
# route template -> method -> bucket index -> count; buckets in seconds
_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
_durations: dict[str, dict[str, list[int]]] = {}
_duration_sums: dict[str, dict[str, float]] = {}
_duration_counts: dict[str, dict[str, int]] = {}
# route template -> method -> total (brief 1065)
_db_queries: dict[str, dict[str, int]] = {}
_db_seconds: dict[str, dict[str, float]] = {}


def observe_request(
    method: str,
    route: str,
    status: int,
    duration_seconds: float,
    db_queries: int = 0,
    db_seconds: float = 0.0,
) -> None:
    """Record one finished request. Call from the outermost middleware."""
    with _lock:
        by_method = _requests.setdefault(route, {})
        by_status = by_method.setdefault(method, {})
        by_status[status] = by_status.get(status, 0) + 1
        d = _durations.setdefault(route, {}).setdefault(method, [0] * len(_DURATION_BUCKETS))
        for i, bound in enumerate(_DURATION_BUCKETS):
            if duration_seconds <= bound:
                d[i] += 1
        sums = _duration_sums.setdefault(route, {})
        sums[method] = sums.get(method, 0.0) + duration_seconds
        counts = _duration_counts.setdefault(route, {})
        counts[method] = counts.get(method, 0) + 1
        queries = _db_queries.setdefault(route, {})
        queries[method] = queries.get(method, 0) + max(0, int(db_queries))
        waited = _db_seconds.setdefault(route, {})
        waited[method] = waited.get(method, 0.0) + max(0.0, float(db_seconds))


def _label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render() -> str:
    """The registry as Prometheus text format (version 0.0.4)."""
    with _lock:
        lines: list[str] = []
        routes = sorted(_requests)
        lines.append("# HELP ubyhost_requests_total Finished requests by route template, method and status.")
        lines.append("# TYPE ubyhost_requests_total counter")
        for route in routes:
            for method, statuses in sorted(_requests[route].items()):
                for status, count in sorted(statuses.items()):
                    lines.append(
                        f'ubyhost_requests_total{{method="{_label_value(method)}",route="{_label_value(route)}",status="{status}"}} {count}'
                    )
        lines.append("# HELP ubyhost_request_duration_seconds Request duration by route template and method.")
        lines.append("# TYPE ubyhost_request_duration_seconds histogram")
        for route in sorted(_durations):
            for method, buckets in sorted(_durations[route].items()):
                labels = f'method="{_label_value(method)}",route="{_label_value(route)}"'
                # observe_request increments every bucket the request fits
                # under, so the stored counts are already cumulative.
                for bound, count in zip(_DURATION_BUCKETS, buckets):
                    lines.append(f'ubyhost_request_duration_seconds_bucket{{le="{bound}",{labels}}} {count}')
                lines.append(f'ubyhost_request_duration_seconds_bucket{{le="+Inf",{labels}}} {count}')
                lines.append(f"ubyhost_request_duration_seconds_sum{{{labels}}} {_duration_sums[route][method]!r}")
                lines.append(f"ubyhost_request_duration_seconds_count{{{labels}}} {_duration_counts[route][method]}")
        lines.append("# HELP ubyhost_request_db_queries_total Database statements run by finished requests, by route template and method.")
        lines.append("# TYPE ubyhost_request_db_queries_total counter")
        for route in sorted(_db_queries):
            for method, total in sorted(_db_queries[route].items()):
                lines.append(
                    f'ubyhost_request_db_queries_total{{method="{_label_value(method)}",route="{_label_value(route)}"}} {total}'
                )
        lines.append("# HELP ubyhost_request_db_seconds_total Seconds finished requests spent in the database helpers, by route template and method.")
        lines.append("# TYPE ubyhost_request_db_seconds_total counter")
        for route in sorted(_db_seconds):
            for method, total in sorted(_db_seconds[route].items()):
                lines.append(
                    f'ubyhost_request_db_seconds_total{{method="{_label_value(method)}",route="{_label_value(route)}"}} {total!r}'
                )
        return "\n".join(lines) + "\n"
