"""
文件编码处理工具

解决跨平台文件编码问题，特别是Windows的GBK编码问题
"""

import codecs
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import chardet

from deepsearch.observability import get_logger

logger = get_logger(__name__)


class EncodingDetector:
    """文件编码检测器"""

    # 常见编码列表（按优先级排序）
    COMMON_ENCODINGS = [
        "utf-8",
        "gbk",
        "gb2312",
        "gb18030",
        "utf-16",
        "utf-16le",
        "utf-16be",
        "big5",
        "shift_jis",
        "euc-jp",
        "euc-kr",
        "iso-8859-1",
        "windows-1252",
        "ascii",
    ]

    @staticmethod
    def detect_encoding(file_path: Union[str, Path], default: str = "utf-8") -> str:
        """
        检测文件编码

        Args:
            file_path: 文件路径
            default: 默认编码

        Returns:
            检测到的编码
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return default

        try:
            # 读取文件前几KB用于检测
            with open(file_path, "rb") as f:
                raw_data = f.read(4096)

            if not raw_data:
                return default

            # 使用chardet检测
            result = chardet.detect(raw_data)

            if result and result["encoding"]:
                encoding = result["encoding"].lower()
                confidence = result.get("confidence", 0)

                # 如果置信度高，使用检测结果
                if confidence > 0.8:
                    # 标准化编码名称
                    encoding_map: Dict[str, str] = {
                        "gb2312": "gbk",
                        "gb18030": "gbk",
                        "windows-1252": "iso-8859-1",
                        "ascii": "utf-8",  # ASCII是UTF-8的子集
                    }
                    mapped_encoding = encoding_map.get(encoding)
                    return mapped_encoding if mapped_encoding is not None else encoding

            # 置信度低，尝试常见编码
            for encoding in EncodingDetector.COMMON_ENCODINGS:
                try:
                    raw_data.decode(encoding)
                    return encoding
                except (UnicodeDecodeError, LookupError):
                    continue

        except Exception as e:
            logger.debug(f"编码检测失败: {e}")

        return default

    @staticmethod
    def is_binary_file(file_path: Union[str, Path]) -> bool:
        """
        检查是否为二进制文件

        Args:
            file_path: 文件路径

        Returns:
            是否为二进制文件
        """
        file_path = Path(file_path)

        # 检查文件扩展名
        binary_extensions = {
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".bin",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".mp3",
            ".mp4",
            ".avi",
            ".mov",
            ".zip",
            ".tar",
            ".gz",
            ".7z",
            ".rar",
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".pyc",
            ".pyo",
            ".whl",
        }

        if file_path.suffix.lower() in binary_extensions:
            return True

        # 读取文件开头检查
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(512)
                if not chunk:
                    return False

                # 检查是否包含NULL字节
                if b"\x00" in chunk:
                    return True

                # 检查非文本字符比例
                text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
                non_text = sum(1 for byte in chunk if byte not in text_chars)

                # 如果非文本字符超过30%，认为是二进制
                return non_text / len(chunk) > 0.3

        except Exception:
            return False


class SafeFileHandler:
    """安全的文件处理器"""

    @staticmethod
    def read_file(
        file_path: Union[str, Path],
        encoding: Optional[str] = None,
        errors: str = "replace",
        auto_detect: bool = True,
    ) -> str:
        """
        安全读取文件

        Args:
            file_path: 文件路径
            encoding: 指定编码
            errors: 错误处理方式 ('strict', 'ignore', 'replace')
            auto_detect: 是否自动检测编码

        Returns:
            文件内容
        """
        file_path = Path(file_path)

        # 自动检测编码
        if encoding is None and auto_detect:
            encoding = EncodingDetector.detect_encoding(file_path)
        elif encoding is None:
            encoding = "utf-8"

        try:
            with open(file_path, "r", encoding=encoding, errors=errors) as f:
                return f.read()
        except UnicodeDecodeError as e:
            logger.warning(f"使用 {encoding} 读取文件失败: {e}")

            # 尝试其他编码
            for fallback_encoding in EncodingDetector.COMMON_ENCODINGS:
                if fallback_encoding == encoding:
                    continue

                try:
                    with open(file_path, "r", encoding=fallback_encoding, errors=errors) as f:
                        logger.info(f"使用备用编码 {fallback_encoding} 成功读取文件")
                        return f.read()
                except UnicodeDecodeError:
                    continue

            # 所有编码都失败，使用二进制模式
            logger.error(f"无法解码文件 {file_path}，返回二进制内容的字符串表示")
            with open(file_path, "rb") as f:
                return str(f.read())

    @staticmethod
    def write_file(
        file_path: Union[str, Path],
        content: str,
        encoding: str = "utf-8",
        errors: str = "replace",
        ensure_dir: bool = True,
        backup: bool = False,
    ) -> None:
        """
        安全写入文件

        Args:
            file_path: 文件路径
            content: 文件内容
            encoding: 编码
            errors: 错误处理方式
            ensure_dir: 是否确保目录存在
            backup: 是否备份原文件
        """
        file_path = Path(file_path)

        # 确保目录存在
        if ensure_dir:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        # 备份原文件
        if backup and file_path.exists():
            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            file_path.rename(backup_path)
            logger.info(f"已备份原文件到 {backup_path}")

        # 写入文件
        try:
            with open(file_path, "w", encoding=encoding, errors=errors) as f:
                f.write(content)
        except UnicodeEncodeError as e:
            logger.error(f"使用 {encoding} 写入文件失败: {e}")

            # 尝试GBK（Windows常用）
            if encoding != "gbk" and sys.platform == "win32":
                try:
                    with open(file_path, "w", encoding="gbk", errors=errors) as f:
                        f.write(content)
                    logger.info("使用GBK编码成功写入文件")
                except UnicodeEncodeError:
                    # 最后尝试UTF-8 with BOM
                    with open(file_path, "wb") as f:
                        f.write(codecs.BOM_UTF8 + content.encode("utf-8", errors=errors))
                    logger.info("使用UTF-8 with BOM写入文件")

    @staticmethod
    def convert_encoding(
        file_path: Union[str, Path],
        target_encoding: str,
        source_encoding: Optional[str] = None,
        backup: bool = True,
    ) -> None:
        """
        转换文件编码

        Args:
            file_path: 文件路径
            target_encoding: 目标编码
            source_encoding: 源编码（None表示自动检测）
            backup: 是否备份原文件
        """
        file_path = Path(file_path)

        # 读取文件
        content = SafeFileHandler.read_file(file_path, encoding=source_encoding, auto_detect=True)

        # 写入新编码
        SafeFileHandler.write_file(file_path, content, encoding=target_encoding, backup=backup)

        logger.info(f"已将文件 {file_path} 转换为 {target_encoding} 编码")


class PlatformEncodingHelper:
    """平台相关的编码帮助器"""

    @staticmethod
    def get_default_encoding() -> str:
        """获取平台默认编码"""
        if sys.platform == "win32":
            # Windows默认使用GBK（中文版）
            import locale

            encoding = locale.getpreferredencoding(False)
            return "gbk" if encoding.lower().startswith("cp936") else encoding
        else:
            # Unix/Linux/Mac默认使用UTF-8
            return "utf-8"

    @staticmethod
    def get_console_encoding() -> str:
        """获取控制台编码"""
        if hasattr(sys.stdout, "encoding"):
            return sys.stdout.encoding or "utf-8"
        return "utf-8"

    @staticmethod
    def setup_console_encoding(encoding: str = "utf-8") -> None:
        """
        设置控制台编码

        Args:
            encoding: 目标编码
        """
        if sys.platform == "win32":
            # Windows特殊处理
            import io

            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding=encoding, errors="replace", line_buffering=True
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding=encoding, errors="replace", line_buffering=True
            )

    @staticmethod
    def safe_print(text: str, encoding: Optional[str] = None) -> None:
        """
        安全打印（处理编码问题）

        Args:
            text: 要打印的文本
            encoding: 编码
        """
        if encoding is None:
            encoding = PlatformEncodingHelper.get_console_encoding()

        try:
            print(text)
        except UnicodeEncodeError:
            # 尝试不同的编码
            for fallback_encoding in ["utf-8", "gbk", "ascii"]:
                try:
                    encoded = text.encode(fallback_encoding, errors="replace")
                    decoded = encoded.decode(fallback_encoding)
                    print(decoded)
                    break
                except Exception:
                    continue
            else:
                # 最后的手段：移除非ASCII字符
                ascii_text = "".join(c if ord(c) < 128 else "?" for c in text)
                print(ascii_text)


@contextmanager
def safe_open(
    file_path: Union[str, Path], mode: str = "r", encoding: Optional[str] = None, **kwargs
):
    """
    安全打开文件的上下文管理器

    Args:
        file_path: 文件路径
        mode: 打开模式
        encoding: 编码
        **kwargs: 其他参数

    Yields:
        文件对象
    """
    file_path = Path(file_path)

    # 如果是文本模式且没有指定编码，自动检测
    if "b" not in mode and encoding is None:
        encoding = EncodingDetector.detect_encoding(file_path)

    # 设置错误处理
    if "errors" not in kwargs and "b" not in mode:
        kwargs["errors"] = "replace"

    # 打开文件
    if "b" not in mode:
        f = open(file_path, mode, encoding=encoding, **kwargs)
    else:
        f = open(file_path, mode, **kwargs)

    try:
        yield f
    finally:
        f.close()


def fix_encoding_in_directory(
    directory: Union[str, Path],
    file_patterns: Optional[List[str]] = None,
    target_encoding: str = "utf-8",
    dry_run: bool = True,
) -> Dict[str, Any]:
    """修复目录中文件的文本编码。"""
    directory = Path(directory)

    if file_patterns is None:
        file_patterns = ["*.py", "*.txt", "*.md", "*.json", "*.yaml", "*.yml"]

    total_files = 0
    converted_files: List[Dict[str, str]] = []
    skipped_files: List[str] = []
    failed_files: List[Dict[str, str]] = []

    for pattern in file_patterns:
        for file_path in directory.rglob(pattern):
            if not file_path.is_file():
                continue

            total_files += 1
            current_encoding = EncodingDetector.detect_encoding(file_path)

            if current_encoding == target_encoding:
                skipped_files.append(str(file_path))
                continue

            try:
                if not dry_run:
                    SafeFileHandler.convert_encoding(
                        file_path,
                        target_encoding,
                        source_encoding=current_encoding,
                        backup=True,
                    )
                converted_files.append(
                    {"path": str(file_path), "from": current_encoding, "to": target_encoding}
                )
            except Exception as exc:
                failed_files.append({"path": str(file_path), "error": str(exc)})

    return {
        "total_files": total_files,
        "converted_files": converted_files,
        "skipped_files": skipped_files,
        "failed_files": failed_files,
    }


def read_text(file_path: Union[str, Path], **kwargs) -> str:
    """便捷的文本读取函数"""
    return SafeFileHandler.read_file(file_path, **kwargs)


def write_text(file_path: Union[str, Path], content: str, **kwargs) -> None:
    """便捷的文本写入函数"""
    SafeFileHandler.write_file(file_path, content, **kwargs)


def detect(file_path: Union[str, Path]) -> str:
    """便捷的编码检测函数"""
    return EncodingDetector.detect_encoding(file_path)


# Windows特殊处理
if sys.platform == "win32":
    # 设置环境变量以支持UTF-8
    os.environ["PYTHONIOENCODING"] = "utf-8:replace"

    # 启用ANSI转义序列（用于彩色输出）
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


# 使用示例
if __name__ == "__main__":
    # 示例1：安全读取文件
    content = read_text("test.txt")
    print(f"文件内容: {content[:100]}...")

    # 示例2：转换编码
    SafeFileHandler.convert_encoding("test_gbk.txt", target_encoding="utf-8", source_encoding="gbk")

    # 示例3：批量修复编码
    results = fix_encoding_in_directory(
        ".", file_patterns=["*.py"], target_encoding="utf-8", dry_run=False
    )
    print(f"处理结果: {results}")
