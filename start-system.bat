@echo off
echo ========================================
echo DeepSearch 系统启动脚本
echo ========================================

:: 检查环境参数
if "%1"=="dev" (
    echo [配置] 使用开发环境 (settings.dev.yaml)
    set APP__ENV=dev
    set ENV_NAME=DEV
) else if "%1"=="prod" (
    echo [配置] 使用生产环境 (settings.prod.yaml)
    set APP__ENV=prod
    set ENV_NAME=PROD
) else (
    echo [配置] 默认使用开发环境 (settings.dev.yaml)
    set APP__ENV=dev
    set ENV_NAME=DEV
)
echo.

:: 1. 简单清理Python进程（可选）
echo [1/3] 清理旧进程...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

:: 2. 启动后端服务
echo.
echo [2/3] 启动后端服务 [%ENV_NAME%]...
start "DeepSearch Backend [%ENV_NAME%]" cmd /k "set APP__ENV=%APP__ENV% && python -m deepsearch run --no-frontend"

:: 等待后端启动
echo 等待后端服务启动（10秒）...
timeout /t 10 /nobreak >nul

:: 3. 启动前端服务
echo.
echo [3/3] 启动前端服务 [%ENV_NAME%]...
cd deepsearch\webui\frontend
start "DeepSearch Frontend [%ENV_NAME%]" cmd /k "npm run dev"

:: 等待前端启动
echo 等待前端服务启动（10秒）...
timeout /t 10 /nobreak >nul

:: 4. 打开浏览器
echo.
echo ========================================
echo 系统启动完成！
echo.
echo 环境: %ENV_NAME% (settings.%APP__ENV%.yaml)
echo 后端地址: http://localhost:8000
echo 前端地址: http://localhost:3000
echo.
if "%ENV_NAME%"=="DEV" (
    echo AmazingData配置 (开发环境):
    echo - 请确保在settings.dev.yaml中配置正确的凭据
    echo.
)
echo 如果Loading界面卡住，请：
echo 1. 检查后端窗口是否有错误
echo 2. 确保数据库和Redis服务正常运行
echo 3. 刷新浏览器页面
echo.
echo 使用方法:
echo   start-system.bat        - 默认使用开发环境
echo   start-system.bat dev    - 使用开发环境
echo   start-system.bat prod   - 使用生产环境
echo ========================================
echo.
echo 正在打开浏览器...
start http://localhost:3000

pause
