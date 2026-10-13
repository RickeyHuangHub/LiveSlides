$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$logPath = Join-Path $root '安装日志.txt'
$ok = $false
$transcriptStarted = $false

try {
    Set-Location -LiteralPath $root
    Start-Transcript -LiteralPath $logPath -Append | Out-Null
    $transcriptStarted = $true
    Write-Host 'LiveSlides first-time setup' -ForegroundColor Cyan

    $activePorts = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -in @(5193, 8787) })
    if ($activePorts.Count -gt 0) {
        $portDetails = ($activePorts | ForEach-Object { "port $($_.LocalPort) (PID $($_.OwningProcess))" } | Sort-Object -Unique) -join ', '
        throw "LiveSlides or another service is already using $portDetails. Stop the running service, then run 安装依赖.bat again."
    }

    $python = $null
    $pythonArgs = @()
    $pyVersion = $null
    foreach ($candidateName in @('py.exe', 'python.exe', 'python3.exe')) {
        $candidate = Get-Command $candidateName -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $candidate) { continue }
        $candidateArgs = if ($candidateName -eq 'py.exe') { @('-3', '-c', "import sys; print('{}.{}.{}'.format(*sys.version_info[:3]))") } else { @('-c', "import sys; print('{}.{}.{}'.format(*sys.version_info[:3]))") }
        $candidateVersion = (& $candidate.Source @candidateArgs 2>$null | Select-Object -Last 1)
        if ($LASTEXITCODE -eq 0 -and $candidateVersion -match '^\d+\.\d+\.\d+$') {
            $python = $candidate
            $pythonArgs = if ($candidateName -eq 'py.exe') { @('-3') } else { @() }
            $pyVersion = $candidateVersion
            break
        }
    }
    if (-not $python) { throw 'Usable Python was not found. Install Python 3.10+ and select “Add Python to PATH”. The Python Launcher (py.exe) is optional.' }
    Write-Host ("Python: {0} ({1})" -f $python.Source, $pyVersion)
    if ([version]$pyVersion -lt [version]'3.10') { throw "Python 3.10 or newer is required (found $pyVersion)." }

    $nodeCommand = Get-Command 'node.exe' -ErrorAction SilentlyContinue
    if (-not $nodeCommand) { throw 'Node.js not found. Install Node.js 20+ and make sure node.exe is on PATH.' }
    $nodeVersion = (& $nodeCommand.Source --version).Trim().TrimStart('v')
    if ($LASTEXITCODE -ne 0 -or [version]$nodeVersion -lt [version]'20.0') { throw "Node.js 20+ is required (found $nodeVersion)." }

    $soffice = 'C:\Program Files\LibreOffice\program\soffice.exe'
    if (-not (Test-Path -LiteralPath $soffice)) { throw "LibreOffice not found at $soffice. Install LibreOffice in its standard location." }

    $venvPath = Join-Path $root '.venv'
    $localPython = Join-Path $venvPath 'Scripts\python.exe'
    $venvUsable = $false
    if (Test-Path -LiteralPath $localPython -PathType Leaf) {
        Write-Host 'Checking the bundled Python environment...'
        try {
            & $localPython -c "import sys; print(sys.executable)"
            $venvUsable = ($LASTEXITCODE -eq 0)
        } catch { $venvUsable = $false }
    }

    if (-not $venvUsable) {
        if (Test-Path -LiteralPath $venvPath) {
            $resolvedRoot = [IO.Path]::GetFullPath($root).TrimEnd('\') + '\'
            $resolvedVenv = [IO.Path]::GetFullPath($venvPath)
            if (-not $resolvedVenv.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase) -or
                [IO.Path]::GetFileName($resolvedVenv) -ne '.venv') {
                throw "Refusing to replace an unexpected Python environment path: $resolvedVenv"
            }
            Write-Host 'The existing .venv is invalid or belongs to another computer. Recreating this project-local environment...'
            Remove-Item -LiteralPath $resolvedVenv -Recurse -Force
        } else {
            Write-Host 'Creating local Python environment...'
        }
        $venvCreateArgs = @($pythonArgs) + @('-m', 'venv', $venvPath)
        Write-Host ("Creating virtual environment with arguments: {0}" -f ($venvCreateArgs -join ' '))
        & $python.Source @venvCreateArgs
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment. See the Python output and installation log.' }
        if (-not (Test-Path -LiteralPath $localPython -PathType Leaf)) { throw 'Python environment creation did not produce .venv\Scripts\python.exe.' }
        & $localPython -c "import sys; print(sys.executable)"
        if ($LASTEXITCODE -ne 0) { throw 'The newly created Python environment could not start. Check the Python installation and installation log.' }
    }

    Write-Host 'Installing Python packages (internet required on first setup)...'
    & $localPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Python package installer failed. See pip output above and 安装日志.txt; check internet access, proxy and permissions.' }
    & $localPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependencies failed to install. See pip output above and 安装日志.txt; check internet access, proxy and permissions.' }

    $npmCommand = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
    if (-not $npmCommand) { throw 'npm.cmd not found. Repair or reinstall Node.js with npm enabled.' }
    Write-Host 'Installing web app packages (internet required on first setup)...'
    & $npmCommand.Source ci
    if ($LASTEXITCODE -ne 0) { throw 'Web dependencies failed to install. Check the internet connection and retry.' }

    Write-Host 'Building the standalone offline HTML player...'
    & $npmCommand.Source run build:offline
    if ($LASTEXITCODE -ne 0) { throw 'Offline HTML player build failed. Check the setup output, then run npm run build:offline from the project folder.' }

    Write-Host 'Setup complete. Next, run 启动LiveSlides.bat.' -ForegroundColor Green
    $ok = $true
}
catch {
    Write-Host ''
    Write-Host ('SETUP ERROR: ' + $_.Exception.Message) -ForegroundColor Red
}
finally {
    if ($transcriptStarted) { Stop-Transcript | Out-Null }
}

if (-not $ok) { exit 1 }

