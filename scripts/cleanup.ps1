<#
.SYNOPSIS
    DeepSearch Project Root Directory Cleanup Script
.DESCRIPTION
    Clean up temporary files, large log files and crash dump files
.PARAMETER Force
    Skip confirmation and delete directly
.PARAMETER DryRun
    Only show files to be deleted, do not actually delete
.EXAMPLE
    .\cleanup.ps1 -DryRun
    .\cleanup.ps1 -Force
#>

param(
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "DeepSearch Project Cleanup Script" -ForegroundColor Cyan
Write-Host "Project Path: $ProjectRoot" -ForegroundColor Gray
Write-Host ""

# Define file patterns to clean
$patterns = @(
    @{ Pattern = "*.dmp"; Description = "Crash dump files" }
    @{ Pattern = "backend*.log"; Description = "Backend log files" }
    @{ Pattern = "_tmp_*.log"; Description = "Temp log files" }
    @{ Pattern = "_tmp_*.txt"; Description = "Temp text files" }
    @{ Pattern = "_tmp_*.json"; Description = "Temp JSON files" }
    @{ Pattern = "startup_debug.log"; Description = "Startup debug log" }
)

# Collect all matching files using PSCustomObject
$filesToDelete = @()
$totalSize = 0

foreach ($p in $patterns) {
    $files = Get-ChildItem -Path $ProjectRoot -Filter $p.Pattern -File -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        $filesToDelete += [PSCustomObject]@{
            Path = $file.FullName
            Name = $file.Name
            Size = $file.Length
            Category = $p.Description
        }
        $totalSize += $file.Length
    }
}

if ($filesToDelete.Count -eq 0) {
    Write-Host "No files found to clean" -ForegroundColor Green
    exit 0
}

# Display file list
$sizeMB = [math]::Round($totalSize / 1MB, 2)
Write-Host "Found $($filesToDelete.Count) files, total $sizeMB MB" -ForegroundColor Yellow
Write-Host ""
Write-Host "File List:" -ForegroundColor Cyan

# Group by category
$grouped = $filesToDelete | Group-Object -Property Category
foreach ($group in $grouped) {
    $categorySize = ($group.Group | Measure-Object -Property Size -Sum).Sum
    $catSizeMB = [math]::Round($categorySize / 1MB, 2)
    Write-Host "  [$($group.Name)] - $($group.Count) files, $catSizeMB MB" -ForegroundColor White
    foreach ($file in $group.Group | Sort-Object -Property Size -Descending | Select-Object -First 5) {
        $fileSizeMB = [math]::Round($file.Size / 1MB, 2)
        Write-Host "    - $($file.Name) ($fileSizeMB MB)" -ForegroundColor Gray
    }
    if ($group.Count -gt 5) {
        $remaining = $group.Count - 5
        Write-Host "    ... and $remaining more files" -ForegroundColor DarkGray
    }
}

Write-Host ""

if ($DryRun) {
    Write-Host "[DryRun] Above files will be deleted (preview mode)" -ForegroundColor Magenta
    exit 0
}

# Confirm deletion
if (-not $Force) {
    $confirm = Read-Host "Delete above files? (y/N)"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "Cancelled" -ForegroundColor Yellow
        exit 0
    }
}

# Execute deletion
$deletedCount = 0
$deletedSize = 0
$errors = @()

foreach ($file in $filesToDelete) {
    try {
        Remove-Item -Path $file.Path -Force
        $deletedCount++
        $deletedSize += $file.Size
        Write-Host "  Deleted: $($file.Name)" -ForegroundColor Green
    }
    catch {
        $errors += "Cannot delete $($file.Name): $_"
        Write-Host "  Failed: $($file.Name)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Cleanup complete!" -ForegroundColor Cyan
$deletedMB = [math]::Round($deletedSize / 1MB, 2)
Write-Host "  Deleted files: $deletedCount" -ForegroundColor White
Write-Host "  Freed space: $deletedMB MB" -ForegroundColor White

if ($errors.Count -gt 0) {
    Write-Host ""
    Write-Host "Errors:" -ForegroundColor Red
    foreach ($err in $errors) {
        Write-Host "  $err" -ForegroundColor Red
    }
}
