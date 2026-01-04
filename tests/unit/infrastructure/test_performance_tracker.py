"""
性能跟踪器单元测试
"""

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from core.infrastructure.monitoring.performance_tracker import (
    Alert,
    AlertSeverity,
    ApplicationMetrics,
    DatabaseMetrics,
    MetricLevel,
    PerformanceTracker,
    SystemMetrics,
    get_tracker,
    record_app_metrics,
    record_db_metrics,
)


class TestSystemMetrics:
    """系统指标测试"""

    def test_system_metrics_creation(self):
        """测试系统指标创建"""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=50.5,
            memory_percent=60.2,
            memory_available=4096000000,
            memory_used=8192000000,
            disk_io_read_bytes=1024000,
            disk_io_write_bytes=2048000,
            network_sent_bytes=512000,
            network_recv_bytes=256000,
            process_count=100,
            thread_count=200,
            open_files=50,
        )

        assert metrics.cpu_percent == 50.5
        assert metrics.memory_percent == 60.2
        assert metrics.process_count == 100

    def test_system_metrics_to_dict(self):
        """测试系统指标转换为字典"""
        timestamp = time.time()
        metrics = SystemMetrics(
            timestamp=timestamp,
            cpu_percent=50.5,
            memory_percent=60.2,
            memory_available=4096000000,
            memory_used=8192000000,
            disk_io_read_bytes=1024000,
            disk_io_write_bytes=2048000,
            network_sent_bytes=512000,
            network_recv_bytes=256000,
            process_count=100,
            thread_count=200,
            open_files=50,
        )

        result = metrics.to_dict()

        assert result["timestamp"] == timestamp
        assert result["cpu"]["percent"] == 50.5
        assert result["memory"]["percent"] == 60.2
        assert result["memory"]["available_mb"] == pytest.approx(3906.25, 0.01)
        assert result["memory"]["used_mb"] == pytest.approx(7812.5, 0.01)
        assert result["disk_io"]["read_mb"] == pytest.approx(0.98, 0.01)
        assert result["disk_io"]["write_mb"] == pytest.approx(1.95, 0.01)
        assert result["process"]["count"] == 100
        assert result["process"]["threads"] == 200


class TestDatabaseMetrics:
    """数据库指标测试"""

    def test_database_metrics_creation(self):
        """测试数据库指标创建"""
        metrics = DatabaseMetrics(
            timestamp=time.time(),
            active_connections=10,
            idle_connections=5,
            total_queries=1000,
            slow_queries=10,
            failed_queries=5,
            avg_query_time=0.05,
            max_query_time=2.5,
            cache_hit_ratio=0.85,
        )

        assert metrics.active_connections == 10
        assert metrics.total_queries == 1000
        assert metrics.cache_hit_ratio == 0.85

    def test_database_metrics_to_dict(self):
        """测试数据库指标转换"""
        timestamp = time.time()
        metrics = DatabaseMetrics(
            timestamp=timestamp,
            active_connections=10,
            idle_connections=5,
            total_queries=1000,
            slow_queries=10,
            failed_queries=5,
            avg_query_time=0.05,
            max_query_time=2.5,
            cache_hit_ratio=0.85,
            deadlocks=2,
            lock_waits=15,
        )

        result = metrics.to_dict()

        assert result["timestamp"] == timestamp
        assert result["connections"]["active"] == 10
        assert result["connections"]["idle"] == 5
        assert result["connections"]["total"] == 15
        assert result["queries"]["total"] == 1000
        assert result["queries"]["error_rate"] == 0.5
        assert result["performance"]["avg_query_time_ms"] == 50.0
        assert result["performance"]["cache_hit_ratio"] == 85.0
        assert result["locks"]["deadlocks"] == 2


class TestApplicationMetrics:
    """应用指标测试"""

    def test_application_metrics_creation(self):
        """测试应用指标创建"""
        metrics = ApplicationMetrics(
            timestamp=time.time(),
            request_count=5000,
            request_rate=100.5,
            error_count=50,
            error_rate=0.01,
            avg_response_time=0.2,
            p50_response_time=0.15,
            p90_response_time=0.4,
            p99_response_time=1.2,
            active_sessions=25,
            cache_hit_rate=0.75,
            event_queue_size=100,
        )

        assert metrics.request_count == 5000
        assert metrics.error_rate == 0.01
        assert metrics.p99_response_time == 1.2

    def test_application_metrics_to_dict(self):
        """测试应用指标转换"""
        timestamp = time.time()
        metrics = ApplicationMetrics(
            timestamp=timestamp,
            request_count=5000,
            request_rate=100.5,
            error_count=50,
            error_rate=0.01,
            avg_response_time=0.2,
            p50_response_time=0.15,
            p90_response_time=0.4,
            p99_response_time=1.2,
            active_sessions=25,
            cache_hit_rate=0.75,
            event_queue_size=100,
        )

        result = metrics.to_dict()

        assert result["timestamp"] == timestamp
        assert result["requests"]["count"] == 5000
        assert result["requests"]["rate_per_sec"] == 100.5
        assert result["requests"]["error_rate"] == 1.0
        assert result["response_time"]["avg_ms"] == 200.0
        assert result["response_time"]["p99_ms"] == 1200.0
        assert result["application"]["cache_hit_rate"] == 75.0


class TestAlert:
    """告警测试"""

    def test_alert_creation(self):
        """测试告警创建"""
        alert = Alert(
            id="test_alert_001",
            severity=AlertSeverity.WARNING,
            metric_level=MetricLevel.SYSTEM,
            message="CPU使用率过高",
            details={"cpu_percent": 85.5},
        )

        assert alert.id == "test_alert_001"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.metric_level == MetricLevel.SYSTEM
        assert not alert.resolved

    def test_alert_resolution(self):
        """测试告警解决"""
        alert = Alert(
            id="test_alert_001",
            severity=AlertSeverity.WARNING,
            metric_level=MetricLevel.SYSTEM,
            message="CPU使用率过高",
            details={"cpu_percent": 85.5},
        )

        # 标记为已解决
        alert.resolved = True
        alert.resolved_at = datetime.now()

        assert alert.resolved
        assert alert.resolved_at is not None

    def test_alert_to_dict(self):
        """测试告警转换为字典"""
        alert = Alert(
            id="test_alert_001",
            severity=AlertSeverity.WARNING,
            metric_level=MetricLevel.SYSTEM,
            message="CPU使用率过高",
            details={"cpu_percent": 85.5},
        )

        result = alert.to_dict()

        assert result["id"] == "test_alert_001"
        assert result["severity"] == "warning"
        assert result["level"] == "system"
        assert result["message"] == "CPU使用率过高"
        assert result["details"]["cpu_percent"] == 85.5
        assert result["resolved"] is False
        assert result["resolved_at"] is None


class TestPerformanceTracker:
    """性能跟踪器测试"""

    @pytest.fixture
    def tracker(self):
        """创建跟踪器实例"""
        tracker = PerformanceTracker(collect_interval=0.1, history_size=100, enable_alerts=True)
        yield tracker
        # 清理
        if tracker._running:
            tracker.stop()

    def test_tracker_initialization(self, tracker):
        """测试跟踪器初始化"""
        assert tracker.collect_interval == 0.1
        assert tracker.history_size == 100
        assert tracker.enable_alerts is True
        assert not tracker._running
        assert len(tracker.alert_rules) > 0  # 有默认规则

    @patch("core.infrastructure.monitoring.performance_tracker.psutil")
    def test_collect_system_metrics(self, mock_psutil, tracker):
        """测试系统指标采集"""
        # 模拟psutil返回值
        mock_psutil.cpu_percent.return_value = 45.5

        mock_memory = MagicMock()
        mock_memory.percent = 60.0
        mock_memory.available = 4000000000
        mock_memory.used = 8000000000
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk_io = MagicMock()
        mock_disk_io.read_bytes = 1000000
        mock_disk_io.write_bytes = 2000000
        mock_psutil.disk_io_counters.return_value = mock_disk_io

        mock_net_io = MagicMock()
        mock_net_io.bytes_sent = 500000
        mock_net_io.bytes_recv = 250000
        mock_psutil.net_io_counters.return_value = mock_net_io

        mock_psutil.pids.return_value = list(range(100))

        # 采集指标
        metrics = tracker._collect_system_metrics()

        assert metrics.cpu_percent == 45.5
        assert metrics.memory_percent == 60.0
        assert metrics.memory_available == 4000000000
        assert metrics.process_count == 100

    def test_record_database_metrics(self, tracker):
        """测试记录数据库指标"""
        metrics = DatabaseMetrics(
            timestamp=time.time(), active_connections=15, total_queries=2000, avg_query_time=0.08
        )

        tracker.record_database_metrics(metrics)

        assert len(tracker.database_metrics) == 1
        assert tracker.database_metrics[0].active_connections == 15

    def test_record_application_metrics(self, tracker):
        """测试记录应用指标"""
        metrics = ApplicationMetrics(
            timestamp=time.time(), request_count=3000, error_count=30, avg_response_time=0.15
        )

        tracker.record_application_metrics(metrics)

        assert len(tracker.application_metrics) == 1
        assert tracker.application_metrics[0].request_count == 3000

    def test_record_custom_metric(self, tracker):
        """测试记录自定义指标"""
        tracker.record_custom_metric("api_calls", 150.0, {"endpoint": "/api/test"})
        tracker.record_custom_metric("api_calls", 200.0, {"endpoint": "/api/test"})

        assert "api_calls" in tracker.custom_metrics
        assert len(tracker.custom_metrics["api_calls"]) == 2
        assert tracker.custom_metrics["api_calls"][0]["value"] == 150.0

    def test_get_current_metrics(self, tracker):
        """测试获取当前指标"""
        # 添加一些指标
        db_metrics = DatabaseMetrics(
            timestamp=time.time(), active_connections=10, total_queries=1000, avg_query_time=0.05
        )
        tracker.record_database_metrics(db_metrics)

        app_metrics = ApplicationMetrics(
            timestamp=time.time(), request_count=500, error_count=5, avg_response_time=0.1
        )
        tracker.record_application_metrics(app_metrics)

        current = tracker.get_current_metrics()

        assert "database" in current
        assert current["database"]["connections"]["active"] == 10
        assert "application" in current
        assert current["application"]["requests"]["count"] == 500

    def test_get_metrics_history(self, tracker):
        """测试获取指标历史"""
        # 添加多个数据库指标
        for i in range(5):
            metrics = DatabaseMetrics(
                timestamp=time.time() + i,
                active_connections=10 + i,
                total_queries=1000 + i * 100,
                avg_query_time=0.05,
            )
            tracker.record_database_metrics(metrics)
            time.sleep(0.01)

        history = tracker.get_metrics_history(MetricLevel.DATABASE)

        assert len(history) == 5
        assert history[0]["connections"]["active"] == 10
        assert history[4]["connections"]["active"] == 14

    def test_alert_generation(self, tracker):
        """测试告警生成"""
        # 记录高错误率的应用指标
        metrics = ApplicationMetrics(
            timestamp=time.time(),
            request_count=1000,
            error_count=200,
            error_rate=0.2,  # 20%错误率，超过阈值
            avg_response_time=0.1,
        )

        tracker.record_application_metrics(metrics)

        # 应该生成告警
        alerts = tracker.get_alerts(active_only=True)
        assert len(alerts) > 0

    def test_alert_resolution(self, tracker):
        """测试告警解决"""
        # 先生成告警
        high_error_metrics = ApplicationMetrics(
            timestamp=time.time(),
            request_count=1000,
            error_count=200,
            error_rate=0.2,
            avg_response_time=0.1,
        )
        tracker.record_application_metrics(high_error_metrics)

        # 确认有告警
        assert len(tracker.get_alerts(active_only=True)) > 0

        # 记录正常指标
        normal_metrics = ApplicationMetrics(
            timestamp=time.time(),
            request_count=1000,
            error_count=10,
            error_rate=0.01,  # 1%错误率，正常
            avg_response_time=0.1,
        )
        tracker.record_application_metrics(normal_metrics)

        # 告警应该被解决
        active_alerts = tracker.get_alerts(active_only=True)
        all_alerts = tracker.get_alerts(active_only=False)

        # 至少有一个告警被解决
        assert len(all_alerts) > len(active_alerts)

    def test_get_statistics(self, tracker):
        """测试获取统计信息"""
        # 添加一些指标
        for i in range(3):
            db_metrics = DatabaseMetrics(
                timestamp=time.time() + i,
                active_connections=10 + i,
                total_queries=1000 + i * 100,
                avg_query_time=0.05,
            )
            tracker.record_database_metrics(db_metrics)

        stats = tracker.get_statistics()

        assert "timestamp" in stats
        assert "metrics_count" in stats
        assert stats["metrics_count"]["database"] == 3
        assert "alerts" in stats

    def test_metric_callbacks(self, tracker):
        """测试指标回调"""
        callback_called = []

        def metric_callback(level, metrics):
            callback_called.append((level, metrics))

        tracker.add_metric_callback(metric_callback)

        # 记录指标
        db_metrics = DatabaseMetrics(
            timestamp=time.time(), active_connections=10, total_queries=1000, avg_query_time=0.05
        )
        tracker.record_database_metrics(db_metrics)

        assert len(callback_called) == 1
        assert callback_called[0][0] == MetricLevel.DATABASE
        assert callback_called[0][1] == db_metrics

    def test_alert_callbacks(self, tracker):
        """测试告警回调"""
        alert_received = []

        def alert_callback(alert):
            alert_received.append(alert)

        tracker.add_alert_callback(alert_callback)

        # 触发告警
        high_error_metrics = ApplicationMetrics(
            timestamp=time.time(),
            request_count=1000,
            error_count=200,
            error_rate=0.2,
            avg_response_time=0.1,
        )
        tracker.record_application_metrics(high_error_metrics)

        assert len(alert_received) > 0
        assert isinstance(alert_received[0], Alert)

    def test_export_metrics(self, tracker, tmp_path):
        """测试导出指标"""
        # 添加一些指标
        db_metrics = DatabaseMetrics(
            timestamp=time.time(), active_connections=10, total_queries=1000, avg_query_time=0.05
        )
        tracker.record_database_metrics(db_metrics)

        # 导出到JSON
        export_file = tmp_path / "metrics.json"
        tracker.export_metrics(str(export_file), format="json")

        assert export_file.exists()

        # 读取并验证
        import json

        with open(export_file, "r") as f:
            data = json.load(f)

        assert "exported_at" in data
        assert "database" in data
        assert len(data["database"]) == 1

    def test_generate_report(self, tracker):
        """测试生成报告"""
        # 添加各种指标
        db_metrics = DatabaseMetrics(
            timestamp=time.time(), active_connections=10, total_queries=1000, avg_query_time=0.05
        )
        tracker.record_database_metrics(db_metrics)

        app_metrics = ApplicationMetrics(
            timestamp=time.time(), request_count=500, error_count=5, avg_response_time=0.1
        )
        tracker.record_application_metrics(app_metrics)

        report = tracker.generate_report()

        assert "# 性能监控报告" in report
        assert "数据库性能" in report
        assert "应用性能" in report

    @patch("core.infrastructure.monitoring.performance_tracker.threading.Thread")
    def test_start_stop(self, mock_thread, tracker):
        """测试启动和停止"""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # 启动
        tracker.start()
        assert tracker._running is True
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

        # 停止
        tracker.stop()
        assert tracker._running is False
        mock_thread_instance.join.assert_called_once()

    def test_history_size_limit(self, tracker):
        """测试历史大小限制"""
        tracker.history_size = 5  # 设置小的历史大小

        # 添加超过限制的指标
        for i in range(10):
            metrics = DatabaseMetrics(
                timestamp=time.time() + i,
                active_connections=i,
                total_queries=i * 100,
                avg_query_time=0.05,
            )
            tracker.record_database_metrics(metrics)

        # 应该只保留最后5个
        assert len(tracker.database_metrics) == 5
        assert tracker.database_metrics[0].active_connections == 5
        assert tracker.database_metrics[-1].active_connections == 9


class TestGlobalFunctions:
    """测试全局函数"""

    @patch("core.infrastructure.monitoring.performance_tracker._tracker", None)
    def test_get_tracker(self):
        """测试获取全局跟踪器"""
        tracker1 = get_tracker()
        tracker2 = get_tracker()

        assert tracker1 is tracker2  # 应该是同一个实例
        assert tracker1._running is True  # 应该自动启动

        # 清理
        tracker1.stop()

    @patch("core.infrastructure.monitoring.performance_tracker.get_tracker")
    def test_record_db_metrics_shortcut(self, mock_get_tracker):
        """测试数据库指标快捷记录"""
        mock_tracker = MagicMock()
        mock_get_tracker.return_value = mock_tracker

        record_db_metrics(
            active_connections=20, total_queries=3000, avg_query_time=0.1, slow_queries=50
        )

        mock_tracker.record_database_metrics.assert_called_once()
        call_args = mock_tracker.record_database_metrics.call_args[0][0]
        assert call_args.active_connections == 20
        assert call_args.total_queries == 3000
        assert call_args.slow_queries == 50

    @patch("core.infrastructure.monitoring.performance_tracker.get_tracker")
    def test_record_app_metrics_shortcut(self, mock_get_tracker):
        """测试应用指标快捷记录"""
        mock_tracker = MagicMock()
        mock_get_tracker.return_value = mock_tracker

        record_app_metrics(
            request_count=1000, error_count=10, avg_response_time=0.2, cache_hit_rate=0.8
        )

        mock_tracker.record_application_metrics.assert_called_once()
        call_args = mock_tracker.record_application_metrics.call_args[0][0]
        assert call_args.request_count == 1000
        assert call_args.error_count == 10
        assert call_args.error_rate == 0.01
        assert call_args.cache_hit_rate == 0.8
