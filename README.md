# VS Code Project Launcher

A sleek, modern, and cross-platform GUI application for quickly launching your recent Visual Studio Code projects.

## Features

- **Automatic Project Detection**: Scans for recently opened VS Code projects and workspaces.
- **Modern UI**: A clean, visually appealing interface built with PyQt6.
- **Custom Frameless Window**: A custom title bar with minimize, maximize, and close controls.
- **Dynamic Grid Layout**: Projects are displayed in a responsive grid that adjusts to the window size.
- **Search Functionality**: Instantly filter projects by name with the built-in search bar.
- **Ignore Folders**: A settings menu to select and hide specific projects from the main view. Your preferences are saved in an `ignored_folders.json` file.
- **Cross-Platform**: Designed to work on Windows, with potential for macOS and Linux compatibility.

## Prerequisites

- Python 3.6+
- Visual Studio Code

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/AMAMazing/VSCode-Hub.git
    cd VSCode-Hub
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the launcher script from your terminal:

```bash
python vscode_project_launcher.py
```

## How It Works

The script locates the `storage.json` file where VS Code stores information about recent workspaces and projects. It parses this file to get a list of project paths, sorts them by modification date, and displays them in the GUI. When you click on a project, it finds your VS Code executable and uses it to launch the selected project directory.
