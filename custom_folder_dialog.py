import os
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QPushButton, QScrollArea,
                             QLabel, QMessageBox, QLineEdit, QFrame, QDialog,
                             QDialogButtonBox)
from PyQt6.QtCore import Qt, QTimer, QPoint, QSize, QRectF
from PyQt6.QtGui import QIcon, QPalette, QColor, QFont, QPainter, QMouseEvent, QPixmap
from PyQt6.QtSvg import QSvgRenderer

def find_project_icon(project_path):
    try:
        for item in os.listdir(project_path):
            if item.lower().endswith('.ico'):
                return os.path.join(project_path, item)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Error searching for icon in {project_path}: {e}")
    return None

class ProjectButton(QPushButton):
    def __init__(self, project_name, project_path, icon_path=None, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(180, 160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.project_path = project_path
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if icon_path:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                icon_label.setText("📁")
                icon_label.setStyleSheet("font-size: 48px;")
        else:
            icon_label.setText("📁")
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
            ProjectButton:checked { background: #007acc; border: 1px solid #0098ff; }
        """)

class CustomFolderDialog(QDialog):
    def __init__(self, projects, ignored_folders=None, parent=None):
        super().__init__(parent)
        self.projects = projects
        if ignored_folders is None:
            self.selected_paths_set = set()
        else:
            self.selected_paths_set = set(ignored_folders)
        
        self.setWindowTitle("Select Folders to Ignore")
        self.resize(1200, 800)

        self.background_frame = QFrame(self)
        self.background_frame.setObjectName("backgroundFrame")
        self.background_frame.setStyleSheet("#backgroundFrame { background-color: #1e1e1e; border-radius: 15px; }")
        
        main_layout = QVBoxLayout(self.background_frame)
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(0)

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

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        
        self.setLayout(main_layout)

    def populate_projects(self):
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget: widget.setParent(None)
        
        BUTTON_WIDTH, HORIZONTAL_SPACING = 180, self.grid_layout.horizontalSpacing()
        margins = self.grid_layout.contentsMargins()
        GRID_HORIZONTAL_MARGINS = margins.left() + margins.right()
        
        available_width = self.width() - GRID_HORIZONTAL_MARGINS
        cols = max(1, (available_width + HORIZONTAL_SPACING) // (BUTTON_WIDTH + HORIZONTAL_SPACING))

        for i, project_path in enumerate(self.projects):
            row, col = i // cols, i % cols
            icon_path = find_project_icon(project_path)
            btn = ProjectButton(os.path.basename(project_path), project_path, icon_path=icon_path)
            if project_path in self.selected_paths_set:
                btn.setChecked(True)
            btn.toggled.connect(self.project_toggled)
            self.grid_layout.addWidget(btn, row, col)

    def project_toggled(self, checked):
        button = self.sender()
        if checked:
            self.selected_paths_set.add(button.project_path)
        else:
            self.selected_paths_set.discard(button.project_path)

    def selected_paths(self):
        return list(self.selected_paths_set)
