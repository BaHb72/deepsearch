#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证 AmazingData 接口扩展
检查接口签名是否正确添加了 begin_date 和 end_date 参数
"""

import inspect
import sys

sys.path.insert(0, "d:/Stock/code/deepsearch")

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_extended import (
    ProcessIsolatedAmazingDataProvider,
)


def verify_method_signature(cls, method_name, expected_params):
    """验证方法签名"""
    if not hasattr(cls, method_name):
        print(f"[FAIL] {method_name}: 方法不存在")
        return False

    method = getattr(cls, method_name)
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())

    print(f"检查方法: {method_name}")
    print(f"  参数列表: {params}")

    for param in expected_params:
        if param not in params:
            print(f"  [FAIL] 缺少参数: {param}")
            return False

    print("  [OK] 所有必需参数存在")
    return True


def main():
    print("验证 AmazingData 接口扩展\\n")
    print("=" * 60)

    results = []

    # 验证 get_profit_express
    print("\\n1. 验证 get_profit_express")
    print("-" * 60)
    result = verify_method_signature(
        ProcessIsolatedAmazingDataProvider,
        "get_profit_express",
        ["code_list", "local_path", "is_local", "begin_date", "end_date"],
    )
    results.append(("get_profit_express", result))

    # 验证 get_profit_notice
    print("\\n2. 验证 get_profit_notice")
    print("-" * 60)
    result = verify_method_signature(
        ProcessIsolatedAmazingDataProvider,
        "get_profit_notice",
        ["code_list", "local_path", "is_local", "begin_date", "end_date"],
    )
    results.append(("get_profit_notice", result))

    # 验证 get_share_holder
    print("\\n3. 验证 get_share_holder")
    print("-" * 60)
    result = verify_method_signature(
        ProcessIsolatedAmazingDataProvider,
        "get_share_holder",
        ["code_list", "local_path", "is_local", "begin_date", "end_date"],
    )
    results.append(("get_share_holder", result))

    # 验证 get_holder_num
    print("\\n4. 验证 get_holder_num")
    print("-" * 60)
    result = verify_method_signature(
        ProcessIsolatedAmazingDataProvider,
        "get_holder_num",
        ["code_list", "local_path", "is_local", "begin_date", "end_date"],
    )
    results.append(("get_holder_num", result))

    # 验证 get_equity_structure
    print("\\n5. 验证 get_equity_structure")
    print("-" * 60)
    result = verify_method_signature(
        ProcessIsolatedAmazingDataProvider,
        "get_equity_structure",
        ["code_list", "local_path", "is_local", "begin_date", "end_date"],
    )
    results.append(("get_equity_structure", result))

    # 汇总结果
    print("\\n" + "=" * 60)
    print("验证结果汇总:")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    for method, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status} - {method}")

    print(f"\\n总计: {passed}/{len(results)} 通过")

    if passed == len(results):
        print("\\n接口扩展验证成功！")
        return 0
    else:
        print("\\n部分接口验证失败，请检查实现")
        return 1


if __name__ == "__main__":
    sys.exit(main())
