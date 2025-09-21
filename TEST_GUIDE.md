# 数据源监控修复测试指南

## 🚀 快速测试步骤

### 1. 启动后端服务
```bash
# 在项目根目录执行
python -m deepsearch run
```

### 2. 启动前端服务（另一个终端）
```bash
cd deepsearch/webui/frontend
npm run dev
```

### 3. 验证修复效果

#### 方式1：通过浏览器
1. 打开浏览器访问：http://localhost:3000
2. 导航到"数据源监控"页面
3. 检查是否显示真实数据（不再是模拟数据）

#### 方式2：通过API测试
```bash
# 测试监控端点
curl http://localhost:8000/api/data-sources/monitor

# 预期返回格式：
# {
#   "code": 0,
#   "message": "获取监控数据成功",
#   "data": {
#     "overview": {...},
#     "sources": [...],
#     "timeline": [],
#     "alerts": []
#   },
#   "success": true
# }
```

## ✅ 验证清单

- [ ] 后端服务成功启动（端口8000）
- [ ] 前端服务成功启动（端口3000）
- [ ] `/api/data-sources/monitor` 返回数据
- [ ] 数据源监控页面显示真实数据
- [ ] 没有"连接失败"的错误提示

## 🔧 常见问题

### Q: 端口被占用
```bash
# Windows查看端口占用
netstat -ano | findstr :8000
# 结束进程
taskkill /PID [进程ID] /F
```

### Q: 监控数据为空
- 检查监控服务是否启动
- 查看后端日志是否有错误
- API会返回默认数据避免页面空白

### Q: 前端仍显示模拟数据
- 清除浏览器缓存
- 检查Network面板中API请求是否成功
- 确认后端API路径正确：`/api/data-sources/monitor`

## 📝 测试报告模板

```markdown
测试时间：2025-09-17
测试人员：[您的名字]

### 测试结果
- [ ] API端点正常工作
- [ ] 前端页面正常显示
- [ ] 数据实时更新
- [ ] 错误处理正常

### 问题记录
（如有问题请记录）

### 截图证明
（可选：附上成功的截图）
```