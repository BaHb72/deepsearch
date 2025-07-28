#!/usr/bin/env python
"""
密码加密工具

用于将明文密码加密后存储到配置文件中。

使用方法：
    python -m deepsearch.tools.encrypt_password
    
或者：
    python encrypt_password.py
"""
import sys
from pathlib import Path
import getpass

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from deepsearch.config.crypto import PasswordCrypto, generate_crypto_key


def main():
    """主函数"""
    print("DeepSearch 密码加密工具")
    print("=" * 50)

    # 检查是否存在密钥文件
    key_file = Path("config/.crypto_key")

    if not key_file.exists():
        print("\n首次使用，需要生成加密密钥...")
        response = input("是否生成新的加密密钥？(y/n): ")

        if response.lower() == 'y':
            # 生成新密钥
            new_key = generate_crypto_key()

            # 创建config目录（如果不存在）
            key_file.parent.mkdir(exist_ok=True)

            # 保存密钥
            key_file.write_text(new_key)
            print(f"✓ 密钥已保存到: {key_file}")
            print("⚠️  请妥善保管此文件，丢失后无法解密密码！")
        else:
            print("已取消操作")
            return

    # 创建加密工具
    crypto = PasswordCrypto()

    while True:
        print("\n请选择操作：")
        print("1. 加密密码")
        print("2. 解密密码（测试）")
        print("3. 退出")

        choice = input("请输入选择 (1-3): ")

        if choice == '1':
            # 加密密码
            password = getpass.getpass("请输入要加密的密码: ")
            if password:
                encrypted = crypto.encrypt(password)
                print(f"\n加密后的密码：")
                print(f"encrypted:{encrypted}")
                print("\n将上面的内容（包括 'encrypted:' 前缀）复制到配置文件的 password 字段")
            else:
                print("密码不能为空")

        elif choice == '2':
            # 解密密码
            encrypted = input("请输入加密的密码（包括 'encrypted:' 前缀）: ")
            if encrypted.startswith("encrypted:"):
                try:
                    encrypted_part = encrypted[10:]
                    decrypted = crypto.decrypt(encrypted_part)
                    print(f"解密后的密码: {decrypted}")
                except Exception as e:
                    print(f"解密失败: {e}")
            else:
                print("加密密码必须以 'encrypted:' 开头")

        elif choice == '3':
            print("再见！")
            break
        else:
            print("无效的选择")


if __name__ == "__main__":
    main()
