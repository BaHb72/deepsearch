# encoding:utf-8
"""
AmazingData 真实登录与只读接口探测脚本。

探测在独立子进程中执行，用于隔离 AmazingData/TGW SDK 可能触发的 stdout 输出、
SystemExit 或进程退出行为。脚本只输出脱敏后的阶段结果，不输出密码或 SDK 原始登录明细。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("packages/core/config/settings.dev.yaml")
DEFAULT_SECURITY_TYPE = "EXTRA_STOCK_A_SH_SZ"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="探测 AmazingData 登录和只读基础接口")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="配置文件路径，默认 packages/core/config/settings.dev.yaml",
    )
    parser.add_argument("--username", default=os.getenv("AMAZINGDATA_USERNAME"))
    parser.add_argument("--password", default=os.getenv("AMAZINGDATA_PASSWORD"))
    parser.add_argument("--host", default=os.getenv("AMAZINGDATA_HOST"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("AMAZINGDATA_PORT", "0") or "0"),
    )
    parser.add_argument(
        "--security-type",
        default=os.getenv("AMAZINGDATA_SECURITY_TYPE", DEFAULT_SECURITY_TYPE),
        help="BaseData.get_code_list 的 security_type 参数",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("AMAZINGDATA_PROBE_TIMEOUT", "90")),
        help="子进程探测超时时间（秒）",
    )
    parser.add_argument(
        "--python-interpreter",
        default=sys.executable,
        help="执行子进程探测的 Python 解释器，默认当前解释器",
    )
    parser.add_argument(
        "--require-rows",
        action="store_true",
        help="要求 get_code_list 至少返回一行；默认只验证接口可返回",
    )
    return parser.parse_args()


def _load_config_credentials(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}

    settings = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    try:
        provider = settings["data_sources"]["providers"]["amazingdata"]
        connection = provider["config"]["connection"]
    except KeyError, TypeError:
        return {}

    return {
        "username": connection.get("username"),
        "password": connection.get("password"),
        "host": connection.get("host"),
        "port": connection.get("port"),
        "enabled": provider.get("enabled"),
    }


def _resolve_credentials(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.config)
    config_values = _load_config_credentials(config_path)
    return {
        "config_path": str(config_path),
        "enabled": bool(config_values.get("enabled")),
        "username": args.username or config_values.get("username") or "",
        "password": args.password or config_values.get("password") or "",
        "host": args.host or config_values.get("host") or "",
        "port": args.port or int(config_values.get("port") or 0),
    }


def _child_code() -> str:
    return r"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


stage_path = Path(os.environ["DEEPSEARCH_PROBE_STAGE"])


def write(stage: str, **data: Any) -> None:
    existing = []
    if stage_path.exists():
        try:
            existing = json.loads(stage_path.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing.append({"stage": stage, **data})
    stage_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


try:
    username = os.environ.get("DEEPSEARCH_AD_USERNAME", "").strip()
    password = os.environ.get("DEEPSEARCH_AD_PASSWORD", "").strip()
    host = os.environ.get("DEEPSEARCH_AD_HOST", "").strip()
    port = int(os.environ.get("DEEPSEARCH_AD_PORT", "0") or "0")
    security_type = os.environ.get("DEEPSEARCH_AD_SECURITY_TYPE", "EXTRA_STOCK_A_SH_SZ")
    write(
        "config_loaded",
        username_present=bool(username),
        password_present=bool(password),
        host_present=bool(host),
        port=port,
    )

    import AmazingData as ad

    write(
        "sdk_imported",
        sdk_version=getattr(ad, "__version__", None),
        has_login=callable(getattr(ad, "login", None)),
        has_base_data=callable(getattr(ad, "BaseData", None)),
        has_market_data=callable(getattr(ad, "MarketData", None)),
        has_info_data=callable(getattr(ad, "InfoData", None)),
    )

    login_result = ad.login(username=username, password=password, host=host, port=port)
    login_success = bool(login_result or login_result == 0)
    write("login_returned", login_success=login_success)
    if not login_success:
        raise RuntimeError("AmazingData login failed")

    base = ad.BaseData()
    info = ad.InfoData()
    write("instances_created", base=type(base).__name__, info=type(info).__name__)

    payload = base.get_code_list(security_type=security_type)
    rows = int(getattr(payload, "shape", [0])[0]) if payload is not None else 0
    write("get_code_list_returned", rows=rows, payload_type=type(payload).__name__)
except BaseException as exc:
    write("error", error_type=type(exc).__name__, error=str(exc)[:300])
    raise
"""


def _build_missing_credentials_report(credentials: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "skipped_missing_credentials",
        "config": {
            "path": credentials["config_path"],
            "enabled": credentials["enabled"],
            "username_present": bool(credentials["username"]),
            "password_present": bool(credentials["password"]),
            "host_present": bool(credentials["host"]),
            "port": credentials["port"],
        },
    }


def run_probe(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    credentials = _resolve_credentials(args)
    if not all(
        [
            credentials["username"],
            credentials["password"],
            credentials["host"],
            credentials["port"],
        ]
    ):
        return 2, _build_missing_credentials_report(credentials)

    stage_file = Path(tempfile.gettempdir()) / "deepsearch_amazingdata_probe_stage.json"
    stage_file.unlink(missing_ok=True)

    env = os.environ.copy()
    env.update(
        {
            "DEEPSEARCH_PROBE_STAGE": str(stage_file),
            "DEEPSEARCH_AD_USERNAME": str(credentials["username"]),
            "DEEPSEARCH_AD_PASSWORD": str(credentials["password"]),
            "DEEPSEARCH_AD_HOST": str(credentials["host"]),
            "DEEPSEARCH_AD_PORT": str(credentials["port"]),
            "DEEPSEARCH_AD_SECURITY_TYPE": str(args.security_type),
        }
    )

    try:
        completed = subprocess.run(
            [args.python_interpreter, "-c", _child_code()],
            cwd=Path.cwd(),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max(float(args.timeout), 1.0),
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        stages = _read_stages(stage_file)
        return 1, {
            "status": "timeout",
            "timeout_seconds": args.timeout,
            "stages": stages,
        }

    stages = _read_stages(stage_file)
    stage_file.unlink(missing_ok=True)

    report: dict[str, Any] = {
        "status": _resolve_status(completed.returncode, stages, args.require_rows),
        "returncode": completed.returncode,
        "sdk_output_captured": bool(completed.stdout),
        "sdk_error_output_captured": bool(completed.stderr),
        "stages": stages,
    }
    exit_code = 0 if report["status"] == "ok" else 1
    return exit_code, report


def _read_stages(stage_file: Path) -> list[dict[str, Any]]:
    if not stage_file.exists():
        return []
    try:
        payload = json.loads(stage_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _resolve_status(returncode: int, stages: list[dict[str, Any]], require_rows: bool) -> str:
    if not stages:
        return "missing_stage_report"
    last = stages[-1]
    if last.get("stage") == "get_code_list_returned":
        if require_rows and int(last.get("rows") or 0) <= 0:
            return "empty_result"
        return "ok"
    if returncode == 0:
        return "early_exit"
    return "failed"


def main() -> None:
    args = parse_args()
    exit_code, report = run_probe(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
