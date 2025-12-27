#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速测试 AmazingData 扩展接口
测试 ETF、指数和行业相关的新增/更新接口
"""

import os
import sys

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入验证脚本
from verify_amazingdata_api import (
    logout,
    test_get_fund_iopv,
    test_get_fund_share,
    test_get_index_constituent,
    test_get_index_weight,
    test_get_industry_base_info,
)


def main():
    """测试新增和更新的接口"""
    print("=" * 80)
    print("  AmazingData 扩展接口测试")
    print("  测试 ETF、指数和行业相关接口")
    print("=" * 80)
    print()

    tests = [
        ("get_fund_share (ETF基金份额)", test_get_fund_share),
        ("get_fund_iopv (ETF每日收益)", test_get_fund_iopv),
        ("get_index_constituent (指数成分股)", test_get_index_constituent),
        ("get_index_weight (指数成分股权重)", test_get_index_weight),
        ("get_industry_base_info (行业指数基本信息)", test_get_industry_base_info),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        print(f"\n{'='*80}")
        print(f"测试: {name}")
        print("=" * 80)
        try:
            if test_func():
                passed += 1
                print(f"✓ {name} 测试通过")
            else:
                failed += 1
                print(f"✗ {name} 测试失败")
        except Exception as e:
            failed += 1
            print(f"✗ {name} 测试异常: {e}")
            import traceback

            traceback.print_exc()

    # 登出
    logout()

    # 打印总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"总计: {len(tests)} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    print(f"成功率: {passed/len(tests)*100:.1f}%")
    print("=" * 80)

    # 返回状态码
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
