"""
凭据读取工具
从配置文件读取 AmazingData 连接信息，避免硬编码密码
"""

import sys
from pathlib import Path

# 确保项目路径在 sys.path 中
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def get_amazingdata_credentials() -> dict:
    """
    从配置文件读取 AmazingData 凭据

    Returns:
        dict: 包含 username, password, host, port 的字典
    """
    from core.config import get_config

    config = get_config()
    ad_config = config.amazingdata.connection

    return {
        "username": ad_config.username,
        "password": ad_config.password,
        "host": ad_config.host,
        "port": ad_config.port,
        "timeout": getattr(ad_config, "timeout", 5000),
    }


def get_amazingdata_connection_config():
    """
    获取 AmazingData 连接配置对象

    Returns:
        AmazingDataConnectionConfig 对象
    """
    from core.config import get_config

    config = get_config()
    return config.amazingdata.connection
