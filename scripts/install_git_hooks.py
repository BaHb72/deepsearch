#!/usr/bin/env python
"""
Git Hooks 安装脚本
自动配置pre-commit hooks防止错误代码提交
"""
import os
import subprocess
import sys
from pathlib import Path


class GitHooksInstaller:
    """Git Hooks安装器"""

    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.git_dir = self.root_dir / ".git"
        self.hooks_dir = self.git_dir / "hooks"

    def check_git_repo(self):
        """检查是否在Git仓库中"""
        if not self.git_dir.exists():
            print("[失败] 错误：当前目录不是Git仓库")
            return False
        return True

    def install_pre_commit(self):
        """安装pre-commit框架"""
        print(" 安装pre-commit框架...")

        # 检查是否已安装
        try:
            result = subprocess.run(["pre-commit", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  [通过] pre-commit已安装: {result.stdout.strip()}")
            else:
                raise FileNotFoundError
        except FileNotFoundError:
            print("   正在安装pre-commit...")
            subprocess.run([sys.executable, "-m", "pip", "install", "pre-commit"])

        # 安装hooks
        print("   配置pre-commit hooks...")
        subprocess.run(["pre-commit", "install"])
        subprocess.run(["pre-commit", "install", "--hook-type", "commit-msg"])
        subprocess.run(["pre-commit", "install", "--hook-type", "pre-push"])

        print("  [通过] pre-commit hooks安装完成")

    def create_custom_hooks(self):
        """创建自定义Git hooks"""
        print(" 创建自定义Git hooks...")

        # 创建commit-msg hook
        commit_msg_hook = self.hooks_dir / "commit-msg"
        commit_msg_content = '''#!/usr/bin/env python
"""
提交信息验证Hook
确保提交信息符合规范
"""
import sys
import re

def validate_commit_message(message):
    """验证提交信息格式"""
    # 提交信息规范: type(scope): subject
    # 例如: feat(api): 添加数据源管理接口

    types = [
        'feat',     # 新功能
        'fix',      # 修复bug
        'docs',     # 文档更新
        'style',    # 代码格式
        'refactor', # 重构
        'test',     # 测试
        'chore',    # 构建/工具
        'perf',     # 性能优化
        'ci',       # CI/CD
        'revert',   # 回滚
        'build',    # 构建系统
    ]

    pattern = r'^(' + '|'.join(types) + r')(\\([\\w\\-\\.]+\\))?:\\s.{1,100}$'

    # 检查第一行
    first_line = message.split('\\n')[0]
    if not re.match(pattern, first_line):
        print("[失败] 提交信息格式错误！")
        print(f"   当前: {first_line}")
        print(f"   格式: type(scope): subject")
        print(f"   类型: {', '.join(types)}")
        print(f"   示例: feat(api): 添加数据源管理接口")
        return False

    # 检查是否包含敏感信息
    sensitive_patterns = [
        r'password\\s*=',
        r'token\\s*=',
        r'api[_-]?key\\s*=',
        r'secret\\s*=',
    ]

    for pattern in sensitive_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            print("[失败] 提交信息可能包含敏感信息！")
            return False

    return True

if __name__ == "__main__":
    commit_msg_file = sys.argv[1]

    with open(commit_msg_file, 'r', encoding='utf-8') as f:
        message = f.read()

    if not validate_commit_message(message):
        sys.exit(1)

    print("[通过] 提交信息验证通过")
'''

        with open(commit_msg_hook, "w", encoding="utf-8") as f:
            f.write(commit_msg_content)

        # 设置可执行权限（Windows下不需要）
        if sys.platform != "win32":
            os.chmod(commit_msg_hook, 0o755)

        print("  [通过] commit-msg hook创建成功")

        # 创建pre-push hook
        pre_push_hook = self.hooks_dir / "pre-push"
        pre_push_content = """#!/bin/bash
# Pre-push Hook
# 推送前运行测试

echo " 运行测试套件..."

# 运行快速测试
python scripts/run_all_tests.py --quick

if [ $? -ne 0 ]; then
    echo "[失败] 测试失败，禁止推送"
    echo "   请修复测试后再推送"
    exit 1
fi

# 检查代码覆盖率
coverage_threshold=70
current_coverage=$(coverage report | grep TOTAL | awk '{print $4}' | sed 's/%//')

if [ -n "$current_coverage" ]; then
    if (( $(echo "$current_coverage < $coverage_threshold" | bc -l) )); then
        echo "[警告] 警告：代码覆盖率 ${current_coverage}% 低于阈值 ${coverage_threshold}%"
        read -p "是否继续推送？(y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

echo "[通过] 所有检查通过"
"""

        with open(pre_push_hook, "w", encoding="utf-8") as f:
            f.write(pre_push_content)

        if sys.platform != "win32":
            os.chmod(pre_push_hook, 0o755)

        print("  [通过] pre-push hook创建成功")

    def create_helper_scripts(self):
        """创建辅助脚本"""
        print(" 创建辅助脚本...")

        # 检查QMT编码的脚本
        check_encoding_script = self.root_dir / "scripts" / "check_qmt_encoding.py"
        check_encoding_content = '''#!/usr/bin/env python
"""检查QMT脚本文件编码"""
import sys
from pathlib import Path

def check_file_encoding(filepath):
    """检查文件是否使用GBK编码"""
    try:
        with open(filepath, 'r', encoding='gbk') as f:
            first_line = f.readline()
            if not first_line.startswith('# encoding:gbk'):
                print(f"[失败] {filepath}: 缺少编码声明")
                return False
        return True
    except UnicodeDecodeError:
        print(f"[失败] {filepath}: 不是GBK编码")
        return False

if __name__ == "__main__":
    all_valid = True
    for filepath in sys.argv[1:]:
        if not check_file_encoding(filepath):
            all_valid = False

    sys.exit(0 if all_valid else 1)
'''

        check_encoding_script.parent.mkdir(exist_ok=True)
        with open(check_encoding_script, "w", encoding="utf-8") as f:
            f.write(check_encoding_content)

        print("  [通过] check_qmt_encoding.py 创建成功")

        # 验证配置文件的脚本
        validate_config_script = self.root_dir / "scripts" / "validate_config.py"
        validate_config_content = '''#!/usr/bin/env python
"""验证配置文件"""
import sys
import yaml
from pathlib import Path

def validate_config(filepath):
    """验证YAML配置文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 检查必要字段
        required_fields = ['app', 'webui', 'database', 'log']
        for field in required_fields:
            if field not in config:
                print(f"[失败] {filepath}: 缺少必要字段 '{field}'")
                return False

        return True
    except Exception as e:
        print(f"[失败] {filepath}: 配置文件错误 - {e}")
        return False

if __name__ == "__main__":
    all_valid = True
    for filepath in sys.argv[1:]:
        if not validate_config(filepath):
            all_valid = False

    sys.exit(0 if all_valid else 1)
'''

        with open(validate_config_script, "w", encoding="utf-8") as f:
            f.write(validate_config_content)

        print("  [通过] validate_config.py 创建成功")

    def run_initial_checks(self):
        """运行初始检查"""
        print("运行初始检查...")

        # 运行pre-commit检查
        print("  运行pre-commit检查...")
        result = subprocess.run(
            ["pre-commit", "run", "--all-files"], capture_output=True, text=True
        )

        if result.returncode != 0:
            print("  [警告] 存在代码质量问题，请运行以下命令修复：")
            print("     pre-commit run --all-files")
        else:
            print("  [通过] 代码质量检查通过")

    def print_usage(self):
        """打印使用说明"""
        print("\n" + "=" * 60)
        print(" Git Hooks 使用说明")
        print("=" * 60)
        print(
            """
1. 自动触发的Hooks:
   - pre-commit: 提交前检查代码质量
   - commit-msg: 验证提交信息格式
   - pre-push: 推送前运行测试

2. 手动命令:
   - pre-commit run --all-files  # 检查所有文件
   - pre-commit run <hook-id>    # 运行特定hook
   - pre-commit autoupdate        # 更新hook版本

3. 跳过Hooks（紧急情况）:
   - git commit --no-verify       # 跳过pre-commit
   - git push --no-verify         # 跳过pre-push

4. 提交信息格式:
   type(scope): subject

   类型(type):
   - feat: 新功能
   - fix: 修复bug
   - docs: 文档更新
   - style: 代码格式
   - refactor: 重构
   - test: 测试
   - chore: 构建/工具

   示例: feat(api): 添加数据源管理接口

5. 配置文件:
   - .pre-commit-config.yaml  # pre-commit配置
   - pyproject.toml           # 工具配置
        """
        )
        print("=" * 60)

    def install(self):
        """执行安装"""
        print(" 开始安装Git Hooks...\n")

        if not self.check_git_repo():
            return False

        try:
            self.install_pre_commit()
            self.create_custom_hooks()
            self.create_helper_scripts()
            self.run_initial_checks()
            self.print_usage()

            print("\n[通过] Git Hooks安装完成！")
            print("   所有提交将自动进行质量检查")
            return True

        except Exception as e:
            print(f"\n[失败] 安装失败: {e}")
            return False


def main():
    """主函数"""
    installer = GitHooksInstaller()
    success = installer.install()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
