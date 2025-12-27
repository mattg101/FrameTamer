from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFileDialog, QSlider, QSizePolicy,
                             QInputDialog, QListWidget, QListWidgetItem, QAbstractItemView)
from PyQt6.QtCore import Qt, QRectF, QPointF, QEvent, QSize, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QTransform, QIcon, QImage
import os
import threading
import requests
from .google_photos import GooglePhotosManager

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
        self.panning_selection = False
        self.last_mouse_pos = QPointF()
        self.selection_start_norm = QPointF()
        self.drag_mode = None # None, 'top_left', 'top_right', 'bottom_left', 'bottom_right', 'new'
        
        # Grid State
        self.grid_visible = False
        self.grid_timer = QTimer()
        self.grid_timer.setSingleShot(True)
        self.grid_timer.timeout.connect(self.hide_grid)

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
        
        # Load default image if available
        self.load_default_texture()
        self.fully_initialized = True

    def load_default_texture(self):
        # Look for texture_default.jpg in the app root
        # Since we are in src/dialogs.py, we go up one level
        default_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "texture_default.jpg")
        if os.path.exists(default_path):
            self.pixmap_orig = QPixmap(default_path)
            self.slider_rot.setValue(0)
            self.reset_view()
            self.on_rotation_changed()
            print(f"Loaded default texture: {default_path}")

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
    
    def hide_grid(self):
        self.grid_visible = False
        self.update_display()

    def on_rotation_changed(self):
        if not self.pixmap_orig: return
        deg = self.slider_rot.value() / 10.0
        t = QTransform().rotate(deg)
        self.pixmap_rotated = self.pixmap_orig.transformed(t, Qt.TransformationMode.SmoothTransformation)
        
        # Show grid for 500ms
        if getattr(self, 'fully_initialized', False):
            self.grid_visible = True
            self.grid_timer.start(500)
        
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
        
        # Draw Grid Overlay (Helpful for straightening)
        # 100px fixed-spacing "Window-Frame" grid
        if self.grid_visible:
            # High-visibility White, 100/255 opacity
            grid_color = QColor(255, 255, 255, 100)
            
            # Secondary Lines (Dashed)
            p.setPen(QPen(grid_color, 1, Qt.PenStyle.DashLine))
            spacing = 100
            
            # Draw from center outwards to ensure symmetry
            cx, cy = w / 2, h / 2
            
            # Vertical lines
            x = cx + spacing
            while x < w:
                p.drawLine(QPointF(x, 0), QPointF(x, h))
                x += spacing
            x = cx - spacing
            while x > 0:
                p.drawLine(QPointF(x, 0), QPointF(x, h))
                x -= spacing
                
            # Horizontal lines
            y = cy + spacing
            while y < h:
                p.drawLine(QPointF(0, y), QPointF(w, y))
                y += spacing
            y = cy - spacing
            while y > 0:
                p.drawLine(QPointF(0, y), QPointF(w, y))
                y -= spacing
                
            # Center Crosshair (Solid)
            p.setPen(QPen(grid_color, 1, Qt.PenStyle.SolidLine))
            p.drawLine(QPointF(cx, 0), QPointF(cx, h))
            p.drawLine(QPointF(0, cy), QPointF(w, cy))
        
        sx = img_rect.x() + self.selection_norm.x() * img_rect.width()
        sy = img_rect.y() + self.selection_norm.y() * img_rect.height()
        sw = self.selection_norm.width() * img_rect.width()
        sh = self.selection_norm.height() * img_rect.height()
        
        sel_screen = QRectF(sx, sy, sw, sh)
        
        # Color based on Orientation (Width vs Height)
        sel_color = QColor(0, 255, 0) # Lime Green (Horizontal)
        if sel_screen.height() > sel_screen.width():
            sel_color = QColor(0, 191, 255) # Deep Sky Blue (Vertical)
            
        p.setPen(QPen(sel_color, 2))
        p.setBrush(QColor(sel_color.red(), sel_color.green(), sel_color.blue(), 40))
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
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        self.panning_selection = True
                    else:
                        self.panning = True
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                elif event.button() == Qt.MouseButton.LeftButton:
                    img_rect, scale = self.get_transforms()
                    if img_rect.width() > 0 and img_rect.height() > 0:
                        # Get handle positions in screen coords
                        sx = img_rect.x() + self.selection_norm.x() * img_rect.width()
                        sy = img_rect.y() + self.selection_norm.y() * img_rect.height()
                        sw = self.selection_norm.width() * img_rect.width()
                        sh = self.selection_norm.height() * img_rect.height()
                        
                        handles = {
                            'top_left': QPointF(sx, sy),
                            'top_right': QPointF(sx + sw, sy),
                            'bottom_left': QPointF(sx, sy + sh),
                            'bottom_right': QPointF(sx + sw, sy + sh)
                        }
                        
                        # Hit test
                        self.drag_mode = 'new'
                        for mode, pt in handles.items():
                            if (QPointF(event.pos()) - pt).manhattanLength() < 25:
                                self.drag_mode = mode
                                break
                        
                        if self.drag_mode == 'new':
                            nx = (event.pos().x() - img_rect.x()) / img_rect.width()
                            ny = (event.pos().y() - img_rect.y()) / img_rect.height()
                            self.selection_start_norm = QPointF(nx, ny)
                            self.selection_norm = QRectF(nx, ny, 0, 0)
                        
                        self.dragging_selection = True
                        self.update_display()
                return True
            
            elif event.type() == QEvent.Type.MouseMove:
                if self.panning or self.panning_selection:
                    delta = event.pos() - self.last_mouse_pos
                    img_rect, scale = self.get_transforms()
                    
                    if self.panning:
                        self.pan += QPointF(delta)
                    elif self.panning_selection and img_rect.width() > 0:
                        dx_norm = delta.x() / img_rect.width()
                        dy_norm = delta.y() / img_rect.height()
                        self.selection_norm.translate(dx_norm, dy_norm)
                        
                    self.last_mouse_pos = event.pos()
                    self.update_display()
                elif self.dragging_selection:
                    img_rect, scale = self.get_transforms()
                    if img_rect.width() > 0:
                        curr_x = (event.pos().x() - img_rect.x()) / img_rect.width()
                        curr_y = (event.pos().y() - img_rect.y()) / img_rect.height()
                        
                        if self.drag_mode == 'new':
                            x1 = self.selection_start_norm.x()
                            y1 = self.selection_start_norm.y()
                            w = abs(curr_x - x1)
                            h = abs(curr_y - y1)
                            
                            # Aspect Ratio Constraint
                            if w > h:
                                if w < 2 * h: w = 2 * h
                            elif h > w:
                                if h < 2 * w: h = 2 * w
                            
                            rx = x1 if curr_x > x1 else x1 - w
                            ry = y1 if curr_y > y1 else y1 - h
                            self.selection_norm = QRectF(rx, ry, w, h)
                        else:
                            # Corner Dragging - Pin the opposite corner
                            r = QRectF(self.selection_norm)
                            if self.drag_mode == 'top_left':
                                x1, y1, x2, y2 = curr_x, curr_y, r.right(), r.bottom()
                            elif self.drag_mode == 'top_right':
                                x1, y1, x2, y2 = r.left(), curr_y, curr_x, r.bottom()
                            elif self.drag_mode == 'bottom_left':
                                x1, y1, x2, y2 = curr_x, r.top(), r.right(), curr_y
                            elif self.drag_mode == 'bottom_right':
                                x1, y1, x2, y2 = r.left(), r.top(), curr_x, curr_y
                            
                            # Constrain Aspect Ratio (2:1 minimum)
                            rw, rh = abs(x2 - x1), abs(y2 - y1)
                            if rw > rh:
                                if rw < 2 * rh: rw = 2 * rh
                            elif rh > rw:
                                if rh < 2 * rw: rh = 2 * rw
                            
                            # Apply width/height adjustments based on which corner is moving
                            # To keep the opposite corner pinned, we recalculate x1/y1 or x2/y2
                            if self.drag_mode == 'top_left':
                                x1, y1 = x2 - (rw if x1 < x2 else -rw), y2 - (rh if y1 < y2 else -rh)
                            elif self.drag_mode == 'top_right':
                                x2, y1 = x1 + (rw if x2 > x1 else -rw), y2 - (rh if y1 < y2 else -rh)
                            elif self.drag_mode == 'bottom_left':
                                x1, y2 = x2 - (rw if x1 < x2 else -rw), y1 + (rh if y2 > y1 else -rh)
                            elif self.drag_mode == 'bottom_right':
                                x2, y2 = x1 + (rw if x2 > x1 else -rw), y1 + (rh if y2 > y1 else -rh)
                                
                            self.selection_norm = QRectF(x1, y1, x2-x1, y2-y1).normalized()
                            
                        self.update_display()
                return True
            
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self.panning = False
                self.panning_selection = False
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
        
        crop = self.pixmap_rotated.copy(r)
        
        # If vertical member (height > width), rotate 90 deg for tiling
        if crop.height() > crop.width():
            t = QTransform().rotate(90)
            crop = crop.transformed(t, Qt.TransformationMode.SmoothTransformation)
            
        return crop
    
    def resizeEvent(self, event): self.update_display(); super().resizeEvent(event)

class TextureLibraryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Texture Library")
        self.resize(800, 500)
        
        main_layout = QHBoxLayout(self)
        
        # Left: List
        left_wid = QWidget(); left_lay = QVBoxLayout(left_wid)
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(80, 80))
        self.list_widget.setSpacing(10)
        self.list_widget.itemSelectionChanged.connect(self.update_preview)
        left_lay.addWidget(QLabel("<b>Textures Found:</b>"))
        left_lay.addWidget(self.list_widget)
        
        # Right: Preview
        right_wid = QWidget(); right_lay = QVBoxLayout(right_wid); right_wid.setFixedWidth(250)
        self.lbl_zoom = QLabel("Select to preview")
        self.lbl_zoom.setFixedSize(230, 230)
        self.lbl_zoom.setStyleSheet("border: 1px solid #555; background: #202020;")
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_lay.addWidget(self.lbl_zoom)
        
        self.btn_del = QPushButton("Delete Texture")
        self.btn_del.setStyleSheet("background-color: #dc3545; color: white;")
        self.btn_del.clicked.connect(self.delete_texture)
        right_lay.addWidget(self.btn_del)
        right_lay.addStretch()
        
        btn_layout = QHBoxLayout()
        btn_select = QPushButton("Use Selected"); btn_select.clicked.connect(self.accept)
        btn_select.setStyleSheet("font-weight: bold; background: #0078d7; color: white;")
        btn_cancel = QPushButton("Close"); btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel); btn_layout.addWidget(btn_select)
        right_lay.addLayout(btn_layout)
        
        main_layout.addWidget(left_wid, 1)
        main_layout.addWidget(right_wid)
        
        self.load_library()
        
    def load_library(self):
        self.list_widget.clear()
        if not os.path.exists("textures"): return
        for fn in os.listdir("textures"):
            if fn.lower().endswith(".png"):
                path = os.path.join("textures", fn)
                pix = QPixmap(path)
                item = QListWidgetItem(fn[:-4])
                item.setIcon(QIcon(pix))
                item.setData(Qt.ItemDataRole.UserRole, path)
                self.list_widget.addItem(item)
                
    def update_preview(self):
        item = self.list_widget.currentItem()
        if item:
            pix = QPixmap(item.data(Qt.ItemDataRole.UserRole))
            self.lbl_zoom.setPixmap(pix.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.lbl_zoom.clear(); self.lbl_zoom.setText("Select to preview")

    def delete_texture(self):
        item = self.list_widget.currentItem()
        if not item: return
        path = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Delete", f"Delete '{item.text()}'?", 
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            os.remove(path)
            self.load_library()
            self.update_preview()

    def get_selected_texture(self):
        item = self.list_widget.currentItem()
        if item: return QPixmap(item.data(Qt.ItemDataRole.UserRole))
        return None

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QWidget

class PresetManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Frame Presets")
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Width", "Height", "Rabbet"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        
        btn_lay = QHBoxLayout()
        btn_del = QPushButton("Delete Selected"); btn_del.clicked.connect(self.delete_preset)
        btn_del.setStyleSheet("background-color: #dc3545; color: white;")
        btn_close = QPushButton("Close"); btn_close.clicked.connect(self.accept)
        btn_lay.addWidget(btn_del); btn_lay.addStretch(); btn_lay.addWidget(btn_close)
        layout.addLayout(btn_lay)
        
        self.load_presets()
        
    def load_presets(self):
        from PyQt6.QtCore import QSettings
        settings = QSettings("MattG", "FrameTamer")
        presets = settings.value("presets", {})
        self.table.setRowCount(0)
        for name, vals in presets.items():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(name))
            self.table.setItem(r, 1, QTableWidgetItem(str(vals.get('w'))))
            self.table.setItem(r, 2, QTableWidgetItem(str(vals.get('h'))))
            self.table.setItem(r, 3, QTableWidgetItem(str(vals.get('r'))))
            
    def delete_preset(self):
        row = self.table.currentRow()
        if row < 0: return
        name = self.table.item(row, 0).text()
        from PyQt6.QtCore import QSettings
        settings = QSettings("MattG", "FrameTamer")
        presets = settings.value("presets", {})
        if name in presets:
            del presets[name]
            settings.setValue("presets", presets)
            self.load_presets()

class PhotoLoader(QThread):
    finished = pyqtSignal(list, str) # list of (id, pixmap, base_url), next_page_token
    error = pyqtSignal(str)

    def __init__(self, manager, page_token=None):
        super().__init__()
        self.manager = manager
        self.page_token = page_token

    def run(self):
        try:
            data = self.manager.list_media_items(self.page_token)
            items = data.get('mediaItems', [])
            next_token = data.get('nextPageToken', "")
            
            results = []
            for item in items:
                # Fetch small thumbnail for the list
                thumb_data = self.manager.get_image_data(item['baseUrl'], width=150, height=150)
                img = QImage.fromData(thumb_data)
                pix = QPixmap.fromImage(img)
                results.append((item['id'], pix, item['baseUrl']))
            
            self.finished.emit(results, next_token)
        except Exception as e:
            self.error.emit(str(e))

class GooglePhotosDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Browse Google Photos")
        self.resize(900, 700)
        self.manager = GooglePhotosManager()
        self.selected_base_url = None
        self.next_page_token = None
        self.loading = False
        
        layout = QVBoxLayout(self)
        
        # Grid list
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(150, 150))
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setSpacing(10)
        self.list_widget.setWordWrap(True)
        layout.addWidget(self.list_widget)
        
        # Bottom controls
        self.btn_load_more = QPushButton("Load More")
        self.btn_load_more.clicked.connect(self.load_photos)
        self.btn_load_more.hide()
        
        btn_layout = QHBoxLayout()
        self.lbl_status = QLabel("Ready")
        btn_layout.addWidget(self.lbl_status)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_load_more)
        
        btn_select = QPushButton("Select Photo"); btn_select.clicked.connect(self.accept)
        btn_select.setStyleSheet("background: #0078d7; color: white; font-weight: bold; padding: 5px 15px;")
        btn_cancel = QPushButton("Cancel"); btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel); btn_layout.addWidget(btn_select)
        
        layout.addLayout(btn_layout)
        
        # Start initial load
        self.load_photos()

    def load_photos(self):
        if self.loading: return
        self.loading = True
        self.lbl_status.setText("Connecting...")
        self.btn_load_more.setEnabled(False)
        
        self.loader = PhotoLoader(self.manager, self.next_page_token)
        self.loader.finished.connect(self.on_photos_loaded)
        self.loader.error.connect(self.on_error)
        self.loader.start()

    def on_photos_loaded(self, results, next_token):
        self.loading = False
        self.next_page_token = next_token
        
        for pid, pix, base_url in results:
            item = QListWidgetItem()
            item.setIcon(QIcon(pix))
            item.setData(Qt.ItemDataRole.UserRole, base_url)
            self.list_widget.addItem(item)
            
        self.lbl_status.setText(f"Loaded {self.list_widget.count()} photos")
        self.btn_load_more.setEnabled(True)
        self.btn_load_more.setVisible(bool(next_token))

    def on_error(self, err_msg):
        self.loading = False
        self.lbl_status.setText(f"Error: {err_msg}")
        QMessageBox.critical(self, "Photos Error", f"Failed to load photos:\n{err_msg}")

    def get_selected_image(self):
        item = self.list_widget.currentItem()
        if item:
            base_url = item.data(Qt.ItemDataRole.UserRole)
            # Fetch higher res for the actual app
            try:
                data = self.manager.get_image_data(base_url, width=2048, height=2048)
                img = QImage.fromData(data)
                return QPixmap.fromImage(img)
            except Exception as e:
                QMessageBox.warning(self, "Download Error", f"Could not download full image: {e}")
        return None
