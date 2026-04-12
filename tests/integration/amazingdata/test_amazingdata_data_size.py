"""AmazingData 数据量手动测试（通过子进程隔离原生 SDK 崩溃风险）。"""

import importlib.util
import json
import os
import subprocess
import sys
import textwrap

import pytest

pytestmark = pytest.mark.manual(reason="需要手动环境和凭证")

if importlib.util.find_spec("AmazingData") is None:
    pytest.skip("AmazingData 未安装", allow_module_level=True)

if not os.getenv("RUN_MANUAL_TESTS"):
    pytest.skip(
        "手动测试默认跳过；设置 RUN_MANUAL_TESTS=1 后运行。",
        allow_module_level=True,
    )


def test_amazingdata_data_size_manual_subprocess() -> None:
    """在子进程执行真实 SDK 调用，避免原生层崩溃拖垮 pytest 主进程。"""
    username = os.getenv("AMAZINGDATA_USERNAME", "")
    password = os.getenv("AMAZINGDATA_PASSWORD", "")
    host = os.getenv("AMAZINGDATA_HOST", "101.230.159.234")
    port = os.getenv("AMAZINGDATA_PORT", "8600")

    if not username or not password:
        pytest.skip("缺少 AMAZINGDATA_USERNAME/AMAZINGDATA_PASSWORD，跳过手动真实测试")

    probe_code = textwrap.dedent("""
        import json
        import time

        import AmazingData as ad
        import pandas as pd

        username = {username!r}
        password = {password!r}
        host = {host!r}
        port = int({port!r})

        start_login = time.time()
        login_result = ad.login(username, password, host, port)
        if login_result not in (0, True):
            raise RuntimeError(f"login failed: {login_result}")

        base_data = ad.BaseData()

        start_info = time.time()
        code_info = base_data.get_code_info("EXTRA_STOCK_A")
        info_elapsed = time.time() - start_info

        info_rows = None
        info_cols = None
        info_mem_mb = None
        sample_json_kb = None
        if isinstance(code_info, pd.DataFrame):
            info_rows = len(code_info)
            info_cols = len(code_info.columns)
            info_mem_mb = float(code_info.memory_usage(deep=True).sum()) / 1024 / 1024
            sample_json_kb = len(code_info.head(10).to_json()) / 1024

        start_cal = time.time()
        calendar = base_data.get_trading_calendar("20240101", "20240131")
        cal_elapsed = time.time() - start_cal

        ad.logout(username)

        payload = {
            "login_elapsed_sec": round(time.time() - start_login, 3),
            "code_info_elapsed_sec": round(info_elapsed, 3),
            "calendar_elapsed_sec": round(cal_elapsed, 3),
            "code_info_rows": info_rows,
            "code_info_cols": info_cols,
            "code_info_mem_mb": None if info_mem_mb is None else round(info_mem_mb, 3),
            "sample_json_kb": None if sample_json_kb is None else round(sample_json_kb, 3),
            "calendar_len": None if calendar is None else len(calendar),
        }
        print(json.dumps(payload, ensure_ascii=False))
        """).format(username=username, password=password, host=host, port=port)

    completed = subprocess.run(
        [sys.executable, "-c", probe_code],
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert completed.returncode == 0, (
        "AmazingData 手动数据量测试失败\n"
        f"returncode={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )

    stdout = completed.stdout.strip()
    assert stdout, "子进程未输出任何结果"
    metrics = json.loads(stdout.splitlines()[-1])
    assert "code_info_elapsed_sec" in metrics
