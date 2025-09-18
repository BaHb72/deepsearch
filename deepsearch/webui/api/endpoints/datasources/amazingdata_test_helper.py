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


def test_amazingdata_connection(
    username: str,
    password: str,
    host: str = "101.230.159.234",
    port: int = 8600,
    test_type: str = "realtime"
) -> Dict[str, Any]:
    """
    测试AmazingData连接

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

    try:
        logger.info(f"[HELPER] 开始测试AmazingData连接: {username}@{host}:{port}")

        # 尝试导入AmazingData
        try:
            import AmazingData as ad
            logger.info("[HELPER] AmazingData SDK导入成功")
        except ImportError as e:
            logger.error(f"[HELPER] AmazingData SDK未安装: {e}")
            return create_test_result(
                success=False,
                message="测试失败",
                error="AmazingData SDK未安装，请先安装SDK",
                details={
                    "install_command": "pip install installer/AmazingData-1.0.9-cp313-none-any.whl",
                    "import_error": str(e)
                },
                latency_ms=(time.time() - start_time) * 1000
            )

        # 尝试登录
        try:
            logger.info(f"[HELPER] 尝试登录到 {host}:{port}")
            login_result = ad.login(
                username=username,
                password=password,
                host=host,
                port=port
            )

            if login_result == 0 or login_result is True:
                logger.info("[HELPER] 登录成功")


                logger.info("[HELPER] 登录验证成功")

                # 立即登出并返回成功
                try:
                    ad.logout(username)
                    logger.info("[HELPER] 登出成功")
                except Exception as logout_error:
                    logger.warning(f"[HELPER] 登出时出错: {logout_error}")

                return create_test_result(
                    success=True,
                    message="测试成功",
                    details={
                        "server": f"{host}:{port}",
                        "username": username,
                        "test_type": "connection",
                        "note": "连接验证成功，数据获取请使用具体的API接口"
                    },
                    latency_ms=(time.time() - start_time) * 1000,
                    data_size=0
                )
            else:
                logger.error(f"[HELPER] 登录失败: {login_result}")
                return create_test_result(
                    success=False,
                    message="测试失败",
                    error=f"登录失败，错误码: {login_result}",
                    details={
                        "server": f"{host}:{port}",
                        "login_result": login_result
                    },
                    latency_ms=(time.time() - start_time) * 1000
                )

        except Exception as e:
            logger.error(f"[HELPER] 登录过程异常: {e}")
            error_msg = str(e)

            # 检查并替换历史错误信息
            if "does not support realtime" in error_msg.lower():
                error_msg = "无法连接到AmazingData服务器，请检查网络和凭证"

            return create_test_result(
                success=False,
                message="测试失败",
                error=error_msg,
                details={
                    "server": f"{host}:{port}",
                    "exception": type(e).__name__
                },
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