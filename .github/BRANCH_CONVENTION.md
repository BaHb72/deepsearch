# Git 分支管理规范

## 分支策略

### 主要分支

#### master (主分支)
- **用途**: 生产环境代码
- **保护**: 必须通过PR合并，禁止直接推送
- **要求**: 所有代码必须经过测试和代码审查

#### dev (开发分支)
- **用途**: 开发环境代码，功能集成
- **保护**: 建议通过PR合并
- **要求**: 功能分支合并前需通过基本测试

### 辅助分支

#### feature/* (功能分支)
- **命名**: `feature/功能描述` 或 `feature/issue-编号`
- **示例**: `feature/add-auth`, `feature/issue-123`
- **来源**: 从 `dev` 分支创建
- **合并**: 合并回 `dev` 分支
- **生命周期**: 功能完成后删除

#### bugfix/* (Bug修复分支)
- **命名**: `bugfix/bug描述` 或 `bugfix/issue-编号`
- **示例**: `bugfix/login-error`, `bugfix/issue-456`
- **来源**: 从 `dev` 或 `master` 分支创建（取决于bug紧急程度）
- **合并**: 合并回相应分支
- **生命周期**: 修复完成后删除

#### hotfix/* (紧急修复分支)
- **命名**: `hotfix/问题描述`
- **示例**: `hotfix/critical-security-issue`
- **来源**: 从 `master` 分支创建
- **合并**: 合并回 `master` 和 `dev` 分支
- **生命周期**: 修复完成后删除

#### release/* (发布分支)
- **命名**: `release/版本号`
- **示例**: `release/v1.2.0`
- **来源**: 从 `dev` 分支创建
- **合并**: 合并到 `master` 和 `dev`
- **生命周期**: 发布完成后保留或删除

#### test/* (测试分支)
- **命名**: `test/测试内容`
- **示例**: `test/performance-optimization`
- **来源**: 任意分支
- **合并**: 通常不合并，测试完成后删除
- **生命周期**: 测试完成后删除

## 工作流程

### 1. 开发新功能

```bash
# 1. 从dev分支创建功能分支
git checkout dev
git pull origin dev
git checkout -b feature/new-feature

# 2. 开发功能
# ... 编写代码 ...

# 3. 提交更改
git add .
git commit -m "feat: add new feature"

# 4. 推送到远程
git push origin feature/new-feature

# 5. 创建Pull Request到dev分支
# 在GitHub/GitLab上创建PR
```

### 2. 修复Bug

```bash
# 1. 从dev分支创建bugfix分支
git checkout dev
git pull origin dev
git checkout -b bugfix/fix-issue

# 2. 修复bug
# ... 修复代码 ...

# 3. 提交更改
git add .
git commit -m "fix: resolve login issue"

# 4. 推送并创建PR
git push origin bugfix/fix-issue
```

### 3. 紧急修复生产环境

```bash
# 1. 从master分支创建hotfix分支
git checkout master
git pull origin master
git checkout -b hotfix/critical-fix

# 2. 修复问题
# ... 修复代码 ...

# 3. 提交更改
git add .
git commit -m "hotfix: fix critical security issue"

# 4. 合并到master
git checkout master
git merge hotfix/critical-fix

# 5. 同步到dev分支
git checkout dev
git merge hotfix/critical-fix

# 6. 删除hotfix分支
git branch -d hotfix/critical-fix
```

### 4. 发布新版本

```bash
# 1. 从dev创建release分支
git checkout dev
git pull origin dev
git checkout -b release/v1.0.0

# 2. 版本准备（更新版本号，最终测试等）
# ... 准备发布 ...

# 3. 合并到master
git checkout master
git merge release/v1.0.0
git tag -a v1.0.0 -m "Release version 1.0.0"

# 4. 合并回dev
git checkout dev
git merge release/v1.0.0
```

## 分支保护规则

### Master分支保护
- ✅ 要求PR审查（至少1人）
- ✅ 要求状态检查通过（CI/CD）
- ✅ 要求分支最新
- ✅ 包含管理员
- ❌ 允许强制推送
- ❌ 允许删除分支

### Dev分支保护
- ✅ 要求PR审查（建议）
- ✅ 要求状态检查通过
- ❌ 允许强制推送
- ❌ 允许删除分支

## 最佳实践

### ✅ 应该做的

1. **频繁提交**: 小而频繁的提交便于追踪和回滚
2. **清晰的提交信息**: 使用规范的提交信息格式
3. **及时同步**: 定期从上游分支拉取最新代码
4. **代码审查**: 所有代码合并前进行审查
5. **测试覆盖**: 新功能必须包含测试
6. **文档更新**: 功能变更同步更新文档
7. **分支清理**: 合并后及时删除无用分支

### ❌ 不应该做的

1. **直接在master提交**: 永远不要直接在master分支上工作
2. **强制推送**: 避免使用 `git push -f`
3. **大型提交**: 避免一次提交过多更改
4. **混合更改**: 不要在一个提交中混合不相关的更改
5. **忽略冲突**: 合并冲突必须仔细解决
6. **跳过测试**: 不要跳过测试就合并代码
7. **长期分支**: 避免功能分支存在超过2周

## 常用命令

```bash
# 查看所有分支
git branch -a

# 清理已合并的本地分支
git branch --merged | grep -v "\*\|master\|dev" | xargs -n 1 git branch -d

# 清理远程已删除的分支引用
git remote prune origin

# 查看分支关系图
git log --graph --pretty=oneline --abbrev-commit --all

# 交互式rebase（整理提交历史）
git rebase -i HEAD~3

# 暂存当前更改
git stash

# 恢复暂存的更改
git stash pop
```

## 版本号规范

遵循语义化版本 (Semantic Versioning):

- **MAJOR.MINOR.PATCH** (如: 1.2.3)
  - **MAJOR**: 不兼容的API更改
  - **MINOR**: 向后兼容的功能添加
  - **PATCH**: 向后兼容的Bug修复

- **预发布版本**:
  - Alpha: `v1.0.0-alpha.1`
  - Beta: `v1.0.0-beta.1`
  - RC: `v1.0.0-rc.1`