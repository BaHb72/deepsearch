@echo off
echo ========================================
echo   DeepSearch React - Development Mode
echo   Port: 3000
echo ========================================
echo.

cd deepsearch\webui\frontend

echo Starting React development server on port 3000...
echo React app will be available at: http://localhost:3000
echo.

call npm run dev:react -- --mode development

pause
