# 贡献指南

感谢您对 DeepSearch 项目的关注！

## 开发环境设置

1. 克隆仓库

```bash
git clone https://github.com/BaHb/deepsearch.git
cd deepsearch
```

2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. 安装开发依赖

```bash
pip install -r requirements-dev.txt
pip install -e .
```

## 代码规范

- 使用 Black 进行代码格式化
- 使用 isort 进行导入排序
- 运行测试确保代码正确

```bash
# 格式化代码
black deepsearch tests
isort deepsearch tests

# 运行测试
pytest
```

## 提交代码

1. 创建新分支

```bash
git checkout -b feature/your-feature
```

2. 提交更改

```bash
git add .
git commit -m "添加新功能"
```

3. 推送并创建 Pull Request

## 报告问题

请在 GitHub Issues 中报告问题，并提供：

- 问题描述
- 复现步骤
- 系统信息