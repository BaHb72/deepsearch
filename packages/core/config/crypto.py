"""
密码加密工具

提供密码的加密和解密功能，用于保护敏感信息。
配置文件中可以存储加密后的密码，格式为: "encrypted:xxxxx"
"""

import base64
import binascii
from pathlib import Path
from typing import TYPE_CHECKING, Optional, cast

from core.observability import logger
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

if TYPE_CHECKING:
    from loguru import Logger

module_logger = cast("Logger", logger)


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
    def _generate_key_from_password(password: bytes, salt: bytes = b"deepsearch-salt") -> bytes:
        """从密码生成密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        derived_key = kdf.derive(password)
        return cast(bytes, derived_key)

    @staticmethod
    def generate_key() -> str:
        """生成新的加密密钥"""
        key_bytes = cast(bytes, Fernet.generate_key())
        return key_bytes.decode()

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
            decrypted_bytes = cast(bytes, self._cipher.decrypt(encrypted_bytes))
            return decrypted_bytes.decode()
        except (ValueError, binascii.Error) as e:
            # Base64 解码失败，可能是明文密码
            module_logger.debug(f"密码解码失败，可能是明文: {type(e).__name__}")
            return encrypted_password
        except Exception as e:
            # 其他解密错误，如 InvalidToken
            module_logger.warning(f"密码解密失败: {type(e).__name__}")
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
