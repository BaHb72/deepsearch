"""
MiniQMT ConnectionGuard 测试套件

测试连接状态守卫功能：
- 连接状态管理
- 日志节流
- 自动恢复探测
- 状态重置
"""

import time

import pytest

from deepsearch.infrastructure.providers.implementations.qmt.connection_guard import (
    MiniQMTConnectionGuard,
)


class TestConnectionGuardBasic:
    """ConnectionGuard 基础功能测试"""

    def setup_method(self):
        """每个测试前重置状态"""
        MiniQMTConnectionGuard.reset()

    def test_initial_state(self):
        """测试初始状态"""
        status = MiniQMTConnectionGuard.get_status()

        assert status["is_available"] is None
        assert status["consecutive_failures"] == 0
        assert status["suppressed_log_count"] == 0
        assert status["first_check_done"] is False

    def test_should_attempt_connection_initial(self):
        """测试初始时应该尝试连接"""
        result = MiniQMTConnectionGuard.should_attempt_connection()
        assert result is True

    def test_mark_available(self):
        """测试标记服务可用"""
        MiniQMTConnectionGuard.mark_available()

        assert MiniQMTConnectionGuard.is_available() is True
        assert MiniQMTConnectionGuard.get_status()["consecutive_failures"] == 0

    def test_mark_unavailable(self):
        """测试标记服务不可用"""
        MiniQMTConnectionGuard.mark_unavailable()

        assert MiniQMTConnectionGuard.is_available() is False
        assert MiniQMTConnectionGuard.get_status()["consecutive_failures"] == 1

    def test_consecutive_failures(self):
        """测试连续失败计数"""
        for i in range(5):
            MiniQMTConnectionGuard.mark_unavailable()

        assert MiniQMTConnectionGuard.get_status()["consecutive_failures"] == 5

    def test_reset(self):
        """测试状态重置"""
        MiniQMTConnectionGuard.mark_unavailable()
        MiniQMTConnectionGuard.mark_unavailable()

        MiniQMTConnectionGuard.reset()

        status = MiniQMTConnectionGuard.get_status()
        assert status["is_available"] is None
        assert status["consecutive_failures"] == 0


class TestConnectionGuardThrottling:
    """ConnectionGuard 连接尝试节流测试"""

    def setup_method(self):
        """每个测试前重置状态"""
        MiniQMTConnectionGuard.reset()
        # 直接设置内部变量绕过最小值限制（仅用于测试）
        MiniQMTConnectionGuard._check_interval = 0.5

    def teardown_method(self):
        """每个测试后恢复默认间隔"""
        MiniQMTConnectionGuard._check_interval = 300

    def test_should_not_attempt_when_unavailable(self):
        """测试服务不可用时不应立即尝试连接"""
        MiniQMTConnectionGuard.mark_unavailable()

        # 立即检查应该返回 False
        result = MiniQMTConnectionGuard.should_attempt_connection()
        assert result is False

    def test_should_attempt_after_interval(self):
        """测试间隔后应该重新尝试"""
        MiniQMTConnectionGuard.mark_unavailable()

        # 等待超过检测间隔 (0.5秒)
        time.sleep(0.6)

        result = MiniQMTConnectionGuard.should_attempt_connection()
        assert result is True

    def test_should_always_attempt_when_available(self):
        """测试服务可用时总是允许连接"""
        MiniQMTConnectionGuard.mark_available()

        for _ in range(10):
            result = MiniQMTConnectionGuard.should_attempt_connection()
            assert result is True


class TestConnectionGuardLogging:
    """ConnectionGuard 日志节流测试"""

    def setup_method(self):
        """每个测试前重置状态"""
        MiniQMTConnectionGuard.reset()
        # 直接设置内部变量绕过最小值限制（仅用于测试）
        MiniQMTConnectionGuard._error_log_interval = 0.5
        # 模拟已经进行过首次检测（触发 _first_check_done = True）
        MiniQMTConnectionGuard._first_check_done = True

    def teardown_method(self):
        """每个测试后恢复默认间隔"""
        MiniQMTConnectionGuard._error_log_interval = 300

    def test_first_error_always_logged(self):
        """测试首次错误总是记录（在首次检测后）"""
        result = MiniQMTConnectionGuard.log_connection_error("测试错误")
        assert result is True

    def test_repeated_errors_suppressed(self):
        """测试重复错误被抑制"""
        # 首次记录
        result1 = MiniQMTConnectionGuard.log_connection_error("错误1")
        assert result1 is True

        # 立即再次调用应该被抑制
        result2 = MiniQMTConnectionGuard.log_connection_error("错误2")
        assert result2 is False

        # 检查抑制计数
        assert MiniQMTConnectionGuard.get_status()["suppressed_log_count"] == 1

    def test_error_logged_after_interval(self):
        """测试间隔后错误会被记录"""
        MiniQMTConnectionGuard.log_connection_error("错误1")

        # 等待超过日志间隔 (0.5秒)
        time.sleep(0.6)

        result = MiniQMTConnectionGuard.log_connection_error("错误2")
        assert result is True


class TestConnectionGuardRecovery:
    """ConnectionGuard 恢复检测测试"""

    def setup_method(self):
        """每个测试前重置状态"""
        MiniQMTConnectionGuard.reset()

    def test_recovery_from_unavailable(self):
        """测试从不可用状态恢复"""
        # 模拟连续失败
        for _ in range(3):
            MiniQMTConnectionGuard.mark_unavailable()

        assert MiniQMTConnectionGuard.is_available() is False

        # 模拟恢复
        MiniQMTConnectionGuard.mark_available()

        assert MiniQMTConnectionGuard.is_available() is True
        assert MiniQMTConnectionGuard.get_status()["consecutive_failures"] == 0


class TestConnectionGuardConfiguration:
    """ConnectionGuard 配置测试"""

    def setup_method(self):
        """每个测试前重置状态"""
        MiniQMTConnectionGuard.reset()

    def test_set_check_interval_minimum(self):
        """测试检测间隔最小值限制"""
        MiniQMTConnectionGuard.set_check_interval(10)  # 低于30秒最小值

        status = MiniQMTConnectionGuard.get_status()
        assert status["check_interval"] == 30  # 应该被限制为30秒

    def test_set_check_interval_valid(self):
        """测试设置有效的检测间隔"""
        MiniQMTConnectionGuard.set_check_interval(120)

        status = MiniQMTConnectionGuard.get_status()
        assert status["check_interval"] == 120


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
