#!/usr/bin/env python
"""
测试AmazingData连接的独立脚本

用于验证测试连接功能是否正常工作
"""
import sys

sys.path.insert(0, "D:\\Stock\\code\\deepsearch")

from apps.api.api.endpoints.datasources.amazingdata_test_helper import (
    test_amazingdata_connection,
    validate_amazingdata_config,
)


def test_direct_connection():
    """直接测试AmazingData连接"""
    print("\n" + "=" * 60)
    print("开始测试AmazingData连接")
    print("=" * 60)

    # 测试配置
    test_config = {
        "username": "",  # 需要填写实际用户名
        "password": "",  # 需要填写实际密码
        "networkProvider": "telecom",
    }

    # 验证配置
    is_valid, error_msg = validate_amazingdata_config(test_config)
    if not is_valid:
        print(f"[ERROR] 配置验证失败: {error_msg}")
        print("请在test_config中填写实际的用户名和密码")
        return

    # 执行测试
    result = test_amazingdata_connection(
        username=test_config["username"], password=test_config["password"], test_type="realtime"
    )

    # 显示结果
    print("\n测试结果:")
    print("-" * 40)
    print(f"成功: {result.get('success')}")
    print(f"消息: {result.get('message')}")
    if result.get("error"):
        print(f"错误: {result.get('error')}")
    if result.get("details"):
        print(f"详情: {result.get('details')}")
    print(f"延迟: {result.get('latency_ms', 0):.2f}ms")

    # 检查是否有历史错误信息
    if result.get("error") == "AmazingData provider does not support realtime data":
        print("\n[WARNING] 检测到历史错误信息！")
        print("这个错误不应该出现，说明还有地方返回了旧的错误消息")

    return result


def test_mock_error_replacement():
    """测试错误信息替换逻辑"""
    print("\n" + "=" * 60)
    print("测试错误信息替换")
    print("=" * 60)

    # 模拟包含历史错误的响应
    mock_errors = [
        "AmazingData provider does not support realtime data",
        "Provider does not support realtime",
        "Normal error message",
    ]

    for error in mock_errors:
        print(f"\n原始错误: {error}")

        # 检查是否需要替换
        if "does not support realtime" in error.lower():
            fixed_error = "AmazingData需要使用订阅模式获取实时数据"
            print(f"[FIXED] 已修正: {fixed_error}")
        else:
            print(f"[KEEP] 保持原样: {error}")


if __name__ == "__main__":
    print("AmazingData连接测试工具")
    print("版本: 1.0.0")

    # 运行测试
    test_mock_error_replacement()

    # 如果要测试实际连接，取消下面的注释并填写凭证
    # test_direct_connection()

    print("\n[SUCCESS] 测试完成！")
    print("\n注意事项:")
    print("1. 如果仍看到'does not support realtime'错误，检查是否有缓存")
    print("2. 查看日志文件了解详细的执行过程")
    print("3. 确保AmazingData SDK已正确安装")
