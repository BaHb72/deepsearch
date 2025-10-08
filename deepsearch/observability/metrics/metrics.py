"""
Metrics collection utilities.

This module provides basic metrics collection functionality
for system monitoring and performance analysis.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional

from deepsearch.constants import METRICS_WINDOW_SIZE


@dataclass
class Metric:
    """Single metric data point."""

    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    Simple metrics collector for system monitoring.

    Collects and aggregates metrics with a sliding time window.
    """

    def __init__(self, window_size: int = METRICS_WINDOW_SIZE) -> None:
        """
        Initialize metrics collector.

        Args:
            window_size: Time window in seconds for metric aggregation
        """
        self.window_size = window_size
        self._metrics: Dict[str, Deque[Metric]] = defaultdict(lambda: deque())
        self._counters: Dict[str, float] = defaultdict(float)

    def record(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """
        Record a metric value.

        Args:
            name: Metric name
            value: Metric value
            tags: Optional tags for the metric
        """
        metric = Metric(name=name, value=value, tags=tags or {})
        self._metrics[name].append(metric)
        self._cleanup_old_metrics(name)

    def increment(self, name: str, value: float = 1.0) -> None:
        """
        Increment a counter metric.

        Args:
            name: Counter name
            value: Amount to increment by
        """
        self._counters[name] += value

    def get_counter(self, name: str) -> float:
        """
        Get current counter value.

        Args:
            name: Counter name

        Returns:
            Current counter value
        """
        return self._counters.get(name, 0.0)

    def get_stats(self, name: str) -> Dict[str, float]:
        """
        Get statistics for a metric.

        Args:
            name: Metric name

        Returns:
            Dictionary with min, max, avg, count
        """
        metrics = list(self._metrics.get(name, []))

        if not metrics:
            return {"min": 0.0, "max": 0.0, "avg": 0.0, "count": 0}

        values = [m.value for m in metrics]
        return {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "count": len(values),
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all collected metrics.

        Returns:
            Dictionary of all metrics and counters
        """
        metrics_map: Dict[str, Dict[str, float]] = {}
        for name in self._metrics:
            metrics_map[name] = self.get_stats(name)

        return {"counters": dict(self._counters), "metrics": metrics_map}

    def reset(self) -> None:
        """Reset all metrics and counters."""
        self._metrics.clear()
        self._counters.clear()

    def _cleanup_old_metrics(self, name: str) -> None:
        """Remove metrics older than the window size."""
        cutoff_time = time.time() - self.window_size
        metrics = self._metrics[name]

        while metrics and metrics[0].timestamp < cutoff_time:
            metrics.popleft()




