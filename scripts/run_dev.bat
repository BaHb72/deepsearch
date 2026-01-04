@echo off
REM DeepSearch Development Environment Launcher for Windows
REM This script sets the environment variable and launches the system in dev mode

echo Starting DeepSearch in DEVELOPMENT mode...
echo.

REM Set environment variable for this session
set APP__ENV=dev

REM Display current environment
echo Environment: %APP__ENV%
echo.

REM Run the application
uv run python -m deepsearch run %*

REM If there was an error, pause to see the message
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error occurred! Press any key to exit...
    pause > nul
)
