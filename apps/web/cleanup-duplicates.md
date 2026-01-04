# 前端项目重复文件清理报告

## 发现的问题

### 1. 重复的入口文件（6个）

- `main.js` - 重复的JS版本
- `main.jsx` - 重复的JSX版本
- `main.tsx` - TypeScript版本（未使用）
- `main-react.jsx` - **保留**（当前使用的主入口）
- `main-react-simple.jsx` - 简化版（可删除）
- `main-simple.jsx` - 简单demo版（可删除）

### 2. 重复的App组件（4个）

- `App.jsx` - **保留**（当前使用的监控系统版本）
- `App.tsx` - TypeScript版本（未使用）
- `App-react.jsx` - 旧版React组件（可删除）
- `AppSimple.jsx` - 简单demo版（可删除）

### 3. 重复的页面组件

#### Dashboard相关

- `Dashboard.jsx` - **保留**（新的监控仪表板）
- `Dashboard/` 目录 - 旧版本目录（可删除）

#### Market相关

- `Market.jsx` - 旧版本（可删除）
- `MarketData.jsx` - **保留**（新的市场数据监控）
- `Market/` 目录 - 旧版本目录（可删除）

#### Log相关

- `Logs.jsx` - 旧版本（可删除）
- `LogCenter.jsx` - **保留**（新的日志中心）

#### Data相关

- `DataSource.jsx` - 旧版本（可删除）
- `DataSourceMonitor.jsx` - **保留**（新的数据源监控）

#### Config相关

- `Config.jsx` - 旧版本（可删除）
- `SystemConfig.jsx` - **保留**（新的系统配置）

#### 其他旧页面

- `Trading.jsx` - 旧版本（可删除）
- `Events.jsx` - 旧版本（可删除）

### 4. 其他需要清理的文件

- `.trash/` 目录 - 之前清理Vue文件时的备份
- `NotFound/` 目录 - 404页面目录（待检查）
- `element-main.js` - Element UI相关（Vue专用，可删除）

## 建议的文件结构

```plaintext
src/
├── main-react.jsx         # 主入口文件
├── App.jsx                # 主应用组件
├── pages/                 # 页面组件
│   ├── Dashboard.jsx      # 系统总览
│   ├── DataSourceMonitor.jsx  # 数据源监控
│   ├── EventSystem.jsx    # 事件系统
│   ├── MarketData.jsx     # 市场数据
│   ├── CacheSystem.jsx    # 缓存系统
│   ├── PerformanceAnalytics.jsx # 性能分析
│   ├── ComponentManager.jsx    # 组件管理
│   ├── LogCenter.jsx      # 日志中心
│   ├── AlertManager.jsx   # 告警管理
│   └── SystemConfig.jsx   # 系统配置
├── components/            # 通用组件
├── services/             # API服务
├── utils/                # 工具函数
└── styles/               # 样式文件
```

## 需要删除的文件列表

### 入口文件（5个）

- src/main.js
- src/main.jsx
- src/main.tsx
- src/main-react-simple.jsx
- src/main-simple.jsx

### App组件（3个）

- src/App.tsx
- src/App-react.jsx
- src/AppSimple.jsx

### 页面组件（7个）

- src/pages/Market.jsx
- src/pages/Logs.jsx
- src/pages/DataSource.jsx
- src/pages/Config.jsx
- src/pages/Trading.jsx
- src/pages/Events.jsx
- src/element-main.js

### 目录（3个）

- src/pages/Dashboard/
- src/pages/Market/
- src/pages/NotFound/

## 清理后的效果

- 减少约20个重复文件
- 项目结构更清晰
- 避免维护混乱
- 减少打包体积
