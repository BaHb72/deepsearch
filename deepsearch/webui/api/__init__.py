"""
Web UI API 路由模块。
"""
import sys
from pathlib import Path


# 启动时检查配置文件
def check_config_files():
    """检查必要的配置文件是否存在"""
    config_dir = Path(__file__).parent.parent.parent / "config"
    dev_config = config_dir / "settings.dev.yaml"
    prod_config = config_dir / "settings.prod.yaml"

    if not config_dir.exists():
        print(f"[错误] 配置目录不存在: {config_dir}", file=sys.stderr)
        print(f"[信息] 请创建配置目录并添加配置文件", file=sys.stderr)
        return False

    if not dev_config.exists() and not prod_config.exists():
        print(f"[错误] 未找到任何配置文件", file=sys.stderr)
        print(f"[信息] 请至少创建以下配置文件之一：", file=sys.stderr)
        print(f"  - {dev_config}", file=sys.stderr)
        print(f"  - {prod_config}", file=sys.stderr)
        return False

    return True


# 在导入时检查配置
if not check_config_files():
    print("[警告] 配置文件缺失，某些功能可能无法正常工作", file=sys.stderr)
