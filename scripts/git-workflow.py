#!/usr/bin/env python3
"""
Git工作流自动化脚本
提供简化的Git操作命令，确保遵循项目规范
"""

import argparse
import re
import subprocess
from pathlib import Path
from typing import Tuple


class GitWorkflow:
    """Git工作流管理器"""

    def __init__(self):
        self.repo_root = self._find_repo_root()

    def _find_repo_root(self) -> Path:
        """查找Git仓库根目录"""
        current = Path.cwd()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        raise RuntimeError("未找到Git仓库")

    def _run_git(self, *args, capture=True) -> Tuple[int, str]:
        """执行Git命令"""
        cmd = ["git"] + list(args)
        if capture:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode, result.stdout.strip()
        else:
            result = subprocess.run(cmd)
            return result.returncode, ""

    def _get_current_branch(self) -> str:
        """获取当前分支名"""
        _, branch = self._run_git("branch", "--show-current")
        return branch

    def _branch_exists(self, branch: str, remote: bool = False) -> bool:
        """检查分支是否存在"""
        if remote:
            code, _ = self._run_git("ls-remote", "--heads", "origin", branch)
            return code == 0
        else:
            code, _ = self._run_git("show-ref", "--verify", f"refs/heads/{branch}")
            return code == 0

    def create_feature(self, name: str):
        """创建功能分支"""
        if not name:
            print("[失败] 请提供功能名称")
            return

        # 切换到dev分支并更新
        print(" 更新dev分支...")
        self._run_git("checkout", "dev")
        self._run_git("pull", "origin", "dev")

        # 创建功能分支
        branch_name = f"feature/{name}"
        print(f" 创建分支: {branch_name}")
        code, _ = self._run_git("checkout", "-b", branch_name)

        if code == 0:
            print(f"[通过] 已创建并切换到 {branch_name}")
            print("提示: 完成开发后使用 'git push -u origin HEAD' 推送分支")
        else:
            print("[失败] 创建分支失败")

    def create_bugfix(self, name: str):
        """创建Bug修复分支"""
        if not name:
            print("[失败] 请提供Bug描述")
            return

        # 切换到dev分支并更新
        print(" 更新dev分支...")
        self._run_git("checkout", "dev")
        self._run_git("pull", "origin", "dev")

        # 创建修复分支
        branch_name = f"bugfix/{name}"
        print(f" 创建分支: {branch_name}")
        code, _ = self._run_git("checkout", "-b", branch_name)

        if code == 0:
            print(f"[通过] 已创建并切换到 {branch_name}")
        else:
            print("[失败] 创建分支失败")

    def create_hotfix(self, name: str):
        """创建紧急修复分支"""
        if not name:
            print("[失败] 请提供紧急修复描述")
            return

        # 切换到master分支并更新
        print(" 更新master分支...")
        self._run_git("checkout", "master")
        self._run_git("pull", "origin", "master")

        # 创建修复分支
        branch_name = f"hotfix/{name}"
        print(f"[警告] 创建分支: {branch_name}")
        code, _ = self._run_git("checkout", "-b", branch_name)

        if code == 0:
            print(f"[通过] 已创建并切换到 {branch_name}")
            print("[警告] 注意: 紧急修复完成后需要同时合并到master和dev分支")
        else:
            print("[失败] 创建分支失败")

    def quick_commit(self, message: str, commit_type: str = "feat"):
        """快速提交（符合规范）"""
        valid_types = [
            "feat",
            "fix",
            "docs",
            "style",
            "refactor",
            "perf",
            "test",
            "chore",
            "revert",
        ]

        if commit_type not in valid_types:
            print(f"[失败] 无效的提交类型: {commit_type}")
            print(f"有效类型: {', '.join(valid_types)}")
            return

        # 添加所有更改
        print(" 添加更改...")
        self._run_git("add", "-A")

        # 检查是否有更改
        code, status = self._run_git("status", "--porcelain")
        if not status:
            print("[信息] 没有需要提交的更改")
            return

        # 构建提交信息
        full_message = f"{commit_type}: {message}"

        # 提交
        print(f" 提交: {full_message}")
        code, _ = self._run_git("commit", "-m", full_message)

        if code == 0:
            print("[通过] 提交成功")
        else:
            print("[失败] 提交失败")

    def cleanup_branches(self):
        """清理已合并的本地分支"""
        print(" 清理已合并的分支...")

        # 获取已合并的分支
        _, merged = self._run_git("branch", "--merged")
        branches = [b.strip() for b in merged.split("\n") if b.strip()]

        # 过滤掉保护分支
        protected = ["*", "master", "main", "dev", "develop"]
        branches_to_delete = [b for b in branches if not any(p in b for p in protected)]

        if not branches_to_delete:
            print("[信息] 没有需要清理的分支")
            return

        print("将删除以下分支:")
        for branch in branches_to_delete:
            print(f"  - {branch}")

        confirm = input("\n确认删除？(y/N): ")
        if confirm.lower() == "y":
            for branch in branches_to_delete:
                self._run_git("branch", "-d", branch.strip())
            print(f"[通过] 已删除 {len(branches_to_delete)} 个分支")
        else:
            print("[失败] 取消删除")

    def status_report(self):
        """生成状态报告"""
        print("\n Git 仓库状态报告")
        print("=" * 50)

        # 当前分支
        current = self._get_current_branch()
        print(f" 当前分支: {current}")

        # 本地分支
        _, local_branches = self._run_git("branch")
        local_count = len(local_branches.strip().split("\n"))
        print(f" 本地分支数: {local_count}")

        # 远程分支
        _, remote_branches = self._run_git("branch", "-r")
        remote_count = len(remote_branches.strip().split("\n")) if remote_branches else 0
        print(f" 远程分支数: {remote_count}")

        # 未提交的更改
        _, status = self._run_git("status", "--porcelain")
        if status:
            changes = status.split("\n")
            print(f" 未提交更改: {len(changes)} 个文件")
        else:
            print("[通过] 工作区干净")

        # 最后一次提交
        _, last_commit = self._run_git("log", "-1", "--pretty=format:%h - %s (%cr)")
        print(f" 最后提交: {last_commit}")

        # 统计信息
        _, total_commits = self._run_git("rev-list", "--count", "HEAD")
        print(f" 总提交数: {total_commits}")

        print("=" * 50)

    def validate_commit_message(self, message: str) -> bool:
        """验证提交信息格式"""
        pattern = r"^(feat|fix|docs|style|refactor|perf|test|chore|revert)(\([a-z\-]+\))?: .{1,50}"
        return bool(re.match(pattern, message))

    def show_help(self):
        """显示帮助信息"""
        help_text = """
Git工作流助手 - 命令列表
========================

基本命令:
  feature <name>    创建功能分支
  bugfix <name>     创建Bug修复分支
  hotfix <name>     创建紧急修复分支
  commit <msg>      快速提交（默认类型: feat）
  cleanup           清理已合并的分支
  status            显示仓库状态报告

提交类型:
  feat              新功能
  fix               修复bug
  docs              文档更改
  style             格式调整
  refactor          重构代码
  perf              性能优化
  test              测试相关
  chore             构建/工具

示例:
  python git-workflow.py feature user-auth
  python git-workflow.py commit "add login feature" --type feat
  python git-workflow.py cleanup
  python git-workflow.py status
        """
        print(help_text)


def main():
    parser = argparse.ArgumentParser(description="Git工作流自动化工具")
    parser.add_argument("command", nargs="?", help="命令")
    parser.add_argument("args", nargs="*", help="命令参数")
    parser.add_argument("--type", default="feat", help="提交类型")

    args = parser.parse_args()

    workflow = GitWorkflow()

    if not args.command or args.command == "help":
        workflow.show_help()
        return

    command = args.command.lower()

    if command == "feature":
        workflow.create_feature(" ".join(args.args))
    elif command == "bugfix":
        workflow.create_bugfix(" ".join(args.args))
    elif command == "hotfix":
        workflow.create_hotfix(" ".join(args.args))
    elif command == "commit":
        workflow.quick_commit(" ".join(args.args), args.type)
    elif command == "cleanup":
        workflow.cleanup_branches()
    elif command == "status":
        workflow.status_report()
    else:
        print(f"[失败] 未知命令: {command}")
        workflow.show_help()


if __name__ == "__main__":
    main()
