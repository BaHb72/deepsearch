<#
.SYNOPSIS
    启动 Windows Dask Workers
.DESCRIPTION
    连接到 Docker Scheduler，声明 WIN=1 资源标签
    用于处理需要 Windows 环境的任务（AmazingData, MiniQMT, AkShare 等）
#>

param(
    [string]$SchedulerAddress = "localhost:8786",
    [int]$NumWorkers = 2,
    [int]$ThreadsPerWorker = 2,
    [string]$MemoryLimit = "4GB",
    [string]$NamePrefix = "windows-worker",
    [string]$HostAddress = ""  # 主机地址，留空则自动检测
)

# 设置环境变量
$env:APP__ENV = "dev"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DeepSearch Windows Dask Workers" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 自动检测主机 IP（用于 Docker 容器访问）
if (-not $HostAddress) {
    # 获取 Docker 网桥接口的 IP（通常是 vEthernet (WSL) 或 DockerNAT）
    $hostIP = (Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.InterfaceAlias -match "vEthernet|DockerNAT|Ethernet" -and $_.IPAddress -notmatch "^169\." } |
        Sort-Object { if ($_.InterfaceAlias -match "DockerNAT") { 0 } elseif ($_.InterfaceAlias -match "vEthernet") { 1 } else { 2 } } |
        Select-Object -First 1).IPAddress

    if (-not $hostIP) {
        # 回退到获取任意非回环 IPv4 地址
        $hostIP = (Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object { $_.IPAddress -notmatch "^127\." -and $_.IPAddress -notmatch "^169\." } |
            Select-Object -First 1).IPAddress
    }

    if ($hostIP) {
        $HostAddress = $hostIP
        Write-Host "自动检测主机 IP: $HostAddress" -ForegroundColor Green
    }
    else {
        Write-Host "警告: 无法检测主机 IP，使用默认值" -ForegroundColor Yellow
        $HostAddress = "host.docker.internal"
    }
}

Write-Host "Scheduler: $SchedulerAddress"
Write-Host "Host Address: $HostAddress (Docker 容器将通过此地址访问 Worker)"
Write-Host "Workers: $NumWorkers"
Write-Host "Threads per worker: $ThreadsPerWorker"
Write-Host "Memory limit: $MemoryLimit"
Write-Host "Resource tag: WIN=1"
Write-Host ""

# 检查 Scheduler 是否可达
Write-Host "检查 Scheduler 连接..." -ForegroundColor Yellow
try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $hostPort = $SchedulerAddress -split ":"
    $tcpClient.Connect($hostPort[0], [int]$hostPort[1])
    $tcpClient.Close()
    Write-Host "Scheduler 可达 ✓" -ForegroundColor Green
}
catch {
    Write-Host "无法连接到 Scheduler: $SchedulerAddress" -ForegroundColor Red
    Write-Host "请确保 Docker 服务已启动: docker compose up -d" -ForegroundColor Yellow
    exit 1
}

# 启动 Workers
Write-Host ""
Write-Host "启动 Dask Workers..." -ForegroundColor Yellow

$workerArgs = @(
    "worker", $SchedulerAddress,
    "--nworkers", $NumWorkers,
    "--nthreads", $ThreadsPerWorker,
    "--memory-limit", $MemoryLimit,
    "--resources", "WIN=1",
    "--name", $NamePrefix,
    "--dashboard-address", ":8789",
    "--host", $HostAddress
)

# 使用 uv 运行 dask worker
uv run dask @workerArgs
