# VS Code Hub (Project Launcher)

A lightning-fast, memory-efficient GUI application for quickly launching your recent Visual Studio Code projects. Designed to sit in your system tray and open instantly.

## Features

- **🚀 Instant Launch**: The app runs in "Resident Mode" (System Tray). Clicking the shortcut wakes it up instantly (<0.1s).
- **🧠 Memory Optimized**: Automatically trims RAM usage when minimized to the tray to save system resources.
- **📂 Automatic Detection**: Scans VS Code history (`storage.json`) in the background without freezing the UI.
- **🔍 Quick Search**: Instantly filter projects by name.
- **🚫 Ignore System**: Right-click or use the settings menu to hide specific folders. Preferences saved to `ignored_folders.json`.
- **🎨 Modern UI**: A custom frameless window with a responsive grid layout built with PyQt6.

## Prerequisites

- Python 3.6+
- Visual Studio Code

## Development Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/AMAMazing/VSCode-Hub.git
    cd VSCode-Hub
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    pip install nuitka zstandard
    ```

---

## 🛠️ Compiling to EXE

To make the app launch instantly, it is recommended to compile it using Nuitka.

### Important: Updating the App
Because the app runs in the background (Resident Mode), **you must fully stop it before re-compiling**, otherwise you will get an "Access Denied" error.

**1. Stop the running instance (PowerShell):**
```powershell
Stop-Process -Name "vscode_project_launcher" -Force -ErrorAction SilentlyContinue
```

**2. Build the executable:**
Run the following command to compile the app into a standalone folder with a custom icon and no console window:

```powershell
python -m nuitka --standalone --enable-plugin=pyqt6 --windows-console-mode=disable --windows-icon-from-ico="VSCode Hub_icon.ico" vscode_project_launcher.py
```

### How to Use the Compiled App
1.  Go to the newly created folder `vscode_project_launcher.dist`.
2.  Right-click `vscode_project_launcher.exe` and select **Create Shortcut**.
3.  Move this shortcut to your Desktop or pin it to your Taskbar.
4.  **Click once** to open. **Click "Close"** to minimize to tray. **Click again** to wake instantly.

---

## How It Works

1.  **Detection**: The script locates the `storage.json` file where VS Code stores workspace history.
2.  **Caching**: It caches the list to a local JSON file so the UI loads immediately upon start.
3.  **Background Threading**: A worker thread scans for icon files and validates paths in the background so the interface never freezes.
4.  **Socket Communication**: It uses a local socket server to ensure only one instance runs. If you try to open it while it's hidden, it sends a signal to the running instance to show itself immediately.