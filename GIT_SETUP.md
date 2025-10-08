# Git 规范化配置使用指南

本项目已配置完整的Git规范化工具，帮助团队保持代码提交的一致性和规范性。

## 📦 配置文件说明

| 文件 | 说明 | 用途 |
|------|------|------|
| `.gitmessage` | Git提交信息模板 | 规范提交信息格式 |
| `.commitlintrc.json` | Commitlint配置 | 验证提交信息规范 |
| `.pre-commit-config.yaml` | Pre-commit hooks配置 | 提交前自动检查 |
| `.gitconfig` | Git别名配置 | 简化Git命令 |
| `.github/BRANCH_CONVENTION.md` | 分支管理规范 | 团队分支策略 |
| `scripts/git-workflow.py` | 自动化脚本 | 简化工作流程 |

## 🚀 快速开始

### 1. 安装Pre-commit hooks

```bash
# 安装pre-commit
pip install pre-commit

# 安装Git hooks
pre-commit install

# 安装commit-msg hook（验证提交信息）
pre-commit install --hook-type commit-msg

# 手动运行所有检查
pre-commit run --all-files
```

### 2. 配置Git提交模板

```bash
# 设置提交信息模板
git config --local commit.template .gitmessage

# 或全局设置（应用到所有项目）
git config --global commit.template "$(pwd)/.gitmessage"
```

### 3. 导入Git别名

```bash
# 项目级别导入
git config --local include.path ../.gitconfig

# 或全局导入（推荐）
git config --global include.path "$(pwd)/.gitconfig"
```

## 📝 提交规范

### 提交信息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 提交类型

- **feat**: 新功能
- **fix**: 修复bug
- **docs**: 文档更改
- **style**: 代码格式（不影响功能）
- **refactor**: 重构
- **perf**: 性能优化
- **test**: 测试相关
- **chore**: 构建/工具链相关

### 示例

```bash
# 使用Git别名快速提交
git feat "add user authentication"
git fix "resolve login timeout issue"
git docs "update API documentation"

# 或使用标准方式
git commit -m "feat(auth): add JWT token validation

Implement JWT token validation middleware for API endpoints
to ensure secure access to protected resources.

Closes #123"
```

## 🛠️ 使用自动化脚本

### 基本用法

```bash
# 创建功能分支
python scripts/git-workflow.py feature user-auth

# 创建Bug修复分支
python scripts/git-workflow.py bugfix login-error

# 快速提交
python scripts/git-workflow.py commit "add new feature" --type feat

# 清理已合并分支
python scripts/git-workflow.py cleanup

# 查看状态报告
python scripts/git-workflow.py status
```

### 添加到系统路径（可选）

```bash
# Windows (PowerShell)
$env:PATH += ";$(pwd)\scripts"

# Linux/Mac
export PATH="$PATH:$(pwd)/scripts"
chmod +x scripts/git-workflow.py

# 之后可以直接使用
git-workflow feature my-feature
```

## 🎯 常用Git别名

配置完成后，可以使用以下简化命令：

### 基础操作
```bash
git st          # status -sb (简洁状态)
git co          # checkout
git br          # branch
git ci          # commit
git aa          # add --all
git cm "msg"    # commit -m "msg"
```

### 日志查看
```bash
git lg          # 漂亮的日志图形显示
git last        # 最后一次提交
git today       # 今天的提交
```

### 分支管理
```bash
git cleanup     # 清理已合并的分支
git feature name  # 创建功能分支
git bugfix name   # 创建修复分支
git done branch   # 完成分支（合并并删除）
```

### 撤销操作
```bash
git unstage     # 取消暂存
git undo        # 撤销上次提交（保留更改）
git amend       # 修改上次提交
```

## 🔍 Pre-commit检查项

提交前会自动执行以下检查：

1. **Python代码格式化** (Black)
2. **Import排序** (isort)
3. **代码质量检查** (Flake8)
4. **类型检查** (MyPy)
5. **YAML/JSON语法检查**
6. **大文件检查** (>5MB)
7. **合并冲突标记检查**
8. **提交信息规范检查**
9. **安全检查** (检测敏感信息)

### 跳过检查（紧急情况）

```bash
# 跳过pre-commit检查
git commit --no-verify -m "hotfix: emergency fix"
```

⚠️ **注意**: 仅在紧急情况下使用，正常情况应该修复所有检查问题。

## 📊 工作流程示例

### 开发新功能

```bash
# 1. 创建功能分支
python scripts/git-workflow.py feature payment-gateway

# 2. 开发代码...

# 3. 提交更改
git aa
git feat "implement payment gateway integration"

# 4. 推送分支
git psu  # push -u origin HEAD

# 5. 创建Pull Request
# 在GitHub/GitLab上创建PR到dev分支
```

### 修复Bug

```bash
# 1. 创建修复分支
python scripts/git-workflow.py bugfix order-calculation

# 2. 修复代码...

# 3. 提交修复
git aa
git fix "correct order total calculation"

# 4. 推送并创建PR
git psu
```

## ⚙️ 自定义配置

### 修改提交规范

编辑 `.commitlintrc.json` 文件来自定义提交规范。

### 添加/移除Pre-commit hooks

编辑 `.pre-commit-config.yaml` 文件来管理hooks。

### 扩展Git别名

编辑 `.gitconfig` 文件添加自己的别名。

## 🆘 常见问题

### Q: Pre-commit失败怎么办？

A: 查看错误信息，修复问题后重新提交。常见修复方法：

```bash
# 自动修复格式问题
black deepsearch tests
isort deepsearch tests

# 查看具体错误
flake8 deepsearch
mypy deepsearch
```

### Q: 如何撤销错误的提交？

A: 使用以下命令：

```bash
# 撤销最后一次提交（保留更改）
git undo

# 修改后重新提交
git aa
git ci -m "correct commit message"
```

### Q: 如何更新Pre-commit hooks？

A: 运行以下命令：

```bash
# 更新所有hooks到最新版本
pre-commit autoupdate

# 清理缓存
pre-commit clean
```

## 📚 参考资源

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Git分支模型](https://nvie.com/posts/a-successful-git-branching-model/)
- [Pre-commit文档](https://pre-commit.com/)
- [Commitlint文档](https://commitlint.js.org/)