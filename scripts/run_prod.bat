@echo off
REM DeepSearch Production Environment Launcher for Windows
REM This script sets the environment variable and launches the system in prod mode

echo Starting DeepSearch in PRODUCTION mode...
echo.

REM Set environment variable for this session
set APP__ENV=prod

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
