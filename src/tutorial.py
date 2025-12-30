from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QCheckBox, QStackedWidget, QWidget, QFrame)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QPixmap, QFont

class TutorialStep(QWidget):
    def __init__(self, title, description, image_path=None):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        # Image
        if image_path:
            lbl_img = QLabel()
            pix = QPixmap(image_path)
            if not pix.isNull():
                lbl_img.setPixmap(pix.scaled(560, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_img.setStyleSheet("border: 1px solid #444; border-radius: 4px; background: #000;")
            layout.addWidget(lbl_img)

        # Description
        lbl_desc = QLabel(description)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("font-size: 13px; color: #cccccc; line-height: 1.4;")
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(lbl_desc)
        
        layout.addStretch()

class TutorialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to FrameTamer")
        self.setFixedSize(600, 550)
        self.setStyleSheet("background-color: #2b2b2b; color: #ddd;")
        
        # Load local graphics (or absolute paths from artifacts if dev)
        # For implementation, we'll use the ones generated in the artifacts dir
        # In a real app, these would be in a resource folder.
        # We'll use the absolute paths for now.
        art_dir = "C:/Users/mattg/.gemini/antigravity/brain/3e4c7fee-f5d7-40ff-9557-63e5e836b35a/"
        
        self.steps_data = [
            {
                "title": "Welcome to FrameTamer",
                "desc": "FrameTamer is a professional utility for designers and makers to precisely calculate frame dimensions, mat borders, and output specifications. Let's take a quick look at the features.",
                "img": art_dir + "tutorial_welcome_1767113457984.png"
            },
            {
                "title": "1. Load Your Media",
                "desc": "Import your photos directly or browse your Google Photos library. You can also extract frame textures from existing photos to see exactly how your art will look in a real frame.",
                "img": art_dir + "tutorial_source_fixed_1767113559744.png"
            },
            {
                "title": "2. Define Dimensions",
                "desc": "Enter the precise Aperture (the visible opening) and the Frame Profile. We track the 'Face Width' and 'Rabbet Depth' to ensure every calculation is millimetre-perfect.",
                "img": art_dir + "tutorial_dimensions_fixed_1767113592783.png"
            },
            {
                "title": "3. Master Matting",
                "desc": "Choose between 'Float' or 'Overmat' mounting. FrameTamer automatically calculates the necessary mat board cuts and hardware requirements based on your choices.",
                "img": art_dir + "tutorial_matting_fixed_1767113624330.png"
            },
            {
                "title": "4. Visual Polish",
                "desc": "Customize the frame and mat colors to match your vision. Our visualization engine renders realistic shadows and textures for an accurate preview.",
                "img": art_dir + "tutorial_appearance_fixed_1767113649110.png"
            },
            {
                "title": "5. Real-time Results",
                "desc": "The MetricCard provides a live-updated list of all final dimensions. When you're ready, export a high-res PDF blueprint or a JPEG for client approval.",
                "img": art_dir + "tutorial_metrics_1767113502630.png"
            }
        ]
        
        self.current_index = 0
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Content
        self.stack = QStackedWidget()
        for step in self.steps_data:
            self.stack.addWidget(TutorialStep(step["title"], step["desc"], step["img"]))
        main_layout.addWidget(self.stack)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #444; max-height: 1px;")
        main_layout.addWidget(line)

        # Footer
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(15, 10, 15, 15)

        self.cb_startup = QCheckBox("Show at startup")
        self.cb_startup.setChecked(True)
        self.cb_startup.setStyleSheet("color: #888; font-size: 11px;")
        footer_layout.addWidget(self.cb_startup)

        footer_layout.addStretch()

        self.btn_back = QPushButton("Back")
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self.prev_step)
        
        self.btn_next = QPushButton("Next")
        self.btn_next.setStyleSheet("background-color: #0078d7; color: white; font-weight: bold; padding: 5px 15px;")
        self.btn_next.clicked.connect(self.nxt_step)

        self.btn_exit = QPushButton("Exit")
        self.btn_exit.clicked.connect(self.close)

        footer_layout.addWidget(self.btn_back)
        footer_layout.addWidget(self.btn_next)
        footer_layout.addWidget(self.btn_exit)
        
        main_layout.addWidget(footer)

    def nxt_step(self):
        if self.current_index < len(self.steps_data) - 1:
            self.current_index += 1
            self.stack.setCurrentIndex(self.current_index)
            self.btn_back.setEnabled(True)
            if self.current_index == len(self.steps_data) - 1:
                self.btn_next.setText("Finish")
        else:
            self.save_and_close()

    def prev_step(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.stack.setCurrentIndex(self.current_index)
            self.btn_next.setText("Next")
            if self.current_index == 0:
                self.btn_back.setEnabled(False)

    def save_and_close(self):
        settings = QSettings("MattG", "FrameTamer")
        settings.setValue("startup/show_tutorial", self.cb_startup.isChecked())
        self.accept()

    @staticmethod
    def show_if_needed(parent=None):
        settings = QSettings("MattG", "FrameTamer")
        show = settings.value("startup/show_tutorial", True, type=bool)
        if show:
            dlg = TutorialDialog(parent)
            dlg.exec()
