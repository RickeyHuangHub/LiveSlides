# Windows setup and troubleshooting

LiveSlides runs locally on Windows. The installer prepares the project-specific Python environment, installs web dependencies, and builds the standalone offline HTML player. It does not install prerequisite applications.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer. The installer detects `py.exe`, `python.exe`, or `python3.exe`; the Python Launcher is optional. If using python.exe, add Python to PATH.
- Node.js 20 or newer, including npm
- LibreOffice at `C:\Program Files\LibreOffice\program\soffice.exe`
- Internet access for the initial package installation
- Fonts used by the source PowerPoint; font substitutions can change line breaks and layout

MP4 export additionally requires FFmpeg with the `libx264` encoder. See [MP4 export](mp4-export.md). FFmpeg is not required for PPT conversion, online preview, QR codes, or offline HTML playback.

## First-time setup

1. Download or clone this repository and extract it to a local folder. A short path such as `C:\LiveSlides` is recommended.
2. Double-click `windows\install.bat`.
3. Keep the command window open until it reports **Setup complete**. First-time setup needs Internet access and may take several minutes.
4. After setup succeeds, double-click `windows\start.bat` to launch the app.

The installer writes full output to `安装日志.txt` in the project folder. It checks ports 5193 and 8787 before setup. If a copied `.venv` belongs to another computer or cannot start, the installer validates that it is the project-local `.venv` and recreates it. Do not copy a virtual environment between computers.

## Start and stop

The launcher checks Python, Node.js, LibreOffice, required build files, and port availability. It starts the API and web app, waits until both respond successfully, and only then opens [http://127.0.0.1:5193/](http://127.0.0.1:5193/). Keep the API and Vite console windows open while using the tool; close both to stop the services.

For phone testing, connect the phone and computer to the same reachable Wi-Fi and allow Windows Firewall access on a trusted private network. VPNs, guest Wi-Fi client isolation, or corporate firewalls may block the connection. This is a local test tool without user authentication; do not expose it to the public Internet or an untrusted network.

## Troubleshooting

- **A window flashes and disappears:** double-click the supplied `.bat` entry point. The wrapper keeps the setup result visible. Review `安装日志.txt` for complete installation output.
- **Python not found:** install Python 3.10+ and enable “Add Python to PATH”, then open a new command window. The Python Launcher (`py.exe`) is optional.
- **Python environment opens an interactive prompt or is broken:** rerun `windows\install.bat`; the setup script validates and, if necessary, rebuilds only the project-local `.venv`.
- **Python or npm package installation fails:** verify Internet/proxy access, disk space, and write permission to the extracted project folder, then rerun setup. Avoid keeping an editor or antivirus scanner locking files during installation.
- **Node.js or npm missing:** install Node.js 20+ with npm enabled, then rerun setup.
- **LibreOffice not found:** install it at the standard location above; the converter currently expects that path.
- **Port 5193 or 8787 is occupied:** stop the existing LiveSlides instance or identify the conflicting process before retrying. The launcher intentionally does not switch ports automatically.
- **The browser does not open:** check the API and Vite console windows. The launcher waits up to 30 seconds for each service and reports which health check timed out.
- **The web app works on the computer but not on a phone:** check Wi-Fi client isolation and Windows Firewall rules. Keep the computer running the app while using the phone link.

The repository contains source code and setup scripts, not Python, Node.js, LibreOffice, customer PowerPoint files, generated albums, music, or exported videos. Each computer needs the prerequisite software and must import its own PPTX.
