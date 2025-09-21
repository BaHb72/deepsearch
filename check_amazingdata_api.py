"""
检查AmazingData SDK的API接口
"""
import AmazingData as ad

print("AmazingData SDK 可用的属性和方法:")
print("=" * 60)

for attr in dir(ad):
    if not attr.startswith('_'):
        obj = getattr(ad, attr)
        print(f"  {attr}: {type(obj).__name__}")

print("\n尝试创建实例:")
print("=" * 60)

# 尝试不同的初始化方式
try:
    print("\n1. 尝试 ad.AmazingData()...")
    client = ad.AmazingData()
    print("   成功!")
except Exception as e:
    print(f"   失败: {e}")

try:
    print("\n2. 尝试 ad.Client()...")
    client = ad.Client()
    print("   成功!")
except Exception as e:
    print(f"   失败: {e}")

try:
    print("\n3. 尝试 ad.DataClient()...")
    client = ad.DataClient()
    print("   成功!")
except Exception as e:
    print(f"   失败: {e}")

# 检查是否有login函数
if hasattr(ad, 'login'):
    print("\n发现 login 函数，可能是函数式API")

if hasattr(ad, 'Login'):
    print("\n发现 Login 类")

if hasattr(ad, 'connect'):
    print("\n发现 connect 函数")