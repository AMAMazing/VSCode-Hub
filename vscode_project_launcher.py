import os
import json
import subprocess
import sys
from urllib.parse import unquote
import logging
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QPushButton, QScrollArea,
                             QLabel, QMessageBox, QLineEdit, QFrame)
from PyQt6.QtCore import Qt, QTimer, QPoint, QSize, QRectF
from PyQt6.QtGui import QIcon, QPalette, QColor, QFont, QPainter, QMouseEvent
from PyQt6.QtSvg import QSvgRenderer

logging.basicConfig(filename='launcher.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')

SVG_ICONS = {
    "minimize": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M20 12H4" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "maximize": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M8 3H5C3.89543 3 3 3.89543 3 5V8" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M16 3H19C20.1046 3 21 3.89543 21 5V8" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M8 21H5C3.89543 21 3 20.1046 3 19V16" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M16 21H19C20.1046 21 21 20.1046 21 19V16" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "restore": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M8 21H5C3.89543 21 3 20.1046 3 19V14" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M21 10V5C21 3.89543 20.1046 3 19 3H14" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M10 21V19C10 17.8954 10.8954 17 12 17H19C20.1046 17 21 17.8954 21 19V21H10Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "close": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M18 6L6 18" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M6 6L18 18" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""
}

class TitleBarButton(QPushButton):
    def __init__(self, icon_name, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._renderer = QSvgRenderer()
        self.setIconName(icon_name)

    def setIconName(self, name):
        self._icon_name = name
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

def find_vscode_executable():
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
            os.path.join(program_files_x86, 'Microsoft VS Code', 'bin', 'code.cmd'),
        ])
    for path in possible_paths:
        if os.path.exists(path):
            logging.info(f"Found executable at: {path}")
            return path
    logging.info("Executable not found in common paths. Falling back to 'where code'.")
    try:
        result = subprocess.run(['where', 'code'], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        first_path = result.stdout.strip().splitlines()[0]
        if os.path.exists(first_path):
            logging.info(f"Found executable via 'where' command: {first_path}")
            return first_path
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError) as e:
        logging.error(f"'where code' command failed: {e}")
    logging.error("VS Code executable not found anywhere.")
    return None

def get_vscode_projects():
    try:
        logging.info("Searching for projects file...")
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
            logging.error("Could not find storage.json in any known location.")
            return []
        with open(storage_path, 'r', encoding='utf-8') as f:
            storage_data = json.load(f)
        project_uris = list(storage_data.get('profileAssociations', {}).get('workspaces', {}).keys())
        cleaned_paths = []
        for uri in project_uris:
            if uri.startswith('file:///'):
                path = unquote(uri[8:]).replace('/', '\\')
                cleaned_paths.append(path)
        folder_paths = [p for p in cleaned_paths if os.path.isdir(p)]
        return sorted(folder_paths, key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)
    except Exception as e:
        logging.critical(f"An unhandled exception in get_vscode_projects: {e}", exc_info=True)
        return []

class ProjectButton(QPushButton):
    def __init__(self, project_name, project_path, parent=None):
        super().__init__(parent)
        self.setFixedSize(180, 160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        icon_label = QLabel("📁")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 48px;")
        layout.addWidget(icon_label)
        name_label = QLabel(project_name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #e1e1e1;")
        layout.addWidget(name_label)
        try:
            mtime = os.path.getmtime(project_path)
            date_str = datetime.fromtimestamp(mtime).strftime('%b %d, %Y')
        except:
            date_str = ""
        if date_str:
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

class VSCodeLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.projects = get_vscode_projects()
        self.filtered_projects = self.projects.copy()

        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(100)
        self.resize_timer.timeout.connect(self.populate_projects)

        self.drag_pos = QPoint()
        self.init_ui()

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

        if not self.projects:
            self.show_no_projects_message()
            QTimer.singleShot(2000, self.close)
            return

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: #1e1e1e; width: 12px; margin: 0; }
            QScrollBar::handle:vertical { background: #3e3e42; border-radius: 6px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #4e4e52; }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(scroll_content)
        self.grid_layout.setSpacing(20)
        self.grid_layout.setContentsMargins(30, 30, 30, 30)

        self.populate_projects()
        self.scroll_area.setWidget(scroll_content)
        main_layout.addWidget(self.scroll_area)

    def resizeEvent(self, event):
        self.resize_timer.start()
        super().resizeEvent(event)

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
        self.count_label = QLabel(f"{len(self.projects)} projects")
        self.count_label.setStyleSheet("font-size: 13px; color: rgba(255, 255, 255, 0.8); background: transparent; margin-right: 20px;")
        layout.addWidget(self.count_label)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(0)
        btn_style = """
            QPushButton { background-color: transparent; border-radius: 5px; }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.2); }
            QPushButton:pressed { background-color: rgba(255, 255, 255, 0.1); }
        """
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
            self.maximize_btn.setIconName("maximize")
            self.background_frame.setStyleSheet("#backgroundFrame { background-color: #1e1e1e; border-radius: 15px; }")
        else:
            self.showMaximized()
            self.maximize_btn.setIconName("restore")
            self.background_frame.setStyleSheet("#backgroundFrame { background-color: #1e1e1e; border-radius: 0px; }")

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
    
    def populate_projects(self):
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget: widget.setParent(None)
        
        BUTTON_WIDTH, HORIZONTAL_SPACING = 180, self.grid_layout.horizontalSpacing()
        margins = self.grid_layout.contentsMargins()
        GRID_HORIZONTAL_MARGINS = margins.left() + margins.right()
        try:
            available_width = self.scroll_area.viewport().width() - GRID_HORIZONTAL_MARGINS
        except AttributeError:
            available_width = self.width() - GRID_HORIZONTAL_MARGINS
        cols = max(1, (available_width + HORIZONTAL_SPACING) // (BUTTON_WIDTH + HORIZONTAL_SPACING))

        for i, project_path in enumerate(self.filtered_projects):
            row, col = i // cols, i % cols
            btn = ProjectButton(os.path.basename(project_path), project_path)
            btn.clicked.connect(lambda checked, p=project_path: self.open_project(p))
            self.grid_layout.addWidget(btn, row, col)
    
    def filter_projects(self):
        search_text = self.search_input.text().lower()
        self.filtered_projects = [p for p in self.projects if search_text in os.path.basename(p).lower()]
        self.count_label.setText(f"{len(self.filtered_projects)} projects")
        self.populate_projects()
    
    def open_project(self, path):
        vscode_exe = find_vscode_executable()
        if not vscode_exe:
            QMessageBox.critical(self, "Error", "Could not find VS Code executable (Code.exe).")
            return
        try:
            subprocess.Popen([vscode_exe, path], creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            QTimer.singleShot(1000, self.close)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open project: {e}")
    
    def show_no_projects_message(self):
        QMessageBox.information(self, "No Projects", "No recent VS Code projects found.")

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = VSCodeLauncher()
    window.setWindowFlag(Qt.WindowType.FramelessWindowHint)
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
