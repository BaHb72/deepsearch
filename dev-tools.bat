@echo off
echo ========================================
echo DeepSearch 开发工具
echo ========================================
echo.

if "%1"=="" (
    echo 用法: dev-tools.bat [命令]
    echo.
    echo 可用命令:
    echo   clean-vite    - 清理 Vite 缓存
    echo   fix-perms     - 修复文件权限
    echo   start-safe    - 安全启动前端（清理后启动）
    echo   clean-all     - 清理所有临时文件
    echo.
    goto :eof
)

if /i "%1"=="clean-vite" (
    echo 清理 Vite 缓存...
    cd deepsearch\webui\frontend
    rd /s /q node_modules\.vite 2>nul
    rd /s /q .vite 2>nul
    del /q vite.config.js.timestamp-*.mjs 2>nul
    echo [OK] Vite 缓存已清理
    goto :eof
)

if /i "%1"=="fix-perms" (
    echo 修复文件权限...
    icacls deepsearch\webui\frontend /grant Everyone:F /T /C /Q
    echo [OK] 权限已修复
    goto :eof
)

if /i "%1"=="start-safe" (
    echo 安全启动前端...
    call :clean-vite
    cd deepsearch\webui\frontend
    npm run dev
    goto :eof
)

if /i "%1"=="clean-all" (
    echo 清理所有临时文件...
    
    echo - 清理 Python 缓存
    for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
    
    echo - 清理 Vite 缓存
    call :clean-vite
    
    echo - 清理日志文件（保留最近7天）
    forfiles /p "logs" /m "*.log" /d -7 /c "cmd /c del @file" 2>nul
    
    echo - 清理监控数据（保留最近7天）
    forfiles /p "data\monitoring" /m "monitor_data_*.json" /d -7 /c "cmd /c del @file" 2>nul
    
    echo [OK] 所有临时文件已清理
    goto :eof
)

echo 错误: 未知命令 "%1"
echo 运行 "dev-tools.bat" 查看帮助
goto :eof

:clean-vite
cd deepsearch\webui\frontend 2>nul
rd /s /q node_modules\.vite 2>nul
rd /s /q .vite 2>nul
del /q vite.config.js.timestamp-*.mjs 2>nul
cd ..\..\..
goto :eof