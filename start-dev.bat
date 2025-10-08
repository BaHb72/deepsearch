@echo off
echo ========================================
echo DeepSearch 开发环境启动脚本
echo ========================================
echo.

:: 设置开发环境
echo [配置] 设置开发环境 (APP__ENV=dev)...
set APP__ENV=dev

:: 1. 简单清理Python进程（可选）
echo [1/3] 清理旧进程...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

:: 2. 启动后端服务（开发模式）
echo.
echo [2/3] 启动后端服务（开发模式）...
echo 配置文件: settings.dev.yaml
start "DeepSearch Backend [DEV]" cmd /k "set APP__ENV=dev && python -m deepsearch run --no-frontend --log-level DEBUG"

:: 等待后端启动
echo 等待后端服务启动（10秒）...
timeout /t 10 /nobreak >nul

:: 3. 启动前端服务（开发模式）
echo.
echo [3/3] 启动前端服务（开发模式）...
cd deepsearch\webui\frontend
start "DeepSearch Frontend [DEV]" cmd /k "npm run dev"

:: 等待前端启动
echo 等待前端服务启动（10秒）...
timeout /t 10 /nobreak >nul

:: 4. 打开浏览器
echo.
echo ========================================
echo 开发环境启动完成！
echo.
echo 环境: DEV (settings.dev.yaml)
echo 后端地址: http://localhost:8000
echo 前端地址: http://localhost:3000
echo.
echo AmazingData配置:
echo - 请确保在settings.dev.yaml中配置正确的凭据
echo.
echo 如果Loading界面卡住，请：
echo 1. 检查后端窗口是否有错误
echo 2. 确保数据库和Redis服务正常运行
echo 3. 刷新浏览器页面
echo ========================================
echo.
echo 正在打开浏览器...
start http://localhost:3000

pause