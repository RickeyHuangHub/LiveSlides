$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ok = $false

try {
    Set-Location -LiteralPath $root
    Write-Host 'LiveSlides first-time setup' -ForegroundColor Cyan

    $pyCommand = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if (-not $pyCommand) { throw 'Python Launcher (py.exe) not found. Install Python 3.10+ and enable the Python Launcher.' }
    $pyVersion = & $pyCommand.Source -3 -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))"
    if ($LASTEXITCODE -ne 0) { throw 'Could not start Python. Install Python 3.10 or newer.' }
    if ([version]$pyVersion -lt [version]'3.10') { throw "Python 3.10 or newer is required (found $pyVersion)." }

    $nodeCommand = Get-Command 'node.exe' -ErrorAction SilentlyContinue
    if (-not $nodeCommand) { throw 'Node.js not found. Install Node.js 20+ and make sure node.exe is on PATH.' }
    $nodeVersion = (& $nodeCommand.Source --version).Trim().TrimStart('v')
    if ($LASTEXITCODE -ne 0 -or [version]$nodeVersion -lt [version]'20.0') { throw "Node.js 20+ is required (found $nodeVersion)." }

    $soffice = 'C:\Program Files\LibreOffice\program\soffice.exe'
    if (-not (Test-Path -LiteralPath $soffice)) { throw "LibreOffice not found at $soffice. Install LibreOffice in its standard location." }

    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        Write-Host 'Creating local Python environment...'
        & $pyCommand.Source -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }

    $localPython = Join-Path $root '.venv\Scripts\python.exe'
    Write-Host 'Installing Python packages (internet required on first setup)...'
    & $localPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Python package installer failed. Check the internet connection and retry.' }
    & $localPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependencies failed to install. Check the internet connection and retry.' }

    $npmCommand = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
    if (-not $npmCommand) { throw 'npm.cmd not found. Repair or reinstall Node.js with npm enabled.' }
    Write-Host 'Installing web app packages (internet required on first setup)...'
    & $npmCommand.Source ci
    if ($LASTEXITCODE -ne 0) { throw 'Web dependencies failed to install. Check the internet connection and retry.' }

    Write-Host 'Setup complete. Next, run 启动LiveSlides.bat.' -ForegroundColor Green
    $ok = $true
}
catch {
    Write-Host ''
    Write-Host ('SETUP ERROR: ' + $_.Exception.Message) -ForegroundColor Red
}

if (-not $ok) { exit 1 }
