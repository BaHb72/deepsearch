#!/usr/bin/env python
"""校验本地 SDK wheel 文件是否与锁定依赖匹配。"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

EXPECTED_WHEELS = {
    "AmazingData-1.1.0-cp314-none-any.whl": (
        "6792e9b871366f1300c0881dd50f47fe72e0a3398f33e8a09693c133a01506d8"
    ),
    "tgw-1.0.8.6-py3-none-any.whl": (
        "2009f468f4f9d032ce88a333e002f5708e538cdad16adad330fb05b1971bff39"
    ),
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_wheels(wheel_dir: Path) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    wheel_dir = wheel_dir.resolve()

    if not wheel_dir.exists():
        errors.append(f"wheel 目录不存在: {wheel_dir}")
    elif not wheel_dir.is_dir():
        errors.append(f"wheel 路径不是目录: {wheel_dir}")

    found_names = {path.name for path in wheel_dir.glob("*.whl")} if wheel_dir.is_dir() else set()
    expected_names = set(EXPECTED_WHEELS)

    for name in sorted(expected_names - found_names):
        errors.append(f"缺少本地 wheel: {wheel_dir / name}")

    for name in sorted(found_names - expected_names):
        warnings.append(f"发现未声明的 wheel，已忽略: {wheel_dir / name}")

    for name, expected_hash in EXPECTED_WHEELS.items():
        wheel_path = wheel_dir / name
        if not wheel_path.exists():
            continue
        actual_hash = _sha256(wheel_path)
        if actual_hash != expected_hash:
            errors.append(
                f"wheel sha256 不匹配: {wheel_path}\n"
                f"  expected: {expected_hash}\n"
                f"  actual:   {actual_hash}"
            )

    if errors:
        print("[FAIL] 本地 SDK wheel 校验失败")
        for error in errors:
            print(f"- {error}")
        print("请将匹配 pyproject.toml 中 uv.sources 的 wheel 放入目标目录后重试。")
        return 1

    print(f"[PASS] 本地 SDK wheel 校验通过: {wheel_dir}")
    for warning in warnings:
        print(f"[WARN] {warning}")
    for name in sorted(EXPECTED_WHEELS):
        print(f"- {name}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="校验本地 SDK wheel 文件")
    parser.add_argument(
        "--wheel-dir",
        type=Path,
        default=_repo_root() / "packages",
        help="wheel 所在目录，默认检查仓库 packages/",
    )
    args = parser.parse_args()
    sys.exit(check_wheels(args.wheel_dir))


if __name__ == "__main__":
    main()
