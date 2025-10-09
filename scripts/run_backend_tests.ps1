[CmdletBinding()]
param(
    [string]$PythonExePath,
    [string[]]$PytestArgs,
    [string]$LogPath,
    [string]$SummaryPath,
    [switch]$SkipWait,
    [switch]$SkipPytest,
    [switch]$SkipFrontend,
    [switch]$SkipProbe,
    [string[]]$FrontendArgs
)

chcp 65001 | Out-Null > $null 2>&1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = 'Stop'

if (-not $SkipWait -and -not $Host.UI.SupportsUserInterface) {
    $SkipWait = $true
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$defaultPythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontendDir = Join-Path $projectRoot 'deepsearch\webui\frontend'
$apiProbe    = Join-Path $projectRoot 'scripts\\probes\\api_probe.py'
$defaultLogDir = Join-Path $projectRoot 'reports\logs'

$pythonExeCandidates = @()
if ($PSBoundParameters.ContainsKey('PythonExePath') -and -not [string]::IsNullOrWhiteSpace($PythonExePath)) {
    $pythonExeCandidates += [pscustomobject]@{ Path = $PythonExePath; Source = '参数 -PythonExePath'; Label = '脚本参数' }
}
if (-not [string]::IsNullOrWhiteSpace($env:DEEPSEARCH_PYTHON_EXE)) {
    $pythonExeCandidates += [pscustomobject]@{ Path = $env:DEEPSEARCH_PYTHON_EXE; Source = '环境变量 DEEPSEARCH_PYTHON_EXE'; Label = '环境变量' }
}
$pythonExeCandidates += [pscustomobject]@{ Path = $defaultPythonExe; Source = '默认虚拟环境'; Label = '默认虚拟环境' }

$selectionErrors = New-Object System.Collections.Generic.List[pscustomobject]
$selectedCandidate = $null
foreach ($candidate in $pythonExeCandidates) {
    if (-not $candidate.Path -or [string]::IsNullOrWhiteSpace($candidate.Path)) {
        continue
    }

    $rawPath = $candidate.Path
    $probePath = $rawPath
    if (-not [System.IO.Path]::IsPathRooted($probePath)) {
        $probePath = Join-Path $projectRoot $probePath
    }

    try {
        $probePath = (Resolve-Path -LiteralPath $probePath -ErrorAction Stop).Path
    }
    catch {
        # 保留原始路径供汇总
    }

    if (Test-Path -LiteralPath $probePath) {
        $selectedCandidate = [pscustomobject]@{
            Path = $probePath
            Source = $candidate.Source
            Label = $candidate.Label
            RawPath = $rawPath
        }
        break
    }

    $selectionErrors.Add(
        [pscustomobject]@{
            Source = $candidate.Source
            RawPath = $rawPath
            ProbedPath = $probePath
        }
    ) | Out-Null
}

if (-not $selectedCandidate) {
    if ($selectionErrors.Count -gt 0) {
        $details = $selectionErrors | ForEach-Object { "- 来源: {0}，原始: {1}，探测: {2}" -f $_.Source, $_.RawPath, $_.ProbedPath }
        throw "无法定位 Python 可执行文件，已尝试: `n$($details -join [Environment]::NewLine)"
    }

    throw '无法确定 Python 可执行路径，请通过 -PythonExePath 或设置环境变量修复后重试。'
}

$pythonExe = $selectedCandidate.Path
$pythonInfoMessage = "使用 Python 可执行文件: $pythonExe (来源: $($selectedCandidate.Label))"

function ConvertTo-ArgumentList {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return @()
    }

    $errors = $null
    $tokens = [System.Management.Automation.PSParser]::Tokenize($Value, [ref]$errors)
    if ($errors -and $errors.Count -gt 0) {
        return $Value -split '\s+' | Where-Object { $_ }
    }

    $result = @()
    foreach ($token in $tokens) {
        if ($token.Type -in @('CommandArgument', 'StringLiteral')) {
            $result += $token.Content
        }
    }

    return $result
}

$script:TranscriptPath = $null
$script:StdErrStarted = $false
$script:StepSummaries = New-Object System.Collections.Generic.List[pscustomobject]
$script:StepFailures = New-Object System.Collections.Generic.List[string]

function Initialize-RunLog {
    param([string]$Path)

    $script:TranscriptPath = $Path
    $script:StdErrStarted = $false
    Set-Content -LiteralPath $script:TranscriptPath -Encoding utf8 -Value '### STDOUT'
}

function Append-RunLog {
    param(
        [string]$Message,
        [switch]$StdErr
    )

    $path = $script:TranscriptPath
    if (-not $path) {
        return
    }

    if ($StdErr -and -not $script:StdErrStarted) {
        Add-Content -LiteralPath $path -Encoding utf8 -Value ''
        Add-Content -LiteralPath $path -Encoding utf8 -Value '### STDERR'
        $script:StdErrStarted = $true
    }

    Add-Content -LiteralPath $path -Encoding utf8 -Value $Message
}

function Write-LogMessage {
    param(
        [string]$Message,
        [string]$ForegroundColor = $null
    )

    if ($ForegroundColor) {
        Write-Host $Message -ForegroundColor $ForegroundColor
    }
    else {
        Write-Host $Message
    }

    Append-RunLog -Message $Message
}

function Write-LogWarning {
    param([string]$Message)

    Write-Warning $Message
    Append-RunLog -Message "[WARNING] $Message"
}

function Write-LogError {
    param([string]$Message)

    Write-Error $Message
    Append-RunLog -Message "[ERROR] $Message" -StdErr
}

function Invoke-NativeCommandLogged {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    $stderrTemp = [System.IO.Path]::GetTempFileName()
    try {
        & $FilePath @Arguments 2> $stderrTemp | ForEach-Object {
            if ($null -ne $_) {
                Append-RunLog -Message $_
                if ([string]::IsNullOrEmpty($_)) {
                    Write-Host ''
                }
                else {
                    Write-Host $_ -ForegroundColor DarkGray
                }
            }
        }

        $exitCode = $LASTEXITCODE
        $global:LASTEXITCODE = $exitCode

        if (Test-Path -LiteralPath $stderrTemp) {
            $stderrLines = Get-Content -Path $stderrTemp -Encoding utf8
            foreach ($line in $stderrLines) {
                Append-RunLog -Message $line -StdErr
                if ([string]::IsNullOrEmpty($line)) {
                    Write-Host ''
                }
                else {
                    Write-Host $line -ForegroundColor Red
                }
            }
        }

        Append-RunLog -Message ''
        return $exitCode
    }
    finally {
        Remove-Item -LiteralPath $stderrTemp -ErrorAction SilentlyContinue
    }
}

function Add-SkippedStep {
    param(
        [string]$Name,
        [string]$Reason
    )

    $record = [pscustomobject]@{
        name = $Name
        status = 'skipped'
        started_at = (Get-Date).ToString('o')
        completed_at = (Get-Date).ToString('o')
        duration_seconds = 0
        exit_code = $null
        error = $null
        notes = @($Reason)
    }
    $script:StepSummaries.Add($record)
    Write-LogWarning ("跳过 {0}: {1}" -f $Name, $Reason)
}

if (-not (Test-Path -LiteralPath $defaultLogDir)) {
    New-Item -ItemType Directory -Force -Path $defaultLogDir | Out-Null
}

$logFilePath = $null
if ($PSBoundParameters.ContainsKey('LogPath') -and -not [string]::IsNullOrWhiteSpace($LogPath)) {
    $resolvedLogPath = $LogPath
    if (-not [System.IO.Path]::IsPathRooted($resolvedLogPath)) {
        $resolvedLogPath = Join-Path $projectRoot $resolvedLogPath
    }
    $logDirectory = Split-Path -Parent $resolvedLogPath
    if ($logDirectory -and -not (Test-Path -LiteralPath $logDirectory)) {
        New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
    }
    $logFilePath = $resolvedLogPath
}
else {
    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $logFilePath = Join-Path $defaultLogDir "backend_tests_$timestamp.log"
}

Initialize-RunLog -Path $logFilePath
Write-LogMessage ("日志将写入: {0}" -f $logFilePath) 'Yellow'
Write-LogMessage $pythonInfoMessage 'Yellow'

$summaryFilePath = $null
if ($PSBoundParameters.ContainsKey('SummaryPath') -and -not [string]::IsNullOrWhiteSpace($SummaryPath)) {
    $resolvedSummary = $SummaryPath
    if (-not [System.IO.Path]::IsPathRooted($resolvedSummary)) {
        $resolvedSummary = Join-Path $projectRoot $resolvedSummary
    }
    $summaryDirectory = Split-Path -Parent $resolvedSummary
    if ($summaryDirectory -and -not (Test-Path -LiteralPath $summaryDirectory)) {
        New-Item -ItemType Directory -Force -Path $summaryDirectory | Out-Null
    }
    $summaryFilePath = $resolvedSummary
}
else {
    $summaryFileName = [System.IO.Path]::GetFileNameWithoutExtension($logFilePath)
    $summaryFilePath = Join-Path (Split-Path -Parent $logFilePath) "${summaryFileName}_summary.json"
}

$pytestExtraArgs = @()
if ($PytestArgs) {
    $rawArgs = @()
    foreach ($item in @($PytestArgs)) {
        if ($null -eq $item) {
            continue
        }
        if ($item -isnot [string]) {
            $rawArgs += $item
            continue
        }
        $parsed = ConvertTo-ArgumentList -Value $item
        if ($parsed.Count -gt 0) {
            $rawArgs += $parsed
        }
        elseif ($item.Trim()) {
            $rawArgs += $item.Trim()
        }
    }
    $pytestExtraArgs = $rawArgs
}
elseif (-not [string]::IsNullOrWhiteSpace($env:PYTEST_ADDOPTS)) {
    $pytestExtraArgs = ConvertTo-ArgumentList -Value $env:PYTEST_ADDOPTS
    if ($pytestExtraArgs.Count -gt 0) {
        Write-LogWarning '检测到环境变量 PYTEST_ADDOPTS，建议使用 -PytestArgs 显式传参以便日志记录。'
    }
}

$frontendCommand = @('run', 'test', '--', '--runInBand')
if ($PSBoundParameters.ContainsKey('FrontendArgs') -and $FrontendArgs) {
    $frontendCommand = @($FrontendArgs)
}

if (-not $SkipFrontend -and -not (Test-Path -LiteralPath $frontendDir)) {
    throw "未找到前端目录: $frontendDir"
}
if (-not $SkipProbe -and -not (Test-Path -LiteralPath $apiProbe)) {
    throw "未找到 API 探活脚本: $apiProbe"
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action,
        [object[]]$ArgumentList = @()
    )

    $record = [pscustomobject]@{
        name = $Name
        status = 'running'
        started_at = (Get-Date).ToString('o')
        completed_at = $null
        duration_seconds = $null
        exit_code = $null
        error = $null
        notes = @()
    }
    $script:StepSummaries.Add($record)

    Write-LogMessage ("==== 开始: {0} ==== " -f $Name) 'Cyan'
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $global:LASTEXITCODE = 0
        & $Action @ArgumentList
        $exitCode = $LASTEXITCODE
        $record.exit_code = $exitCode

        if ($exitCode -ne 0) {
            $message = "步骤 {0} 以退出码 {1} 结束" -f $Name, $exitCode
            Write-LogWarning $message
            $script:StepFailures.Add($message) | Out-Null
            $record.status = 'failed'
            $record.notes = @($message)
        }
        else {
            $record.status = 'succeeded'
        }
    }
    catch {
        $exitCode = $LASTEXITCODE
        $record.exit_code = $exitCode
        $errorMessage = $_.Exception.Message
        Write-LogError ("步骤 {0} 抛出异常: {1}" -f $Name, $errorMessage)
        $script:StepFailures.Add("步骤 {0} 抛出异常: {1}" -f $Name, $errorMessage) | Out-Null
        $record.status = 'error'
        $record.error = $errorMessage
        $record.notes = @("捕获异常: $errorMessage")
        throw
    }
    finally {
        if ($sw.IsRunning) {
            $sw.Stop()
        }
        $record.duration_seconds = [math]::Round($sw.Elapsed.TotalSeconds, 2)
        $record.completed_at = (Get-Date).ToString('o')

        switch ($record.status) {
            'succeeded' {
                Write-LogMessage ("==== 结束: {0} (耗时 {1} 秒) ==== " -f $Name, $record.duration_seconds) 'Green'
            }
            'failed' {
                Write-LogMessage ("==== 结束(异常): {0} (耗时 {1} 秒) ==== " -f $Name, $record.duration_seconds) 'Yellow'
            }
            'error' {
                Write-LogMessage ("==== 失败: {0} (耗时 {1} 秒) ==== " -f $Name, $record.duration_seconds) 'Red'
            }
            default {
                Write-LogMessage ("==== 中止: {0} ==== " -f $Name) 'Yellow'
            }
        }
    }
}

$runStartTime = Get-Date
$overallTimer = [System.Diagnostics.Stopwatch]::StartNew()
$runOutcome = 'unknown'

try {
    if ($SkipPytest) {
        Add-SkippedStep -Name '执行 pytest tests/api' -Reason '检测到 -SkipPytest 参数。'
    }
    else {
        Invoke-Step -Name '执行 pytest tests/api' -Action {
            param($pythonPath, $extraArgs)

            $pytestArgsList = @('-m', 'pytest', 'tests/api')
            if ($extraArgs -and $extraArgs.Count -gt 0) {
                Write-LogMessage ("追加 pytest 参数: {0}" -f ($extraArgs -join ' ')) 'DarkCyan'
                $pytestArgsList += $extraArgs
            }

            Write-LogMessage ("执行命令: {0} {1}" -f $pythonPath, ($pytestArgsList -join ' ')) 'DarkGray'
            Invoke-NativeCommandLogged -FilePath $pythonPath -Arguments $pytestArgsList | Out-Null
        } -ArgumentList $pythonExe, $pytestExtraArgs
    }

    if ($SkipFrontend) {
        Add-SkippedStep -Name 'npm run test -- --runInBand' -Reason '检测到 -SkipFrontend 参数。'
    }
    else {
        Invoke-Step -Name 'npm run test -- --runInBand' -Action {
            param($directory, $arguments)

            Push-Location $directory
            try {
                Write-LogMessage ("执行命令: npm {0}" -f ($arguments -join ' ')) 'DarkGray'
                Invoke-NativeCommandLogged -FilePath 'npm' -Arguments $arguments | Out-Null
            }
            finally {
                Pop-Location
            }
        } -ArgumentList $frontendDir, $frontendCommand
    }

    if ($SkipProbe) {
        Add-SkippedStep -Name '执行 scripts/probes/api_probe.py' -Reason '检测到 -SkipProbe 参数。'
    }
    else {
        Invoke-Step -Name '执行 scripts/probes/api_probe.py' -Action {
            param($pythonPath, $scriptPath)

            Write-LogMessage ("执行命令: {0} {1}" -f $pythonPath, $scriptPath) 'DarkGray'
            Invoke-NativeCommandLogged -FilePath $pythonPath -Arguments @($scriptPath) | Out-Null
        } -ArgumentList $pythonExe, $apiProbe
    }

    if ($script:StepFailures.Count -gt 0) {
        $runOutcome = 'failed'
        $summary = $script:StepFailures -join '；'
        throw "自动回归失败: $summary"
    }

    $runOutcome = 'passed'
    Write-LogMessage '回归执行完成，日志已写入上述路径。' 'Yellow'
}
catch {
    if ($runOutcome -eq 'unknown') {
        $runOutcome = 'failed'
    }
    Write-LogError ("回归脚本捕获异常: {0}" -f $_.Exception.Message)
    throw
}
finally {
    if ($overallTimer.IsRunning) {
        $overallTimer.Stop()
    }

    $totalDuration = [Math]::Round($overallTimer.Elapsed.TotalSeconds, 2)
    $durationLine = "TotalDuration={0}s" -f $totalDuration
    Write-LogMessage $durationLine 'Yellow'

    $runEndTime = Get-Date
    $summaryPayload = [ordered]@{
        project = 'DeepSearch'
        started_at = $runStartTime.ToString('o')
        completed_at = $runEndTime.ToString('o')
        duration_seconds = $totalDuration
        outcome = $runOutcome
        python_executable = $pythonExe
        python_source = $selectedCandidate.Source
        log_path = $logFilePath
        summary_path = $summaryFilePath
        parameters = [ordered]@{
            pytest_args = @($pytestExtraArgs)
            frontend_args = @($frontendCommand)
            skip_pytest = [bool]$SkipPytest
            skip_frontend = [bool]$SkipFrontend
            skip_probe = [bool]$SkipProbe
        }
        steps = @($script:StepSummaries)
        failures = @($script:StepFailures)
    }

    try {
        $json = $summaryPayload | ConvertTo-Json -Depth 6
        Set-Content -LiteralPath $summaryFilePath -Encoding utf8 -Value $json
        Write-LogMessage ("运行摘要已写入: {0}" -f $summaryFilePath) 'Yellow'
    }
    catch {
        Write-LogWarning ("写入摘要文件失败: {0}" -f $_.Exception.Message)
    }

    if (-not $SkipWait) {
        Read-Host -Prompt '按回车关闭窗口。' | Out-Null
    }
}

