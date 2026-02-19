# AkShare Worker 代理迁移验收清单

> 适用场景：新机器部署、网络环境变更、Cloudflare Worker 重新发布后验收。

## 1. 依赖与配置完整性

1. 在项目根目录执行：
   - `uv pip check`
2. 检查 `settings.<env>.yaml` 中是否存在 `cloudflare_workers`，至少包含：
   - `url`
   - `use_system_proxy`
   - `prefer_ipv4_fallback`

通过标准：
- `uv pip check` 无冲突。
- 配置文件可被系统正常加载（启动日志无配置解析错误）。

## 2. 系统代理状态确认（Windows）

1. 检查 Internet Settings：
   - `Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' | Select-Object ProxyEnable,ProxyServer,AutoConfigURL`
2. 检查 WinHTTP：
   - `netsh winhttp show proxy`

通过标准：
- 若网络要求代理，至少有一种系统代理来源可用（Internet Settings 或 WinHTTP）。
- 若网络不要求代理，确认已关闭系统代理并在配置中评估是否关闭 `use_system_proxy`。

## 3. Worker 健康接口验收

1. 健康检查：
   - `Invoke-WebRequest 'https://<your-worker>.workers.dev/health' -UseBasicParsing`
2. 代理转发检查：
   - `Invoke-WebRequest 'https://<your-worker>.workers.dev/proxy?url=https%3A%2F%2Fquote.eastmoney.com%2Fcenter%2Fgridlist.html%23hs_a_board' -UseBasicParsing`

通过标准：
- `/health` 返回 `200`，且 `status=healthy`。
- `/proxy` 返回 `200`，并包含目标站点正文。

## 4. Python 链路与业务链路验收

1. Python 代理链路（建议使用项目虚拟环境）：
   - `uv run --python ./.venv/Scripts/python.exe -c "from core.utils.network.proxy_client import ProxyClient; c=ProxyClient(worker_url='https://<your-worker>.workers.dev'); r=c.get('https://quote.eastmoney.com/center/gridlist.html#hs_a_board', timeout=20); print(c.session.proxies); print(r.status_code)"`
2. AkShare worker 模式实链：
   - 使用 PowerShell 运行：

```powershell
@'
import asyncio
from core.infrastructure.providers.implementations.akshare.akshare_direct import AkShareProvider

async def main():
    provider = AkShareProvider(
        config={
            "mode": "worker",
            "proxy": {
                "enabled": True,
                "worker_url": "https://<your-worker>.workers.dev",
                "timeout": 20,
            },
        }
    )
    await provider.initialize()
    quote = await provider.get_realtime_quote("000001")
    print(provider.access_mode, quote.get("name"), quote.get("current"), quote.get("error"))

asyncio.run(main())
'@ | uv run --python ./.venv/Scripts/python.exe -
```

通过标准：
- `ProxyClient` 请求状态码为 `200`，`session.proxies` 非空（在需要代理的网络中）。
- `AkShareProvider` 输出 `access_mode=worker`，且 `error` 为空。

## 5. 回滚开关（失败时）

1. 临时回滚到直连：
   - 将 `data_sources.providers.akshare.config.mode` 设置为 `direct`。
   - 或将 `data_sources.providers.akshare.config.proxy.enabled` 设置为 `false`。
2. 重启服务后复验接口可用性。

通过标准：
- 回滚后系统可恢复稳定响应，不阻塞主流程。
- 在问题未解决前保留 Worker 配置，不删除历史参数，便于后续对比排障。
