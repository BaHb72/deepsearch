<#
.SYNOPSIS
    Start Windows Dask workers with WIN=1 resource.

.DESCRIPTION
    Connects to a Dask scheduler and starts local Windows workers.
    This script is kept ASCII-only for PowerShell 5.1 compatibility.
#>

param(
    [string]$SchedulerAddress = "localhost:8786",
    [int]$NumWorkers = 2,
    [int]$ThreadsPerWorker = 2,
    [string]$MemoryLimit = "4GB",
    [string]$NamePrefix = "windows-worker",
    [string]$HostAddress = ""
)

$env:APP__ENV = "dev"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DeepSearch Windows Dask Workers" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (-not $HostAddress) {
    $primaryCandidates = Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object {
            $_.InterfaceAlias -match "vEthernet|DockerNAT|Ethernet" -and
            $_.IPAddress -notmatch "^169\."
        } |
        ForEach-Object {
            $priority = 5
            if ($_.InterfaceAlias -match "WSL") {
                $priority = 0
            }
            elseif ($_.InterfaceAlias -match "DockerNAT") {
                $priority = 1
            }
            elseif ($_.InterfaceAlias -match "vEthernet \(Default Switch\)") {
                $priority = 4
            }
            elseif ($_.InterfaceAlias -match "vEthernet") {
                $priority = 2
            }
            elseif ($_.InterfaceAlias -match "Ethernet") {
                $priority = 3
            }

            [PSCustomObject]@{
                IPAddress = $_.IPAddress
                Priority = $priority
            }
        }

    $hostIP = ($primaryCandidates | Sort-Object -Property Priority | Select-Object -First 1).IPAddress

    if (-not $hostIP) {
        $hostIP = (Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object {
                $_.IPAddress -notmatch "^127\." -and $_.IPAddress -notmatch "^169\."
            } |
            Select-Object -First 1).IPAddress
    }

    if ($hostIP) {
        $HostAddress = $hostIP
        Write-Host "Auto-detected host IP: $HostAddress" -ForegroundColor Green
    }
    else {
        Write-Host "Warning: failed to detect host IP, fallback to host.docker.internal" -ForegroundColor Yellow
        $HostAddress = "host.docker.internal"
    }
}

Write-Host "Scheduler: $SchedulerAddress"
Write-Host "Host Address: $HostAddress"
Write-Host "Workers: $NumWorkers"
Write-Host "Threads per worker: $ThreadsPerWorker"
Write-Host "Memory limit: $MemoryLimit"
Write-Host "Resource tag: WIN=1"
Write-Host ""

Write-Host "Checking scheduler connectivity..." -ForegroundColor Yellow
try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $hostPort = $SchedulerAddress -split ":"
    $tcpClient.Connect($hostPort[0], [int]$hostPort[1])
    $tcpClient.Close()
    Write-Host "Scheduler reachable" -ForegroundColor Green
}
catch {
    Write-Host "Cannot connect to scheduler: $SchedulerAddress" -ForegroundColor Red
    Write-Host "Please ensure scheduler is running first." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Starting Dask workers..." -ForegroundColor Yellow

$workerArgs = @(
    "worker", $SchedulerAddress,
    "--nworkers", $NumWorkers,
    "--nthreads", $ThreadsPerWorker,
    "--memory-limit", $MemoryLimit,
    "--resources", "WIN=1",
    "--name", $NamePrefix,
    "--dashboard-address", ":8789",
    "--host", $HostAddress
)

uv run dask @workerArgs
