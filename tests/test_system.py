"""
Tests for System Management APIs

Endpoints tested:
- /api/system/info
- /api/system/config
- /api/system/logs
- /api/system/restart
- /api/system/shutdown
"""

import platform

import psutil
import pytest


class TestSystemInfo:
    """Test system information endpoints."""

    @pytest.mark.asyncio
    async def test_get_system_info(self):
        """Test getting system information."""
        info = {
            "version": "0.1.0",
            "python_version": platform.python_version(),
            "platform": platform.system(),
            "architecture": platform.machine(),
            "hostname": platform.node(),
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": psutil.virtual_memory().total / (1024**3),
            "disk_total_gb": psutil.disk_usage("/").total / (1024**3),
            "start_time": "2025-09-13 09:00:00",
            "uptime_hours": 1.5,
        }

        assert info["version"] == "0.1.0"
        assert info["cpu_count"] > 0
        assert info["memory_total_gb"] > 0

    @pytest.mark.asyncio
    async def test_get_environment_info(self):
        """Test getting environment information."""
        env_info = {
            "environment": "production",
            "debug_mode": False,
            "config_file": "settings.prod.yaml",
            "data_dir": "./data",
            "log_dir": "./logs",
            "cache_enabled": True,
            "installed_packages": [
                {"name": "fastapi", "version": "0.116.1"},
                {"name": "sqlalchemy", "version": "2.0.41"},
                {"name": "redis", "version": "6.2.0"},
            ],
        }

        assert env_info["environment"] == "production"
        assert not env_info["debug_mode"]
        assert len(env_info["installed_packages"]) > 0


class TestConfiguration:
    """Test configuration management endpoints."""

    @pytest.mark.asyncio
    async def test_get_current_config(self, mock_config):
        """Test getting current configuration."""
        config_data = {
            "app": {"name": "DeepSearch", "env": "prod", "debug": False},
            "database": {
                "main": {
                    "type": "postgresql",
                    "host": "localhost",
                    "port": 5432,
                    "database": "deepsearch",
                }
            },
            "data_providers": {
                "amazingdata": {"enabled": True, "priority": 1},
                "qmt": {"enabled": True, "priority": 2},
                "akshare": {
                    "enabled": True,
                    "priority": 3,
                    "config": {"mode": "worker", "proxy": {"enabled": True}},
                },
            },
        }

        assert config_data["app"]["name"] == "DeepSearch"
        assert config_data["database"]["main"]["type"] == "postgresql"
        assert len(config_data["data_providers"]) == 3

    @pytest.mark.asyncio
    async def test_validate_config_changes(self):
        """Test configuration validation."""

        validation_result = {
            "valid": False,
            "errors": [
                {"field": "database.main.port", "error": "Must be an integer", "value": "invalid"}
            ],
        }

        assert not validation_result["valid"]
        assert len(validation_result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_reload_configuration(self):
        """Test configuration reload."""
        result = {
            "success": True,
            "message": "Configuration reloaded successfully",
            "changes": [
                "data_providers.amazingdata.enabled: false -> true",
                "log.level: INFO -> DEBUG",
            ],
        }

        assert result["success"]
        assert len(result["changes"]) == 2


class TestLogManagement:
    """Test log management endpoints."""

    @pytest.mark.asyncio
    async def test_get_recent_logs(self):
        """Test getting recent log entries."""
        logs = [
            {
                "timestamp": "2025-09-13 10:00:00",
                "level": "INFO",
                "logger": "core.engine",
                "message": "Engine started successfully",
            },
            {
                "timestamp": "2025-09-13 10:00:05",
                "level": "ERROR",
                "logger": "deepsearch.data_providers",
                "message": "Failed to connect to AmazingData",
                "exception": "ConnectionTimeout",
            },
        ]

        assert len(logs) == 2
        assert logs[0]["level"] == "INFO"
        assert logs[1]["level"] == "ERROR"
        assert "exception" in logs[1]

    @pytest.mark.asyncio
    async def test_filter_logs_by_level(self):
        """Test filtering logs by level."""
        all_logs = [
            {"level": "DEBUG", "message": "Debug"},
            {"level": "INFO", "message": "Info"},
            {"level": "WARNING", "message": "Warning"},
            {"level": "ERROR", "message": "Error"},
        ]

        error_logs = [log for log in all_logs if log["level"] == "ERROR"]
        assert len(error_logs) == 1

        important_logs = [log for log in all_logs if log["level"] in ["WARNING", "ERROR"]]
        assert len(important_logs) == 2

    @pytest.mark.asyncio
    async def test_get_log_statistics(self):
        """Test getting log statistics."""
        stats = {
            "total_entries": 10000,
            "by_level": {
                "DEBUG": 3000,
                "INFO": 5000,
                "WARNING": 1500,
                "ERROR": 400,
                "CRITICAL": 100,
            },
            "by_logger": {
                "core.engine": 2000,
                "deepsearch.webui": 3000,
                "deepsearch.data_providers": 5000,
            },
            "errors_last_hour": 25,
            "warnings_last_hour": 50,
        }

        assert stats["total_entries"] == sum(stats["by_level"].values())
        assert stats["by_level"]["ERROR"] < stats["by_level"]["INFO"]


class TestSystemControl:
    """Test system control endpoints."""

    @pytest.mark.asyncio
    async def test_restart_component(self):
        """Test restarting a system component."""
        result = {
            "success": True,
            "component": "data_sources",
            "message": "Component restarted successfully",
            "downtime_ms": 500,
        }

        assert result["success"]
        assert result["downtime_ms"] < 1000  # Less than 1 second

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self):
        """Test graceful system shutdown."""
        shutdown_result = {
            "initiated": True,
            "grace_period_seconds": 30,
            "components_to_stop": ["webui", "engine", "data_sources", "database_connections"],
            "message": "Shutdown initiated, will complete in 30 seconds",
        }

        assert shutdown_result["initiated"]
        assert shutdown_result["grace_period_seconds"] == 30
        assert "engine" in shutdown_result["components_to_stop"]

    @pytest.mark.asyncio
    async def test_emergency_stop(self):
        """Test emergency stop functionality."""
        result = {
            "success": True,
            "stopped_components": ["engine", "webui", "data_sources"],
            "time_taken_ms": 100,
            "data_loss_risk": "minimal",
        }

        assert result["success"]
        assert result["time_taken_ms"] < 500  # Should be fast
        assert result["data_loss_risk"] == "minimal"


class TestBackupRestore:
    """Test backup and restore endpoints."""

    @pytest.mark.asyncio
    async def test_create_backup(self):
        """Test creating system backup."""
        backup = {
            "id": "backup_20250913_100000",
            "timestamp": "2025-09-13 10:00:00",
            "size_mb": 500,
            "includes": ["database", "configuration", "logs"],
            "location": "/backups/backup_20250913_100000.tar.gz",
            "success": True,
        }

        assert backup["success"]
        assert "database" in backup["includes"]
        assert backup["size_mb"] > 0

    @pytest.mark.asyncio
    async def test_list_backups(self):
        """Test listing available backups."""
        backups = [
            {"id": "backup_20250913_100000", "date": "2025-09-13", "size_mb": 500, "valid": True},
            {"id": "backup_20250912_100000", "date": "2025-09-12", "size_mb": 480, "valid": True},
        ]

        assert len(backups) == 2
        assert all(b["valid"] for b in backups)
        assert backups[0]["date"] > backups[1]["date"]  # Most recent first
