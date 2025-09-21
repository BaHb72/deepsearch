@echo off
echo 正在启动市场数据页面测试环境...
echo ================================

REM 启动后端
echo 启动后端服务...
start cmd /k "cd /d D:\Stock\code\deepsearch && uv run python -m deepsearch run --mode webui"

REM 等待后端启动
echo 等待后端启动...
timeout /t 10 /nobreak > nul

REM 启动前端
echo 启动前端开发服务器...
start cmd /k "cd /d D:\Stock\code\deepsearch\deepsearch\webui\frontend && npm run dev"

echo.
echo ================================
echo 市场数据页面已启动！
echo.
echo 后端地址: http://localhost:8000
echo 前端地址: http://localhost:3000
echo.
echo 请在浏览器中访问 http://localhost:3000 查看效果
echo.
echo 按任意键关闭所有服务...
pause > nul

REM 关闭所有相关进程
taskkill /F /IM python.exe 2>nul
taskkill /F /IM node.exe 2>nul
echo 服务已关闭