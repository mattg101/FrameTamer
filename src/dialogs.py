from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFileDialog, QSlider, QSizePolicy,
                             QInputDialog, QListWidget, QListWidgetItem, QAbstractItemView)
from PyQt6.QtCore import Qt, QRectF, QPointF, QEvent, QSize
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QTransform, QIcon
import os

class TextureSamplerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Extract Frame Texture")
        self.resize(1000, 800)
        
        # Data
        self.pixmap_orig = None
        self.pixmap_rotated = None # Cache rotated version
        self.selection_norm = QRectF(0.2, 0.2, 0.6, 0.1) 
        
        # View State
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.rotation = 0
        
        # Interaction State
        self.dragging_selection = False
        self.panning = False
        self.last_mouse_pos = QPointF()
        self.selection_start_norm = QPointF()

        # Layout
        layout = QVBoxLayout(self)
        
        # Header / Instructions
        info = QLabel("<b>Controls:</b><br>• <b>Left Click + Drag:</b> Select Texture Area<br>• <b>Right Click + Drag:</b> Pan Image<br>• <b>Scroll Wheel:</b> Zoom In/Out<br>• <b>Slider:</b> Straighten Image")
        info.setStyleSheet("color: #ccc;")
        layout.addWidget(info)

        # Preview Label (The Canvas)
        self.lbl_preview = QLabel("Load Image...")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setStyleSheet("background-color: #202020; border: 1px solid #555;")
        self.lbl_preview.setMouseTracking(True)
        self.lbl_preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.lbl_preview.installEventFilter(self)
        layout.addWidget(self.lbl_preview, 1)

        # Bottom Controls
        h_ctrl = QHBoxLayout()
        
        btn_load = QPushButton("Load Image"); btn_load.clicked.connect(self.load_image)
        btn_load.setStyleSheet("padding: 5px 10px;")
        h_ctrl.addWidget(btn_load)
        
        h_ctrl.addWidget(QLabel("Straighten:"))
        self.slider_rot = QSlider(Qt.Orientation.Horizontal)
        self.slider_rot.setRange(-450, 450); self.slider_rot.setValue(0) # +/- 45 deg
        self.slider_rot.valueChanged.connect(self.on_rotation_changed)
        h_ctrl.addWidget(self.slider_rot)
        
        btn_reset = QPushButton("Reset View"); btn_reset.clicked.connect(self.reset_view)
        h_ctrl.addWidget(btn_reset)

        btn_ok = QPushButton("Use Texture"); btn_ok.clicked.connect(self.accept)
        btn_ok.setStyleSheet("background-color: #0078d7; font-weight: bold; padding: 5px 15px;")
        h_ctrl.addWidget(btn_ok)
        
        btn_save = QPushButton("Save to Library"); btn_save.clicked.connect(self.save_to_library)
        btn_save.setStyleSheet("background-color: #28a745; color: white; padding: 5px 15px;")
        h_ctrl.addWidget(btn_save)
        
        layout.addLayout(h_ctrl)

    def save_to_library(self):
        tex = self.get_texture()
        if not tex: return
        name, ok = QInputDialog.getText(self, "Save Texture", "Texture Name:")
        if ok and name:
            if not os.path.exists("textures"): os.makedirs("textures")
            path = os.path.join("textures", f"{name}.png")
            tex.save(path)

    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.pixmap_orig = QPixmap(path)
            self.slider_rot.setValue(0)
            self.reset_view()
            self.on_rotation_changed()

    def reset_view(self):
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.selection_norm = QRectF(0.2, 0.4, 0.6, 0.2)
        self.update_display()

    def on_rotation_changed(self):
        if not self.pixmap_orig: return
        deg = self.slider_rot.value() / 10.0
        t = QTransform().rotate(deg)
        self.pixmap_rotated = self.pixmap_orig.transformed(t, Qt.TransformationMode.SmoothTransformation)
        # FIX: Do NOT reset view here, just update display to keep zoom/pan
        self.update_display()

    def get_transforms(self):
        """Returns (draw_rect, scale) for the image on the label"""
        if not self.pixmap_rotated: return QRectF(), 1.0
        
        Lw, Lh = self.lbl_preview.width(), self.lbl_preview.height()
        Iw, Ih = self.pixmap_rotated.width(), self.pixmap_rotated.height()
        
        if Iw == 0 or Ih == 0: return QRectF(), 1.0
        fit_scale = min(Lw/Iw, Lh/Ih) * 0.9
        
        final_scale = fit_scale * self.zoom
        Dw, Dh = Iw * final_scale, Ih * final_scale
        
        Cx, Cy = Lw / 2, Lh / 2
        Ix = Cx - (Dw / 2) + self.pan.x()
        Iy = Cy - (Dh / 2) + self.pan.y()
        
        return QRectF(Ix, Iy, Dw, Dh), final_scale

    def update_display(self):
        if not self.pixmap_rotated: return
        
        w, h = self.lbl_preview.width(), self.lbl_preview.height()
        if w <= 0 or h <= 0: return

        canvas = QPixmap(w, h)
        canvas.fill(QColor(32, 32, 32))
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        img_rect, scale = self.get_transforms()
        p.drawPixmap(img_rect.toRect(), self.pixmap_rotated)
        
        sx = img_rect.x() + self.selection_norm.x() * img_rect.width()
        sy = img_rect.y() + self.selection_norm.y() * img_rect.height()
        sw = self.selection_norm.width() * img_rect.width()
        sh = self.selection_norm.height() * img_rect.height()
        
        sel_screen = QRectF(sx, sy, sw, sh)
        
        p.setPen(QPen(QColor(0, 255, 0), 2))
        p.setBrush(QColor(0, 255, 0, 40))
        p.drawRect(sel_screen)
        
        p.setBrush(QColor(255, 255, 255))
        p.setPen(Qt.PenStyle.NoPen)
        handle_sz = 8
        for pt in [sel_screen.topLeft(), sel_screen.topRight(), sel_screen.bottomLeft(), sel_screen.bottomRight()]:
            p.drawRect(QRectF(pt.x() - handle_sz/2, pt.y() - handle_sz/2, handle_sz, handle_sz))

        p.end()
        self.lbl_preview.setPixmap(canvas)

    def eventFilter(self, source, event):
        if source == self.lbl_preview and self.pixmap_rotated:
            if event.type() == QEvent.Type.Wheel:
                delta = event.angleDelta().y()
                factor = 1.1 if delta > 0 else 0.9
                self.zoom *= factor
                self.zoom = max(0.1, min(self.zoom, 20.0))
                self.update_display()
                return True
                
            elif event.type() == QEvent.Type.MouseButtonPress:
                self.last_mouse_pos = event.pos()
                if event.button() == Qt.MouseButton.RightButton:
                    self.panning = True
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                elif event.button() == Qt.MouseButton.LeftButton:
                    self.dragging_selection = True
                    img_rect, scale = self.get_transforms()
                    if img_rect.width() > 0 and img_rect.height() > 0:
                        nx = (event.pos().x() - img_rect.x()) / img_rect.width()
                        ny = (event.pos().y() - img_rect.y()) / img_rect.height()
                        self.selection_start_norm = QPointF(nx, ny)
                        self.selection_norm = QRectF(nx, ny, 0, 0)
                        self.update_display()
                return True
            
            elif event.type() == QEvent.Type.MouseMove:
                if self.panning:
                    delta = event.pos() - self.last_mouse_pos
                    self.pan += QPointF(delta)
                    self.last_mouse_pos = event.pos()
                    self.update_display()
                elif self.dragging_selection:
                    img_rect, scale = self.get_transforms()
                    if img_rect.width() > 0:
                        curr_x = (event.pos().x() - img_rect.x()) / img_rect.width()
                        curr_y = (event.pos().y() - img_rect.y()) / img_rect.height()
                        x1 = min(self.selection_start_norm.x(), curr_x)
                        y1 = min(self.selection_start_norm.y(), curr_y)
                        w = abs(curr_x - self.selection_start_norm.x())
                        h = abs(curr_y - self.selection_start_norm.y())
                        self.selection_norm = QRectF(x1, y1, w, h)
                        self.update_display()
                return True
                
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self.panning = False
                self.dragging_selection = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
                return True
                
        return super().eventFilter(source, event)

    def get_texture(self):
        if not self.pixmap_rotated: return None
        w, h = self.pixmap_rotated.width(), self.pixmap_rotated.height()
        r = QRectF(self.selection_norm.x()*w, self.selection_norm.y()*h, 
                   self.selection_norm.width()*w, self.selection_norm.height()*h).toRect()
        if r.width() < 1 or r.height() < 1: return None
        return self.pixmap_rotated.copy(r)
    
    def resizeEvent(self, event): self.update_display(); super().resizeEvent(event)

class TextureLibraryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Texture Library")
        self.resize(600, 400)
        self.selected_texture = None
        
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(100, 100))
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListWidget.Movement.Static)
        self.list_widget.setSpacing(10)
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        btn_select = QPushButton("Select"); btn_select.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel"); btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel); btn_layout.addWidget(btn_select)
        layout.addLayout(btn_layout)
        
        self.load_library()
        
    def load_library(self):
        if not os.path.exists("textures"): return
        for fn in os.listdir("textures"):
            if fn.lower().endswith(".png"):
                path = os.path.join("textures", fn)
                pix = QPixmap(path)
                item = QListWidgetItem(fn[:-4])
                item.setIcon(QIcon(pix))
                item.setData(Qt.ItemDataRole.UserRole, path)
                self.list_widget.addItem(item)
                
    def get_selected_texture(self):
        item = self.list_widget.currentItem()
        if item:
            return QPixmap(item.data(Qt.ItemDataRole.UserRole))
        return None
