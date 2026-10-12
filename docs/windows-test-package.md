# Windows setup and troubleshooting

LiveSlides can be run locally on a Windows PC. This repository contains the same guided setup and launch scripts used for the cross-computer test package.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer, with the Python Launcher (`py.exe`)
- Node.js 20 or newer (includes npm)
- LibreOffice installed at `C:\Program Files\LibreOffice\program\soffice.exe`
- Internet access for the first dependency setup
- Fonts used by the source presentation; missing fonts can change line breaks and layout

MP4 export additionally requires FFmpeg with the `libx264` encoder. See [MP4 export](mp4-export.md).

## First-time setup

1. Download or clone this repository. If possible, place it in a short local path such as `C:\LiveSlides`.
2. Double-click `windows\install.bat`.
3. Keep the command window open until it reports **Setup complete**. It creates a local Python virtual environment and installs the Python and web dependencies. First-time installation needs internet access.
4. If setup reports an error, read the message in the same window. Common causes are a missing Python Launcher, old Node.js, LibreOffice installed in a non-standard location, or a blocked network connection. Install/fix the prerequisite and run the setup script again.

## Start LiveSlides

Double-click `windows\start.bat`. It opens the local web app at [http://127.0.0.1:5193/](http://127.0.0.1:5193/). Keep the API and web-server console windows open while using LiveSlides; closing them stops the app. To stop, close both service windows.

For phone testing on the same Wi-Fi, use the computer's LAN address and allow the Windows Firewall prompt on a trusted private network. The app currently has no login or user authorization; do not expose it to the public Internet or an untrusted network.

## Troubleshooting

- **A console flashes and disappears:** use the supplied `.bat` entry point, not the PowerShell helper directly. The batch wrapper keeps the window open after setup errors.
- **“Python Launcher not found”:** install Python 3.10+ and enable the Python Launcher, then open a new command window.
- **“Node.js 20+ required”:** install/update Node.js, then rerun setup.
- **LibreOffice not found:** install it in the standard path above; the current converter does not auto-discover other installation paths.
- **Dependencies fail to download:** confirm internet/proxy access, then rerun `windows\install.bat`.
- **Port 5193 is occupied:** close the other service using that port. The launcher deliberately fails instead of silently switching to another port.

The scripts install dependencies; they do not package Python, Node.js, LibreOffice or customer files into the repository. Each computer must have the listed prerequisites installed. Customer PPTX files, generated albums, music, exports and configuration data are intentionally excluded from Git.
