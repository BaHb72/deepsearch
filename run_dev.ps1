# DeepSearch Development Environment Launcher for Windows PowerShell
# This script sets the environment variable and launches the system in dev mode

Write-Host "Starting DeepSearch in DEVELOPMENT mode..." -ForegroundColor Green
Write-Host ""

# Set environment variable for this session
$env:APP__ENV = "dev"

# Display current environment
Write-Host "Environment: $($env:APP__ENV)" -ForegroundColor Cyan
Write-Host ""

# Start Docker infrastructure services
Write-Host "Starting Docker infrastructure services (RabbitMQ, Redis, Dask)..." -ForegroundColor Yellow
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Docker services failed to start. Make sure Docker Desktop is running." -ForegroundColor Red
    Write-Host "Press any key to continue or Ctrl+C to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
Start-Sleep -Seconds 5
Write-Host "Docker services started." -ForegroundColor Green
Write-Host ""

# Start Windows Dask Workers in background
Write-Host "Starting Windows Dask Workers..." -ForegroundColor Yellow
$daskWorkerScript = Join-Path $PSScriptRoot "scripts\start_windows_dask.ps1"
if (Test-Path $daskWorkerScript) {
    # 在后台启动 Windows Workers
    $daskJob = Start-Job -ScriptBlock {
        param($script, $env)
        $env:APP__ENV = $env
        & $script -SchedulerAddress "localhost:8786" -NumWorkers 2
    } -ArgumentList $daskWorkerScript, $env:APP__ENV
    Write-Host "Windows Dask Workers started in background (Job ID: $($daskJob.Id))" -ForegroundColor Green
}
else {
    Write-Host "Warning: Windows Dask worker script not found: $daskWorkerScript" -ForegroundColor Yellow
}
Write-Host ""

# Run the application with all passed arguments
try {
    python -m deepsearch run $args
}
catch {
    Write-Host ""
    Write-Host "Error occurred: $_" -ForegroundColor Red
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
