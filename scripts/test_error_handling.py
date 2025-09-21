#!/usr/bin/env python
"""
测试错误处理修复
"""

import requests
import json

# 测试后端API的验证错误处理
def test_validation_error():
    """测试FastAPI的ValidationError处理"""
    print("测试ValidationError处理...")

    # 发送一个会触发验证错误的请求
    # 假设有一个需要特定参数的端点
    response = requests.post(
        "http://localhost:8000/api/data/query",
        json={
            # 故意发送错误格式的参数
            "invalid_field": "test",
            "missing_required_field": None
        }
    )

    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")

    # 检查响应格式
    if response.status_code == 422:
        data = response.json()
        if "detail" in data and isinstance(data["detail"], str):
            print("✅ ValidationError已正确格式化为字符串")
        else:
            print("❌ ValidationError格式不正确")
    else:
        print(f"⚠️ 未预期的状态码: {response.status_code}")


def test_general_error():
    """测试一般错误处理"""
    print("\n测试一般错误处理...")

    # 测试404错误
    response = requests.get("http://localhost:8000/api/nonexistent")
    print(f"404测试 - 状态码: {response.status_code}")
    print(f"404测试 - 响应: {response.json()}")


if __name__ == "__main__":
    print("开始测试错误处理修复...")
    print("=" * 50)

    try:
        test_validation_error()
        test_general_error()
        print("\n测试完成!")
    except Exception as e:
        print(f"测试失败: {e}")
        print("请确保后端服务正在运行")