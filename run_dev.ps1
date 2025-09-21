# DeepSearch Development Environment Launcher for Windows PowerShell
# This script sets the environment variable and launches the system in dev mode

Write-Host "Starting DeepSearch in DEVELOPMENT mode..." -ForegroundColor Green
Write-Host ""

# Set environment variable for this session
$env:APP__ENV = "dev"

# Display current environment
Write-Host "Environment: $($env:APP__ENV)" -ForegroundColor Cyan
Write-Host ""

# Run the application with all passed arguments
try {
    python -m deepsearch run $args
} catch {
    Write-Host ""
    Write-Host "Error occurred: $_" -ForegroundColor Red
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}