"""
AmazingData测试辅助模块

提供AmazingData数据源的测试功能，包括错误处理和兼容性修复
"""
import time
from typing import Dict, Any, Optional
from loguru import logger


def create_test_result(
    success: bool = False,
    source: str = "amazingdata",
    message: str = "",
    error: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    latency_ms: float = 0,
    data_size: int = 0
) -> Dict[str, Any]:
    """
    创建标准的测试结果格式

    Args:
        success: 测试是否成功
        source: 数据源类型
        message: 测试消息
        error: 错误信息
        details: 详细信息
        latency_ms: 延迟（毫秒）
        data_size: 数据大小

    Returns:
        标准测试结果字典
    """
    result = {
        "success": success,
        "source": source,
        "message": message or ("测试成功" if success else "测试失败"),
        "latency_ms": latency_ms,
        "data_size": data_size,
        "error": error,
        "details": details or {}
    }

    # 清理None值
    if error is None:
        del result["error"]

    return result


def safe_logout(username: str) -> bool:
    """
    安全的logout包装，防止SDK的SystemExit影响主进程

    Args:
        username: 用户名

    Returns:
        bool: logout是否成功
    """
    import threading
    import time
    from loguru import logger

    # 用于存储logout结果
    result_holder = {'success': False, 'exception': None}

    def logout_in_thread():
        """在独立线程中执行logout"""
        try:
            # 导入AmazingData模块
            import AmazingData as ad
            # 执行logout
            ad.logout(username)
            result_holder['success'] = True
        except SystemExit as e:
            # SDK调用了exit，但我们认为logout成功
            logger.warning(f"[HELPER] SDK在logout时调用了exit: {e}")
            result_holder['success'] = True
        except Exception as e:
            logger.error(f"[HELPER] logout异常: {e}")
            result_holder['exception'] = e

    # 创建并启动线程
    thread = threading.Thread(target=logout_in_thread)
    thread.start()

    # 等待线程完成（最多5秒）
    thread.join(timeout=5)

    if thread.is_alive():
        logger.warning("[HELPER] logout操作超时")
        # 即使超时也认为logout成功（避免阻塞）
        return True

    if result_holder['exception']:
        logger.error(f"[HELPER] logout失败: {result_holder['exception']}")
        return False

    return result_holder['success']


def test_amazingdata_connection(
    username: str,
    password: str,
    host: str = "101.230.159.234",
    port: int = 8600,
    test_type: str = "realtime"
) -> Dict[str, Any]:
    """
    测试AmazingData连接（使用进程隔离）

    Args:
        username: 用户名
        password: 密码
        host: 服务器地址
        port: 端口
        test_type: 测试类型（realtime/history）

    Returns:
        测试结果
    """
    start_time = time.time()

    logger.info(f"[HELPER] 开始测试AmazingData连接: {username}@{host}:{port}")
    logger.info("[HELPER] 使用进程隔离代理，防止SDK崩溃影响主进程")

    try:
        # 使用安全包装器进行测试
        try:
            from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_safe_wrapper import (
                get_safe_wrapper
            )
            logger.info("[HELPER] 安全包装器导入成功")
        except ImportError as e:
            logger.error(f"[HELPER] 安全包装器导入失败: {e}")
            # 降级到旧方式（直接调用SDK，有崩溃风险）
            logger.warning("[HELPER] 降级到直接SDK调用模式（有崩溃风险）")

            try:
                import AmazingData as ad
                logger.info("[HELPER] AmazingData SDK导入成功")

                # 直接调用SDK（危险！）
                logger.warning("[HELPER] 警告：直接调用SDK可能导致进程崩溃")
                login_result = ad.login(
                    username=username,
                    password=password,
                    host=host,
                    port=port
                )

                if login_result == 0 or login_result is True:
                    logger.info("[HELPER] 登录成功")
                    return create_test_result(
                        success=True,
                        message="测试成功",
                        details={
                            "server": f"{host}:{port}",
                            "username": username,
                            "test_type": "connection",
                            "mode": "direct_sdk",
                            "warning": "使用直接SDK调用，存在崩溃风险"
                        },
                        latency_ms=(time.time() - start_time) * 1000,
                        data_size=0
                    )
                else:
                    return create_test_result(
                        success=False,
                        message="测试失败",
                        error=f"登录失败，错误码: {login_result}",
                        latency_ms=(time.time() - start_time) * 1000
                    )

            except ImportError:
                return create_test_result(
                    success=False,
                    message="测试失败",
                    error="AmazingData SDK未安装，请先安装SDK",
                    details={
                        "install_command": "pip install installer/AmazingData-1.0.9-cp313-none-any.whl"
                    },
                    latency_ms=(time.time() - start_time) * 1000
                )
            except SystemExit as e:
                logger.critical(f"[HELPER] SDK尝试退出进程: {e}")
                return create_test_result(
                    success=False,
                    message="测试失败",
                    error="SDK尝试终止进程（SystemExit），连接失败",
                    details={
                        "crash_type": "SystemExit",
                        "exit_code": str(e.code) if hasattr(e, 'code') else "unknown"
                    },
                    latency_ms=(time.time() - start_time) * 1000
                )

        # 使用安全包装器
        wrapper = get_safe_wrapper()

        logger.info(f"[HELPER] 尝试通过进程代理登录到 {host}:{port}")
        success, error = wrapper.safe_login(
            username=username,
            password=password,
            host=host,
            port=port,
            timeout=30.0
        )

        if success:
            logger.info("[HELPER] 登录成功")

            # 获取统计信息
            stats = wrapper.get_stats()

            # 自动登出（实际会跳过以避免崩溃）
            wrapper.safe_logout(username)

            return create_test_result(
                success=True,
                message="测试成功",
                details={
                    "server": f"{host}:{port}",
                    "username": username,
                    "test_type": "connection",
                    "mode": "process_proxy",
                    "note": "使用进程隔离代理，SDK崩溃不会影响主进程",
                    "stats": {
                        "crashes_handled": stats.get("crashes_handled", 0),
                        "proxy_restarts": stats.get("proxy_stats", {}).get("process_restarts", 0)
                    }
                },
                latency_ms=(time.time() - start_time) * 1000,
                data_size=0
            )
        else:
            logger.error(f"[HELPER] 登录失败: {error}")

            # 分析错误类型
            error_details = {
                "server": f"{host}:{port}",
                "username": username
            }

            if "SystemExit" in str(error):
                error_details["crash_type"] = "SystemExit"
                error_details["note"] = "SDK尝试退出但被进程代理拦截"
            elif "进程崩溃" in str(error):
                error_details["crash_type"] = "ProcessCrash"
                error_details["note"] = "工作进程崩溃但主进程安全"

            return create_test_result(
                success=False,
                message="测试失败",
                error=error or "登录失败",
                details=error_details,
                latency_ms=(time.time() - start_time) * 1000
            )

    except Exception as e:
        logger.error(f"[HELPER] 测试过程发生未知错误: {e}")
        return create_test_result(
            success=False,
            message="测试失败",
            error=f"未知错误: {str(e)}",
            latency_ms=(time.time() - start_time) * 1000
        )


def validate_amazingdata_config(config: Dict[str, Any]) -> tuple[bool, str]:
    """
    验证AmazingData配置

    Args:
        config: 配置字典

    Returns:
        (是否有效, 错误信息)
    """
    if not config.get("username"):
        return False, "缺少用户名"

    if not config.get("password"):
        return False, "缺少密码"

    # 验证网络提供商设置
    network_provider = config.get("networkProvider", "telecom")
    if network_provider not in ["telecom", "unicom", "custom"]:
        return False, f"无效的网络提供商: {network_provider}"

    # 如果是自定义，需要提供host和port
    if network_provider == "custom":
        if not config.get("host"):
            return False, "自定义网络需要提供服务器地址"
        if not config.get("port"):
            return False, "自定义网络需要提供端口号"

    return True, ""