"""测试专用的 AmazingData Stub"""

from typing import Any, Dict

_logged_in_users = set()


def login(username: str, password: str, host: str, port: int) -> int:
    _logged_in_users.add(username)
    return 0  # 与真实 SDK 对齐：0 表示成功


def logout(username: str) -> bool:
    _logged_in_users.discard(username)
    return True


def health_check() -> Dict[str, Any]:
    return {"status": "ok", "logged_in": list(_logged_in_users)}


def fetch_basic_data(*args, **kwargs) -> Dict[str, Any]:
    return {"data": [], "args": args, "kwargs": kwargs}


def get_version() -> str:
    return "amazingdata-stub-1.0"
