@echo off
echo ======================================
echo DeepSearch Startup Script
echo ======================================
echo.

if "%1"=="" (
    echo Starting complete system...
    python -m deepsearch run
) else if "%1"=="backend" (
    echo Starting backend only...
    python -m deepsearch run --no-frontend
) else if "%1"=="frontend" (
    echo Starting frontend only...
    cd deepsearch\webui\frontend
    npm run dev
) else (
    echo Invalid option: %1
    echo.
    echo Usage: start.bat [backend^|frontend]
    echo   start.bat         - Start complete system
    echo   start.bat backend - Start backend only
    echo   start.bat frontend- Start frontend only
)

pause