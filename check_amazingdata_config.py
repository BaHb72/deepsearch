"""
检查AmazingData config模块
"""
import AmazingData as ad

print("AmazingData.config 模块内容:")
print("=" * 60)

for attr in dir(ad.config):
    if not attr.startswith('_'):
        obj = getattr(ad.config, attr)
        print(f"  {attr}: {type(obj).__name__}")

print("\n检查environment模块:")
print("=" * 60)
for attr in dir(ad.environment):
    if not attr.startswith('_'):
        print(f"  {attr}")

# 检查是否需要在登录时传递服务器参数
import inspect

print("\n检查login函数签名:")
print("=" * 60)
sig = inspect.signature(ad.login)
print(f"  参数: {sig}")

# 尝试获取帮助
print("\nlogin函数文档:")
print("=" * 60)
if ad.login.__doc__:
    print(ad.login.__doc__)
else:
    print("  无文档")