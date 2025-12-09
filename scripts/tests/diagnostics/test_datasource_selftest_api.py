"""
诊断脚本：调用 WebUI `/api/data-sources/test/{source}` 接口，复现自检 500 错误。

使用方式：
    uv run python scripts/tests/diagnostics/test_datasource_selftest_api.py --source akshare
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

from fastapi.testclient import TestClient
from loguru import logger

os.environ.setdefault("APP__ENV", "dev")


def run_self_test(source: str, payload: Dict[str, Any]) -> None:
    from deepsearch.webui.server import create_app

    app = create_app()
    with TestClient(app) as client:
        logger.info("POST /api/data-sources/test/{} payload={}", source, payload)
        response = client.post(
            f"/api/data-sources/test/{source}",
            json=payload or None,
        )

        logger.info("HTTP {} 响应体:\n{}", response.status_code,
                    json.dumps(response.json(), ensure_ascii=False, indent=2))
        if response.status_code >= 500:
            logger.error("接口返回 500，需检查 `response_payload` 未初始化或后端测试逻辑。")
        else:
            logger.success("自检通过。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="测试数据源自检接口。")
    parser.add_argument("--source", default="akshare", help="要测试的数据源标识")
    parser.add_argument(
        "--payload",
        default="{}",
        help="JSON 格式的临时配置覆盖，例如 '{\"timeout\": 10}'",
    )
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.payload) if args.payload else {}
    except json.JSONDecodeError as exc:  # pragma: no cover - 诊断脚本保留原始异常
        logger.error("payload 解析失败: {}", exc)
        return 1

    run_self_test(args.source, payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
