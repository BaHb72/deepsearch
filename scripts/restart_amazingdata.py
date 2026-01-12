from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(
        description="重启 AmazingData 进程池（停止所有 Worker，下次使用时自动重建）"
    )
    parser.add_argument("env", choices=["dev", "prod"], nargs="?", default="prod")
    args = parser.parse_args()

    os.environ["APP__ENV"] = args.env
    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_pool import (
        shutdown_pool,
    )

    print(f"正在停止 AmazingData 进程池 (env={args.env}) …")
    shutdown_pool()
    print("[OK] 已停止 AmazingData 进程池；下次调用会自动拉起新 Worker")


if __name__ == "__main__":
    main()
