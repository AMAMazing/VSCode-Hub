import os
import json
import subprocess
import sys
import ctypes
from urllib.parse import unquote
import logging
from datetime import datetime

# PyQt Imports
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QPushButton, QScrollArea,
                             QLabel, QMessageBox, QLineEdit, QFrame, QSystemTrayIcon,
                             QMenu)
from PyQt6.QtCore import Qt, QTimer, QPoint, QSize, QRectF, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QPalette, QColor, QFont, QPainter, QMouseEvent, QPixmap, QAction
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

# Attempt imports for your custom modules
try:
    from svg_icons import SVG_ICONS
    from custom_folder_dialog import CustomFolderDialog
except ImportError:
    # Fallback if running standalone or missing files
    SVG_ICONS = {} 
    class CustomFolderDialog: pass

logging.basicConfig(filename='launcher.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')

CACHE_FILE = 'project_cache.json'
CONFIG_FILE = 'launcher_config.json'
SOCKET_NAME = 'VSCodeLauncherInstance'

# --- WORKER THREAD FOR BACKGROUND SCANNING ---
class ProjectScannerWorker(QThread):
    finished = pyqtSignal(list, str) 

    def __init__(self, ignored_folders):
        super().__init__()
        self.ignored_folders = ignored_folders

    def find_vscode_executable(self):
        # Check config first
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    path = config.get('vscode_path')
                    if path and os.path.exists(path):
                        return path
            except:
                pass

        logging.info("Searching for VS Code executable...")
        appdata_path = os.environ.get('LOCALAPPDATA', '')
        program_files = os.environ.get('ProgramFiles', '')
        program_files_x86 = os.environ.get('ProgramFiles(x86)', '')
        possible_paths = [
            os.path.join(appdata_path, 'Programs', 'Microsoft VS Code', 'Code.exe'),
            os.path.join(appdata_path, 'Programs', 'Microsoft VS Code', 'bin', 'code.cmd'),
            os.path.join(program_files, 'Microsoft VS Code', 'Code.exe'),
            os.path.join(program_files, 'Microsoft VS Code', 'bin', 'code.cmd'),
        ]
        if program_files_x86:
            possible_paths.extend([
                os.path.join(program_files_x86, 'Microsoft VS Code', 'Code.exe'),
            ])
        
        found_path = None
        for path in possible_paths:
            if os.path.exists(path):
                found_path = path
                break
        
        if not found_path:
            try:
                result = subprocess.run(['where', 'code'], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                first_path = result.stdout.strip().splitlines()[0]
                if os.path.exists(first_path):
                    found_path = first_path
            except:
                pass
        
        if found_path:
            with open(CONFIG_FILE, 'w') as f:
                json.dump({'vscode_path': found_path}, f)
        
        return found_path

    def find_project_icon(self, project_path):
        common_names = ['favicon.ico', 'icon.ico', 'logo.ico', 'app.ico']
        try:
            # Quick check for common names first
            for name in common_names:
                p = os.path.join(project_path, name)
                if os.path.exists(p):
                    return p
            # Fallback to scanning dir (limit 50 files)
            files = os.listdir(project_path)
            for item in files[:50]: 
                if item.lower().endswith('.ico'):
                    return os.path.join(project_path, item)
        except:
            pass
        return None

    def run(self):
        vscode_path = self.find_vscode_executable()
        try:
            possible_paths = [
                os.path.join(os.environ['APPDATA'], 'Code', 'User', 'globalStorage', 'storage.json'),
                os.path.join(os.environ['APPDATA'], 'Code - Insiders', 'User', 'globalStorage', 'storage.json'),
                os.path.join(os.environ['APPDATA'], 'VSCodium', 'User', 'globalStorage', 'storage.json')
            ]
            storage_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    storage_path = path
                    break
            
            if not storage_path:
                self.finished.emit([], vscode_path)
                return

            with open(storage_path, 'r', encoding='utf-8') as f:
                storage_data = json.load(f)
            
            project_uris = list(storage_data.get('profileAssociations', {}).get('workspaces', {}).keys())
            final_projects = []
            
            for uri in project_uris:
                if uri.startswith('file:///'):
                    path = unquote(uri[8:]).replace('/', '\\\\')
                    
                    if path in self.ignored_folders:
                        continue

                    if os.path.isdir(path):
                        mtime = os.path.getmtime(path)
                        icon = self.find_project_icon(path)
                        final_projects.append({
                            "path": path,
                            "name": os.path.basename(path),
                            "mtime": mtime,
                            "icon": icon
                        })

            final_projects.sort(key=lambda x: x['mtime'], reverse=True)
            
            with open(CACHE_FILE, 'w') as f:
                json.dump(final_projects, f)

            self.finished.emit(final_projects, vscode_path)

        except Exception as e:
            logging.error(f"Scanner error: {e}")
            self.finished.emit([], vscode_path)

# --- UI CLASSES ---

class TitleBarButton(QPushButton):
    def __init__(self, icon_name, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._renderer = QSvgRenderer()
        self.setIconName(icon_name)

    def setIconName(self, name):
        self._icon_name = name
        if name in SVG_ICONS:
            self._renderer.load(SVG_ICONS[self._icon_name].encode('utf-8'))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        icon_size = self.iconSize()
        rect = self.rect()
        x = (rect.width() - icon_size.width()) / 2
        y = (rect.height() - icon_size.height()) / 2
        target_rect = QRectF(x, y, icon_size.width(), icon_size.height())
        self._renderer.render(painter, target_rect)

    def iconSize(self):
        return QSize(16, 16)

class ProjectButton(QPushButton):
    def __init__(self, project_data, parent=None):
        super().__init__(parent)
        self.project_path = project_data['path']
        self.setFixedSize(180, 160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_path = project_data.get('icon')
        if icon_path and os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self._set_default_icon(icon_label)
        else:
            self._set_default_icon(icon_label)
            
        layout.addWidget(icon_label)
        
        name_label = QLabel(project_data['name'])
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #e1e1e1;")
        layout.addWidget(name_label)

        if project_data.get('mtime'):
            date_str = datetime.fromtimestamp(project_data['mtime']).strftime('%b %d, %Y')
            date_label = QLabel(date_str)
            date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            date_label.setStyleSheet("font-size: 10px; color: #888;")
            layout.addWidget(date_label)

        self.setStyleSheet("""
            ProjectButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2d2d30, stop:1 #252526);
                           border: 1px solid #3e3e42; border-radius: 12px; padding: 16px; }
            ProjectButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3e3e42, stop:1 #2d2d30);
                                 border: 1px solid #007acc; }
            ProjectButton:pressed { background: #1e1e1e; border: 1px solid #0098ff; }
        """)

    def _set_default_icon(self, label):
        label.setText("📁")
        label.setStyleSheet("font-size: 48px; color: #d4d4d4;")

class VSCodeLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ignored_folders = self.load_ignored_folders()
        self.projects_data = []
        self.vscode_exe = None
        self.drag_pos = QPoint()
        
        self.init_ui()
        self.setup_tray()
        
        # Load cache + Start Scan
        self.load_from_cache()
        self.start_scan()

        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(100)
        self.resize_timer.timeout.connect(self.populate_projects)

    def start_scan(self):
        self.scanner = ProjectScannerWorker(self.ignored_folders)
        self.scanner.finished.connect(self.on_scan_finished)
        self.scanner.start()

    def trim_memory(self):
        """Forces Windows to trim working set memory"""
        if sys.platform == 'win32':
            try:
                ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
            except Exception:
                pass

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("VSCode Hub_icon.ico")) 
        
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_window)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.force_close)
        
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        self.tray_icon.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window()

    def show_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self.search_input.setFocus()
        self.search_input.selectAll()
        self.start_scan()

    def closeEvent(self, event):
        # Hide window and Trim Memory
        event.ignore()
        self.hide()
        self.trim_memory()
        self.tray_icon.showMessage(
            "VS Code Hub",
            "Minimised to tray. Click the shortcut again to open instantly.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def force_close(self):
        QApplication.instance().quit()

    def load_ignored_folders(self):
        try:
            with open('ignored_folders.json', 'r') as f:
                return json.load(f)
        except:
            return []

    def save_ignored_folders(self):
        with open('ignored_folders.json', 'w') as f:
            json.dump(self.ignored_folders, f, indent=4)

    def load_from_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    self.projects_data = json.load(f)
                self.populate_projects()
                self.count_label.setText(f"{len(self.projects_data)} projects (Cached)")
            except Exception as e:
                logging.error(f"Cache load failed: {e}")

    def on_scan_finished(self, projects, vscode_path):
        self.vscode_exe = vscode_path
        current_paths = [p['path'] for p in self.projects_data]
        new_paths = [p['path'] for p in projects]
        
        if current_paths != new_paths:
            self.projects_data = projects
            self.filter_projects()
            self.count_label.setText(f"{len(self.projects_data)} projects")
        else:
             self.count_label.setText(f"{len(self.projects_data)} projects")

    def add_ignored_folder(self):
        current_paths = [p['path'] for p in self.projects_data]
        try:
            dialog = CustomFolderDialog(current_paths, self.ignored_folders, self)
            if dialog.exec():
                self.ignored_folders = dialog.selected_paths()
                self.save_ignored_folders()
                self.start_scan()
        except NameError:
            QMessageBox.information(self, "Info", "CustomFolderDialog module not found.")

    def init_ui(self):
        self.setWindowTitle("VS Code Project Launcher")
        self.resize(1200, 800)

        self.background_frame = QFrame(self)
        self.background_frame.setObjectName("backgroundFrame")
        self.background_frame.setStyleSheet("#backgroundFrame { background-color: #1e1e1e; border-radius: 15px; }")
        self.setCentralWidget(self.background_frame)
        
        main_layout = QVBoxLayout(self.background_frame)
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(0)

        self.header = self.create_header()
        main_layout.addWidget(self.header)

        search_widget = self.create_search_bar()
        main_layout.addWidget(search_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: #1e1e1e; width: 12px; margin: 0; }
            QScrollBar::handle:vertical { background: #3e3e42; border-radius: 6px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #4e4e52; }
        """)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        
        # Grid Layout Setup
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setSpacing(20)
        self.grid_layout.setContentsMargins(30, 30, 30, 30)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

    def create_header(self):
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet("""
            QFrame { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007acc, stop:1 #005a9e);
                     border-top-left-radius: 14px; border-top-right-radius: 14px; }
        """)
        header.setMouseTracking(True)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 0, 5, 0)
        title = QLabel("VS Code Projects")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: white; background: transparent;")
        layout.addWidget(title)
        layout.addStretch()

        self.count_label = QLabel("Loading...")
        self.count_label.setStyleSheet("font-size: 13px; color: rgba(255, 255, 255, 0.8); background: transparent; margin-right: 20px;")
        layout.addWidget(self.count_label)
        
        btn_style = """
            QPushButton { background-color: transparent; border-radius: 5px; }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.2); }
            QPushButton:pressed { background-color: rgba(255, 255, 255, 0.1); }
        """

        settings_btn = TitleBarButton("ignore")
        settings_btn.setStyleSheet(btn_style)
        settings_btn.clicked.connect(self.add_ignored_folder)
        layout.addWidget(settings_btn)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(0)

        minimize_btn = TitleBarButton("minimize")
        minimize_btn.setStyleSheet(btn_style)
        minimize_btn.clicked.connect(self.showMinimized)
        
        self.maximize_btn = TitleBarButton("maximize")
        self.maximize_btn.setStyleSheet(btn_style)
        self.maximize_btn.clicked.connect(self.toggle_maximize_restore)
        
        close_btn = TitleBarButton("close")
        close_btn.setStyleSheet(btn_style + "QPushButton:hover { background-color: #E81123; }")
        close_btn.clicked.connect(self.close)
        
        controls_layout.addWidget(minimize_btn)
        controls_layout.addWidget(self.maximize_btn)
        controls_layout.addWidget(close_btn)
        layout.addLayout(controls_layout)
        return header

    def toggle_maximize_restore(self):
        if self.isMaximized():
            self.showNormal()
            self.background_frame.setStyleSheet("#backgroundFrame { background-color: #1e1e1e; border-radius: 15px; }")
            self.header.setStyleSheet("QFrame { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007acc, stop:1 #005a9e); border-top-left-radius: 14px; border-top-right-radius: 14px; }")
        else:
            self.showMaximized()
            self.background_frame.setStyleSheet("#backgroundFrame { background-color: #1e1e1e; border-radius: 0px; }")
            self.header.setStyleSheet("QFrame { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007acc, stop:1 #005a9e); border-top-left-radius: 0px; border-top-right-radius: 0px; }")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.header.underMouse():
                self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.drag_pos = QPoint()
        event.accept()
    
    def create_search_bar(self):
        search_widget = QFrame()
        search_widget.setFixedHeight(70)
        search_widget.setStyleSheet("background: #252526; border-bottom: 1px solid #3e3e42;")
        layout = QHBoxLayout(search_widget)
        layout.setContentsMargins(30, 15, 30, 15)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search projects...")
        self.search_input.textChanged.connect(self.filter_projects)
        self.search_input.setStyleSheet("""
            QLineEdit { background: #3c3c3c; border: 2px solid #3e3e42; border-radius: 8px;
                        padding: 12px 16px; font-size: 14px; color: #e1e1e1; }
            QLineEdit:focus { border: 2px solid #007acc; background: #2d2d30; }
        """)
        layout.addWidget(self.search_input)
        return search_widget
    
    def resizeEvent(self, event):
        self.resize_timer.start()
        super().resizeEvent(event)

    def populate_projects(self, projects_to_show=None):
        # 1. Clean up existing widgets
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget: widget.setParent(None)
        
        # 2. Reset any previous layout stretches
        for r in range(self.grid_layout.rowCount()):
            self.grid_layout.setRowStretch(r, 0)
        for c in range(self.grid_layout.columnCount()):
            self.grid_layout.setColumnStretch(c, 0)

        data_list = projects_to_show if projects_to_show is not None else self.projects_data

        BUTTON_WIDTH, HORIZONTAL_SPACING = 180, self.grid_layout.horizontalSpacing()
        margins = self.grid_layout.contentsMargins()
        GRID_HORIZONTAL_MARGINS = margins.left() + margins.right()
        try:
            viewport_width = self.scroll_area.viewport().width()
            if viewport_width == 0: viewport_width = self.width()
            available_width = viewport_width - GRID_HORIZONTAL_MARGINS
        except AttributeError:
            available_width = self.width() - GRID_HORIZONTAL_MARGINS
        
        cols = max(1, (available_width + HORIZONTAL_SPACING) // (BUTTON_WIDTH + HORIZONTAL_SPACING))

        # 3. Add Buttons
        last_row = 0
        for i, proj_data in enumerate(data_list):
            row, col = i // cols, i % cols
            last_row = row
            btn = ProjectButton(proj_data)
            btn.clicked.connect(lambda checked, p=proj_data['path']: self.open_project(p))
            self.grid_layout.addWidget(btn, row, col)
            
        # 4. Add spacer at bottom and right to force Top-Left alignment
        self.grid_layout.setRowStretch(last_row + 1, 1)
        self.grid_layout.setColumnStretch(cols, 1)
    
    def filter_projects(self):
        search_text = self.search_input.text().lower()
        filtered = [p for p in self.projects_data if search_text in p['name'].lower()]
        self.populate_projects(filtered)
    
    def open_project(self, path):
        if not self.vscode_exe:
            scanner = ProjectScannerWorker([])
            self.vscode_exe = scanner.find_vscode_executable()

        if not self.vscode_exe:
            QMessageBox.critical(self, "Error", "Could not find VS Code executable (Code.exe).")
            return
        try:
            subprocess.Popen([self.vscode_exe, path], creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            self.hide()
            self.trim_memory()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open project: {e}")



def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) 

    # --- SINGLE INSTANCE CHECK ---
    socket = QLocalSocket()
    socket.connectToServer(SOCKET_NAME)
    
    if socket.waitForConnected(500):
        # App is already running. Send "SHOW" command and quit this new instance.
        socket.write(b"SHOW")
        socket.flush()
        socket.waitForBytesWritten(1000)
        sys.exit(0)
    
    # If we are here, we are the first instance. Create Server.
    server = QLocalServer()
    # Cleanup previous socket file if it exists (crashed)
    QLocalServer.removeServer(SOCKET_NAME)
    server.listen(SOCKET_NAME)
    
    app.setStyle('Fusion')
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = VSCodeLauncher()
    window.setWindowFlag(Qt.WindowType.FramelessWindowHint)
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    
    # Handle incoming connections from new instances
    def handle_connection():
        client_socket = server.nextPendingConnection()
        if client_socket.waitForReadyRead(1000):
            command = client_socket.readAll().data().decode()
            if command == "SHOW":
                window.show_window()

    server.newConnection.connect(handle_connection)

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()