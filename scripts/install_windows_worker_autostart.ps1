<#
.SYNOPSIS
    安装 Windows Dask Worker 开机自启
.DESCRIPTION
    创建 Windows 任务计划程序任务，在用户登录时自动启动 Dask Worker
    Worker 将连接到 Docker Scheduler (localhost:8786)，声明 WIN=1 资源
#>

param(
    [switch]$Uninstall,
    [string]$TaskName = "DeepSearch-DaskWorker",
    [string]$ProjectPath = "D:\Stock\code\deepsearch"
)

$ErrorActionPreference = "Stop"

# 卸载
if ($Uninstall) {
    Write-Host "正在卸载任务: $TaskName" -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "已卸载 ✓" -ForegroundColor Green
    exit 0
}

# 检查项目路径
if (-not (Test-Path $ProjectPath)) {
    Write-Error "项目路径不存在: $ProjectPath"
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  安装 Windows Dask Worker 自启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "任务名称: $TaskName"
Write-Host "项目路径: $ProjectPath"
Write-Host ""

# 创建启动脚本的包装批处理文件
$wrapperPath = Join-Path $ProjectPath "scripts\dask_worker_wrapper.cmd"
$wrapperContent = @"
@echo off
cd /d "$ProjectPath"
set APP__ENV=dev
powershell -ExecutionPolicy Bypass -File "$ProjectPath\scripts\start_windows_dask.ps1" -NumWorkers 1 -ThreadsPerWorker 4 -MemoryLimit 8GB
"@
Set-Content -Path $wrapperPath -Value $wrapperContent -Encoding ASCII
Write-Host "创建包装脚本: $wrapperPath ✓" -ForegroundColor Green

# 创建任务计划
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$wrapperPath`""

# 用户登录时触发
$trigger = New-ScheduledTaskTrigger -AtLogOn

# 任务设置
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)  # 无限运行

# 注册任务（以当前用户身份）
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

# 删除旧任务（如果存在）
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# 注册新任务
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "DeepSearch Windows Dask Worker - 连接到 Docker Scheduler，处理 Windows-only 数据源任务 (AmazingData, MiniQMT 等)"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  安装完成 ✓" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "任务已注册: $TaskName"
Write-Host "触发条件: 用户登录时自动启动"
Write-Host ""
Write-Host "手动操作:"
Write-Host "  启动: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  停止: Stop-ScheduledTask -TaskName '$TaskName'"
Write-Host "  卸载: .\install_windows_worker_autostart.ps1 -Uninstall"
Write-Host ""
Write-Host "现在启动 Worker? (Y/N): " -NoNewline -ForegroundColor Yellow
$response = Read-Host
if ($response -eq 'Y' -or $response -eq 'y') {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Worker 已启动 ✓" -ForegroundColor Green
}
