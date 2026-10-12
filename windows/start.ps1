$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = Join-Path $root '.venv\Scripts\python.exe'
$vite = Join-Path $root 'node_modules\vite\bin\vite.js'
$nodeCommand = Get-Command 'node.exe' -ErrorAction Stop

if (-not (Test-Path -LiteralPath $python)) { throw 'Python environment missing. Run 安装依赖.bat first.' }
if (-not (Test-Path -LiteralPath $vite)) { throw 'Vite dependency missing. Run 安装依赖.bat first.' }

Start-Process -FilePath $python -ArgumentList @('server.py') -WorkingDirectory $root
Start-Process -FilePath $nodeCommand.Source -ArgumentList @("`"$vite`"", '--host', '0.0.0.0', '--port', '5193', '--strictPort') -WorkingDirectory $root
Start-Sleep -Seconds 8
Start-Process 'http://127.0.0.1:5193/'
Write-Host 'LiveSlides started at http://127.0.0.1:5193/.'
Write-Host 'Keep the API and Vite console windows open while using the app.'
Write-Host 'Close both console windows to stop the services.'
