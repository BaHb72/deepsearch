"""
密码加密工具

提供密码的加密和解密功能，用于保护敏感信息。
配置文件中可以存储加密后的密码，格式为: "encrypted:xxxxx"
"""
import base64
import os
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class PasswordCrypto:
    """密码加密解密工具类"""

    def __init__(self, key: Optional[str] = None):
        """
        初始化加密工具
        
        Args:
            key: 加密密钥，如果不提供则从密钥文件读取
        """
        if key:
            self._key = key.encode()
        else:
            # 从密钥文件读取（如果存在）
            key_file = Path("config/.crypto_key")
            if key_file.exists():
                self._key = key_file.read_text().strip().encode()
            else:
                # 如果没有密钥文件，生成一个默认密钥（仅用于开发环境）
                self._key = self._generate_key_from_password(b"deepsearch-default-key")

        self._cipher = Fernet(base64.urlsafe_b64encode(self._key[:32]))

    @staticmethod
    def _generate_key_from_password(password: bytes, salt: bytes = b'deepsearch-salt') -> bytes:
        """从密码生成密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(password)

    @staticmethod
    def generate_key() -> str:
        """生成新的加密密钥"""
        return Fernet.generate_key().decode()

    def encrypt(self, password: str) -> str:
        """
        加密密码
        
        Args:
            password: 明文密码
            
        Returns:
            加密后的密码（base64编码）
        """
        if not password:
            return ""

        encrypted = self._cipher.encrypt(password.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, encrypted_password: str) -> str:
        """
        解密密码
        
        Args:
            encrypted_password: 加密的密码（base64编码）
            
        Returns:
            明文密码
        """
        if not encrypted_password:
            return ""

        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_password.encode())
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception:
            # 如果解密失败，可能是明文密码，直接返回
            return encrypted_password


# 全局加密工具实例
_crypto = PasswordCrypto()


def encrypt_password(password: str) -> str:
    """加密密码"""
    return _crypto.encrypt(password)


def decrypt_password(encrypted_password: str) -> str:
    """解密密码"""
    return _crypto.decrypt(encrypted_password)


def generate_crypto_key() -> str:
    """生成新的加密密钥"""
    return PasswordCrypto.generate_key()
