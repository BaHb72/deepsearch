@echo off
echo ========================================
echo   DeepSearch React - Production Mode
echo   Port: 3001
echo ========================================
echo.

cd deepsearch\webui\frontend

echo Starting React production server on port 3001...
echo React app will be available at: http://localhost:3001
echo.

call npm run dev:react -- --mode production

pause
