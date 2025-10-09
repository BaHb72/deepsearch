# Windows Redis 自动启动指南

为了保证本地开发效率，DeepSearch 在 Windows 环境启动引擎前会优先检测 Redis：

- 当 database.cache.enabled 且主机指向本机 (localhost / 127.0.0.1) 时才会触发自动启动逻辑。
- 优先尝试 database.cache.windows_service_names 中配置的系统服务，不存在时继续尝试 database.cache.startup_binary_path。
- 如果设置了 database.cache.startup_command，会在前两者失败后执行该命令。
- 通过 database.cache.auto_start_windows 可以整体关闭自动启动流程，改为人工维护 Redis。

## Windows 服务 / 可执行文件示例

`yaml
database:
  cache:
    enabled: true
    host: localhost
    port: 6379
    auto_start_windows: true
    windows_service_names:
      - Redis
      - redis
    startup_binary_path: 'C:/Program Files/Redis/redis-server.exe'
    startup_arguments: []
`

> 提示：startup_binary_path 用于当服务未注册或被禁用时，直接执行 redis-server.exe。若尚未安装 Redis，请先按照官方文档安装 Windows 版本。

## 故障排查

1. 查看 CLI 输出中的 [ERROR] Redis 相关日志，确认失败原因（端口占用 / 路径错误等）。
2. 使用 sc query <service> 检查 Windows 服务是否存在且状态正常。
3. 若不希望自动启动，可将 uto_start_windows 设为 alse，并在外部保持 Redis 常驻。

## WSL 部署场景

当 Redis 部署在 WSL 内时，可以结合 startup_command 与 database.cache.wsl 配置自动解析 IP：

`yaml
database:
  cache:
    auto_start_windows: true
    startup_command:
      - wsl.exe
      - -d
      - Ubuntu
      - -u
      - root
      - service
      - redis-server
      - start
    wsl:
      enabled: true
      distro: Ubuntu
      auto_resolve_ip: true
`

- startup_command 示例通过 wsl.exe 调用目标发行版的 service redis-server start 并提升为 root，实际命令可按需调整。
- wsl.auto_resolve_ip 会在每次启动时自动解析发行版当前分配的 IP，并同步覆盖 cache.host，避免 WSL2 动态 IP 造成连接失败。如果希望自行维护端口映射，可将其改为 alse。
- 若 WSL 中的 Redis 需要 sudo，请将命令改为 wsl.exe -d <发行版> -u root ... 或通过 sudoers 放行对应脚本。

配置完成后，DeepSearch 会在启动时自动刷新 WSL IP 并重试连接，从而兼容“Redis 在 WSL、引擎在 Windows”这一常见组合。

## RedisTimeSeries 模块加载

CI 与集成测试需要 RedisTimeSeries 扩展。若本地或流水线 Redis 仍为社区版，可通过以下方式加载：

1. **升级至官方 Redis 7.2+**：安装最新稳定版 Redis（Windows 可使用官方安装包或可信移植版本），自 Redis 7.2 起默认随附 `redistimeseries` 模块，无需再安装 redis-stack。请确保 `database.cache.startup_binary_path` 指向目标 `redis-server` 可执行文件，并保持其监听 DeepSearch 的 `host/port`。
2. **启用 Timeseries 模块**：使用 Redis 自带的 `redistimeseries` 模块文件（通常位于 `modules/` 目录），在 `settings.<env>.yaml` 的 `database.cache.startup_arguments` 中追加 `--loadmodule <模块绝对路径>`，或在启动前设置环境变量 `REDIS_TIMESERIES_LIB=<模块绝对路径>`，以便 DeepSearch 在需要时自动加载。
3. **验证**：启动 Redis 后执行 `redis-cli MODULE LIST`，确认输出包含 `name=timeseries`。若缺失，请检查模块路径、平台架构与 Redis 版本（推荐 Redis ≥ 7.2）。

> Windows 环境建议将模块文件放置在 `C\\Program Files\\Redis\\modules\\`，并在 PowerShell 中执行 `$env:REDIS_TIMESERIES_LIB='C:/Program Files/Redis/modules/redistimeseries.dll'`，随后运行 `uv run pytest …`。
