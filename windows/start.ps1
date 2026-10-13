$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = Join-Path $root '.venv\Scripts\python.exe'
$vite = Join-Path $root 'node_modules\vite\bin\vite.js'
$nodeCommand = Get-Command 'node.exe' -ErrorAction SilentlyContinue
$soffice = 'C:\Program Files\LibreOffice\program\soffice.exe'

if (-not (Test-Path -LiteralPath $python)) { throw 'Python environment missing. Run 安装依赖.bat first.' }
if (-not (Test-Path -LiteralPath $vite)) { throw 'Vite dependency missing. Run 安装依赖.bat first.' }
if (-not $nodeCommand) { throw 'Node.js is missing from PATH. Reinstall Node.js 20+ and enable npm.' }
try {
    & $python -c "import sys; print(sys.version)"
    if ($LASTEXITCODE -ne 0) { throw 'Python could not start.' }
} catch { throw 'The project Python environment is broken or was copied from another computer. Run 安装依赖.bat to repair it.' }
if (-not (Test-Path -LiteralPath $soffice -PathType Leaf)) { throw "LibreOffice is missing at $soffice. Install it before converting PPT files." }

$activePorts = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in @(5193, 8787) })
if ($activePorts.Count -gt 0) {
    $portDetails = ($activePorts | ForEach-Object { "port $($_.LocalPort) (PID $($_.OwningProcess))" } | Sort-Object -Unique) -join ', '
    throw "A service is already using $portDetails. Close the previous LiveSlides instance or resolve the port conflict, then retry."
}

$offlinePlayer = Join-Path $root 'offline-dist\player.js'
$offlineStyles = Join-Path $root 'offline-dist\player.css'
if (-not (Test-Path -LiteralPath $offlinePlayer) -or -not (Test-Path -LiteralPath $offlineStyles)) {
    $npmCommand = Get-Command 'npm.cmd' -ErrorAction Stop
    Write-Host 'Building the standalone HTML player required by the download buttons...'
    & $npmCommand.Source run build:offline
    if ($LASTEXITCODE -ne 0) { throw 'Offline HTML player build failed. Resolve the build error before starting LiveSlides.' }
}

function Wait-ForService([string]$url, [string]$name) {
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return }
        } catch { }
        Start-Sleep -Seconds 1
    }
    throw "$name did not become ready at $url within 30 seconds. Check its console window for the startup error."
}

Write-Host 'Starting LiveSlides API...'
Start-Process -FilePath $python -ArgumentList @('server.py') -WorkingDirectory $root
Wait-ForService 'http://127.0.0.1:8787/api/config' 'LiveSlides API'

Write-Host 'Starting LiveSlides web app...'
Start-Process -FilePath $nodeCommand.Source -ArgumentList @("`"$vite`"", '--host', '0.0.0.0', '--port', '5193', '--strictPort') -WorkingDirectory $root
Wait-ForService 'http://127.0.0.1:5193/' 'LiveSlides web app'

Start-Process 'http://127.0.0.1:5193/'
Write-Host 'LiveSlides started at http://127.0.0.1:5193/.'
Write-Host 'Keep the API and Vite console windows open while using the app.'
Write-Host 'Close both console windows to stop the services.'

