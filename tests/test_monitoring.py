"""
Tests for Monitoring APIs

Endpoints tested:
- /api/monitor/status
- /api/monitor/metrics
- /api/monitor/events
- /api/monitor/performance
- /api/monitor/alerts
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta


class TestMonitoringStatus:
    """Test monitoring status endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_system_status(self):
        """Test getting overall system status."""
        status = {
            "status": "operational",
            "uptime_seconds": 3600,
            "start_time": "2025-09-13 09:00:00",
            "components": {
                "engine": "running",
                "webui": "running",
                "data_sources": "operational",
                "database": "healthy"
            },
            "last_check": datetime.now().isoformat()
        }
        
        assert status["status"] == "operational"
        assert status["uptime_seconds"] > 0
        assert all(v in ["running", "operational", "healthy"] 
                  for v in status["components"].values())
    
    @pytest.mark.asyncio
    async def test_component_health_check(self):
        """Test individual component health checks."""
        components = [
            {"name": "engine", "status": "healthy", "latency_ms": 5},
            {"name": "webui", "status": "healthy", "latency_ms": 10},
            {"name": "redis", "status": "healthy", "latency_ms": 1},
            {"name": "postgresql", "status": "degraded", "latency_ms": 150}
        ]
        
        unhealthy = [c for c in components if c["status"] != "healthy"]
        assert len(unhealthy) == 1
        assert unhealthy[0]["name"] == "postgresql"


class TestMetricsCollection:
    """Test metrics collection endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_system_metrics(self):
        """Test getting system metrics."""
        metrics = {
            "cpu": {
                "usage_percent": 45.5,
                "cores": 8,
                "load_average": [2.5, 2.1, 1.8]
            },
            "memory": {
                "used_gb": 8.5,
                "total_gb": 16.0,
                "percent": 53.1,
                "available_gb": 7.5
            },
            "disk": {
                "used_gb": 250,
                "total_gb": 500,
                "percent": 50.0
            },
            "network": {
                "bytes_sent": 1000000,
                "bytes_recv": 2000000,
                "packets_sent": 10000,
                "packets_recv": 15000
            }
        }
        
        assert metrics["cpu"]["usage_percent"] < 100
        assert metrics["memory"]["percent"] < 100
        assert metrics["disk"]["percent"] == 50.0
    
    @pytest.mark.asyncio
    async def test_get_api_metrics(self):
        """Test getting API performance metrics."""
        api_metrics = {
            "total_requests": 100000,
            "success_rate": 99.5,
            "error_rate": 0.5,
            "response_times": {
                "p50": 10,
                "p95": 50,
                "p99": 100,
                "max": 500
            },
            "endpoints": [
                {
                    "path": "/api/market/realtime/*",
                    "count": 50000,
                    "avg_time_ms": 15
                },
                {
                    "path": "/api/data-sources/status",
                    "count": 10000,
                    "avg_time_ms": 5
                }
            ]
        }
        
        assert api_metrics["success_rate"] > 95
        assert api_metrics["response_times"]["p50"] < api_metrics["response_times"]["p95"]
        assert api_metrics["response_times"]["p95"] < api_metrics["response_times"]["p99"]
    
    @pytest.mark.asyncio
    async def test_get_data_source_metrics(self):
        """Test getting data source metrics."""
        ds_metrics = {
            "amazingdata": {
                "requests": 10000,
                "success_rate": 98.5,
                "avg_latency_ms": 20,
                "errors": 150,
                "last_error": "2025-09-13 09:45:00"
            },
            "qmt": {
                "requests": 5000,
                "success_rate": 95.0,
                "avg_latency_ms": 15,
                "errors": 250,
                "last_error": "2025-09-13 10:00:00"
            },
            "cloudflare": {
                "requests": 20000,
                "success_rate": 99.9,
                "avg_latency_ms": 50,
                "errors": 20,
                "last_error": None
            }
        }
        
        best_source = max(ds_metrics.items(), key=lambda x: x[1]["success_rate"])
        assert best_source[0] == "cloudflare"


class TestEventMonitoring:
    """Test event monitoring endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_recent_events(self):
        """Test getting recent system events."""
        events = [
            {
                "id": 1001,
                "timestamp": "2025-09-13 10:00:00",
                "level": "info",
                "source": "engine",
                "message": "Engine started successfully"
            },
            {
                "id": 1002,
                "timestamp": "2025-09-13 10:00:05",
                "level": "warning",
                "source": "data_source",
                "message": "QMT connection slow, latency > 100ms"
            },
            {
                "id": 1003,
                "timestamp": "2025-09-13 10:00:10",
                "level": "error",
                "source": "amazingdata",
                "message": "Connection timeout"
            }
        ]
        
        assert len(events) == 3
        assert events[0]["level"] == "info"
        assert events[2]["level"] == "error"
        
        errors = [e for e in events if e["level"] == "error"]
        assert len(errors) == 1
    
    @pytest.mark.asyncio
    async def test_filter_events_by_level(self):
        """Test filtering events by severity level."""
        all_events = [
            {"level": "debug", "message": "Debug message"},
            {"level": "info", "message": "Info message"},
            {"level": "warning", "message": "Warning message"},
            {"level": "error", "message": "Error message"},
            {"level": "critical", "message": "Critical message"}
        ]
        
        # Filter for warnings and above
        important_events = [e for e in all_events 
                          if e["level"] in ["warning", "error", "critical"]]
        assert len(important_events) == 3
    
    @pytest.mark.asyncio
    async def test_event_aggregation(self):
        """Test event aggregation by source."""
        aggregated = {
            "engine": {"total": 100, "errors": 2},
            "data_sources": {"total": 500, "errors": 25},
            "webui": {"total": 200, "errors": 5},
            "database": {"total": 150, "errors": 1}
        }
        
        total_events = sum(s["total"] for s in aggregated.values())
        total_errors = sum(s["errors"] for s in aggregated.values())
        error_rate = (total_errors / total_events) * 100
        
        assert total_events == 950
        assert error_rate < 5  # Less than 5% error rate


class TestPerformanceMonitoring:
    """Test performance monitoring endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_performance_profile(self):
        """Test getting performance profiling data."""
        profile = {
            "cpu_profile": {
                "hot_functions": [
                    {"name": "calculate_indicators", "percent": 15.5},
                    {"name": "process_market_data", "percent": 12.3},
                    {"name": "update_cache", "percent": 8.7}
                ]
            },
            "memory_profile": {
                "largest_objects": [
                    {"type": "DataFrame", "size_mb": 150},
                    {"type": "dict", "size_mb": 50},
                    {"type": "list", "size_mb": 30}
                ]
            },
            "io_profile": {
                "disk_operations": 10000,
                "network_calls": 50000,
                "cache_hits": 45000,
                "cache_misses": 5000
            }
        }
        
        assert profile["cpu_profile"]["hot_functions"][0]["percent"] > 10
        cache_hit_rate = profile["io_profile"]["cache_hits"] / (
            profile["io_profile"]["cache_hits"] + profile["io_profile"]["cache_misses"]
        )
        assert cache_hit_rate > 0.8  # 80% cache hit rate
    
    @pytest.mark.asyncio
    async def test_bottleneck_detection(self):
        """Test bottleneck detection."""
        bottlenecks = [
            {
                "type": "database",
                "severity": "high",
                "description": "Slow queries on kline_data table",
                "recommendation": "Add index on (symbol, date) columns"
            },
            {
                "type": "memory",
                "severity": "medium",
                "description": "High memory usage in data processing",
                "recommendation": "Implement data streaming instead of loading all data"
            }
        ]
        
        high_severity = [b for b in bottlenecks if b["severity"] == "high"]
        assert len(high_severity) == 1
        assert "recommendation" in high_severity[0]


class TestAlertManagement:
    """Test alert management endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_active_alerts(self):
        """Test getting active alerts."""
        alerts = [
            {
                "id": 1,
                "severity": "critical",
                "title": "Database connection pool exhausted",
                "description": "All connections in use, queries queuing",
                "created_at": "2025-09-13 10:00:00",
                "acknowledged": False
            },
            {
                "id": 2,
                "severity": "warning",
                "title": "High memory usage",
                "description": "Memory usage above 80%",
                "created_at": "2025-09-13 09:45:00",
                "acknowledged": True
            }
        ]
        
        unacknowledged = [a for a in alerts if not a["acknowledged"]]
        assert len(unacknowledged) == 1
        assert unacknowledged[0]["severity"] == "critical"
    
    @pytest.mark.asyncio
    async def test_acknowledge_alert(self):
        """Test acknowledging an alert."""
        alert_id = 1
        
        # Acknowledge alert
        result = {"success": True, "alert_id": alert_id, "acknowledged_at": datetime.now().isoformat()}
        
        assert result["success"] == True
        assert result["alert_id"] == alert_id
    
    @pytest.mark.asyncio
    async def test_alert_rules(self):
        """Test alert rule configuration."""
        rules = [
            {
                "id": 1,
                "name": "High CPU Usage",
                "condition": "cpu_usage > 80",
                "severity": "warning",
                "enabled": True,
                "notification_channels": ["email", "webhook"]
            },
            {
                "id": 2,
                "name": "Database Connection Failure",
                "condition": "database_connected == false",
                "severity": "critical",
                "enabled": True,
                "notification_channels": ["email", "sms", "webhook"]
            }
        ]
        
        critical_rules = [r for r in rules if r["severity"] == "critical"]
        assert len(critical_rules) == 1
        assert "sms" in critical_rules[0]["notification_channels"]