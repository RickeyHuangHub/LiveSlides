@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
echo.
echo Review the setup result above. Press any key to close this window.
pause >nul
