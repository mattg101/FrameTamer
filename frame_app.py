import sys
import math
import os
import ssl 
from urllib.request import Request, urlopen
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFileDialog, QColorDialog, QDialog,
                             QGroupBox, QGridLayout, QDoubleSpinBox, QComboBox, QSlider,
                             QRadioButton, QMessageBox, QCheckBox, QSizePolicy, 
                             QFormLayout, QButtonGroup, QStackedWidget, QScrollArea, QFrame)
# FIX: Added QEvent to imports
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QPointF, QSize, QPoint, QEvent
from PyQt6.QtGui import (QPixmap, QPainter, QColor, QPen, QPageSize, QBrush, QTransform,
                         QPdfWriter, QRegion, QCursor, QPolygonF, QFont, QPalette, QImageReader)

# --- CONSTANTS ---
DEFAULT_MAT_COLOR = QColor(255, 255, 255)
DEFAULT_FRAME_COLOR = QColor(60, 40, 30)
GRID_MAJOR_COLOR = QColor(255, 255, 0, 200)
GRID_MINOR_COLOR = QColor(0, 255, 255, 80)
RICK_ROLL_URL = "https://img.youtube.com/vi/dQw4w9WgXcQ/0.jpg"

RICK_ASCII = """
      ................
    .':   ~ ~ ~      :`.
  .' :  ~       ~    :  `.
 .'  :   ~     ~     :    `.
.'   :     ~ ~       :      `.
:    :   (o)   (o)   :       :
:    :       |       :       :
:    :      ===      :       :
:    :               :       :
 `.  :    _______    :     .'
  `.  :              :   .'
    `.. ____________ ..'
       NEVER GONNA
       GIVE YOU UP
"""

# --- HELPERS ---

def get_fit_metrics(view_w, view_h, content_w, content_h):
    """Calculates scale to fit content within a view while maintaining aspect ratio."""
    if content_w == 0 or content_h == 0: return 0
    return min(view_w / content_w, view_h / content_h) * 0.95 

class UnitUtils:
    @staticmethod
    def to_mm(val): return val * 25.4
    @staticmethod
    def from_mm(val): return val / 25.4
    @staticmethod
    def format_dual(val_in, mode):
        mm = val_in * 25.4
        return f"{val_in:.3f}\" ({mm:.1f}mm)" if mode == "in" else f"{mm:.1f}mm ({val_in:.3f}\")"

def draw_physical_grid(painter, rect, px_per_inch, unit_mode, w_px, h_px):
    if px_per_inch < 10: return 
    painter.save()
    painter.setFont(QFont("Arial", 8))
    step_val = 0.25 if unit_mode == "in" else (5.0/25.4)
    major_step_count = 4 if unit_mode == "in" else 2
    step_px = step_val * px_per_inch
    pen_minor = QPen(GRID_MINOR_COLOR, 1, Qt.PenStyle.DotLine)
    pen_major = QPen(GRID_MAJOR_COLOR, 1, Qt.PenStyle.SolidLine)
    text_pen = QPen(GRID_MAJOR_COLOR)

    def draw_lines(limit, is_vertical):
        pos = 0.0; count = 0
        while pos <= limit:
            is_major = (count % major_step_count == 0 and count != 0)
            painter.setPen(pen_major if is_major else pen_minor)
            if is_vertical:
                painter.drawLine(QPointF(rect.left() + pos, rect.top()), QPointF(rect.left() + pos, rect.bottom()))
                if is_major:
                    val = count * (0.25 if unit_mode == "in" else 5.0)
                    painter.setPen(text_pen); painter.drawText(QPointF(rect.left() + pos + 2, rect.bottom() - 2), f"{int(val)}")
            else:
                draw_y = rect.bottom() - pos
                painter.drawLine(QPointF(rect.left(), draw_y), QPointF(rect.right(), draw_y))
                if is_major:
                    val = count * (0.25 if unit_mode == "in" else 5.0)
                    painter.setPen(text_pen); painter.drawText(QPointF(rect.left() + 2, draw_y - 2), f"{int(val)}")
            pos += step_px; count += 1
    draw_lines(w_px, True); draw_lines(h_px, False)
    painter.restore()

# --- DIALOG: TEXTURE SAMPLER ---
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
        
        layout.addLayout(h_ctrl)

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

# --- WIDGETS ---

class SourceCropper(QLabel):
    cropChanged = pyqtSignal(QRectF) 
    H_NONE, H_TL, H_TR, H_BL, H_BR, H_MOVE = range(6)

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.setStyleSheet("border: 1px solid #555; background-color: #1e1e1e;") 
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.pixmap_original = None
        self.scaled_pixmap = None
        self.crop_norm = QRectF(0.0, 0.0, 1.0, 1.0)
        self.active_handle = self.H_NONE
        self.start_pos = QPointF()
        self.start_crop = None
        self.show_grid = False
        self.params = {} 

    def set_image(self, pixmap):
        self.pixmap_original = pixmap
        self.crop_norm = QRectF(0.05, 0.05, 0.9, 0.9)
        self.refresh_display()

    def update_params(self, params):
        self.params = params
        self.update()

    def set_grid_enabled(self, enabled): 
        self.show_grid = enabled
        self.update()

    def refresh_display(self):
        if self.pixmap_original:
            w, h = self.width() - 4, self.height() - 4
            if w <= 0 or h <= 0: return
            self.scaled_pixmap = self.pixmap_original.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.update()

    def get_image_offset(self):
        if not self.scaled_pixmap: return 0, 0
        return (self.width() - self.scaled_pixmap.width()) / 2, (self.height() - self.scaled_pixmap.height()) / 2

    def to_screen_rect(self, norm_rect):
        if not self.scaled_pixmap: return QRectF()
        x_off, y_off = self.get_image_offset()
        sw, sh = self.scaled_pixmap.width(), self.scaled_pixmap.height()
        return QRectF(x_off + norm_rect.x()*sw, y_off + norm_rect.y()*sh, norm_rect.width()*sw, norm_rect.height()*sh)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.scaled_pixmap:
            QPainter(self).drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Import Image")
            return

        x_off, y_off = self.get_image_offset()
        painter = QPainter(self)
        painter.drawPixmap(int(x_off), int(y_off), self.scaled_pixmap)

        img_rect = QRectF(x_off, y_off, self.scaled_pixmap.width(), self.scaled_pixmap.height())
        crop_rect = self.to_screen_rect(self.crop_norm)
        
        full_region = QRegion(self.rect())
        painter.setClipRegion(full_region.subtracted(QRegion(crop_rect.toRect())))
        painter.fillRect(self.rect(), QColor(0, 0, 0, 180))
        painter.setClipRect(self.rect())

        if self.show_grid and self.params:
            if self.params.get('img_w', 0) > 0:
                px_per_inch = crop_rect.width() / self.params['img_w']
                draw_physical_grid(painter, img_rect, px_per_inch, self.params['unit'], img_rect.width(), img_rect.height())
                
                info = (f"Full: {UnitUtils.format_dual(self.params['img_w'] / self.crop_norm.width(), self.params['unit'])}\n"
                        f"Crop: {UnitUtils.format_dual(self.params['img_w'], self.params['unit'])}")
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(10, 20, info)

        painter.setPen(QPen(QColor(0, 120, 215), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(crop_rect)

        painter.setBrush(QColor(255, 255, 255)); painter.setPen(Qt.GlobalColor.black)
        hs = 6
        for c in [crop_rect.topLeft(), crop_rect.topRight(), crop_rect.bottomLeft(), crop_rect.bottomRight()]:
            painter.drawRect(QRectF(c.x()-hs, c.y()-hs, 12, 12))

    def get_handle_at(self, pos):
        if not self.scaled_pixmap: return self.H_NONE
        s_rect = self.to_screen_rect(self.crop_norm)
        p = QPointF(pos)
        tol = 15
        if (p - s_rect.topLeft()).manhattanLength() < tol: return self.H_TL
        if (p - s_rect.topRight()).manhattanLength() < tol: return self.H_TR
        if (p - s_rect.bottomLeft()).manhattanLength() < tol: return self.H_BL
        if (p - s_rect.bottomRight()).manhattanLength() < tol: return self.H_BR
        if s_rect.contains(p): return self.H_MOVE
        return self.H_NONE

    def mouseMoveEvent(self, event):
        if not self.scaled_pixmap: return
        pos = QPointF(event.pos())
        
        if self.active_handle == self.H_NONE:
            h = self.get_handle_at(event.pos())
            cursors = {self.H_TL: Qt.CursorShape.SizeFDiagCursor, self.H_BR: Qt.CursorShape.SizeFDiagCursor,
                       self.H_TR: Qt.CursorShape.SizeBDiagCursor, self.H_BL: Qt.CursorShape.SizeBDiagCursor,
                       self.H_MOVE: Qt.CursorShape.SizeAllCursor}
            self.setCursor(cursors.get(h, Qt.CursorShape.ArrowCursor))
        else:
            sw, sh = self.scaled_pixmap.width(), self.scaled_pixmap.height()
            if sw == 0 or sh == 0: return
            dx = (pos.x() - self.start_pos.x()) / sw; dy = (pos.y() - self.start_pos.y()) / sh
            r = QRectF(self.start_crop)
            if self.active_handle == self.H_MOVE: r.adjust(dx, dy, dx, dy)
            elif self.active_handle == self.H_TL: r.setTopLeft(r.topLeft() + QPointF(dx, dy))
            elif self.active_handle == self.H_TR: r.setTopRight(r.topRight() + QPointF(dx, dy))
            elif self.active_handle == self.H_BL: r.setBottomLeft(r.bottomLeft() + QPointF(dx, dy))
            elif self.active_handle == self.H_BR: r.setBottomRight(r.bottomRight() + QPointF(dx, dy))
            self.crop_norm = QRectF(max(0, min(1-r.width(), r.x())), max(0, min(1-r.height(), r.y())),
                                    min(1, max(0.01, r.width())), min(1, max(0.01, r.height())))
            self.update(); self.cropChanged.emit(self.crop_norm)

    def mousePressEvent(self, event):
        if not self.scaled_pixmap: return
        self.active_handle = self.get_handle_at(event.pos()); self.start_pos = QPointF(event.pos()); self.start_crop = self.crop_norm
    def mouseReleaseEvent(self, event): self.active_handle = self.H_NONE; self.update()
    def resizeEvent(self, event): self.refresh_display(); super().resizeEvent(event)

class InteractiveMatEditor(QLabel):
    matDimensionsChanged = pyqtSignal(float, float, float, float)
    H_NONE, H_TOP, H_BOT, H_LEFT, H_RIGHT = range(5)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setStyleSheet("border: 1px solid #555; background-color: #1e1e1e;") 
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.pixmap_original = None 
        self.params = {} 
        self.active_handle = self.H_NONE; self.hover_handle = self.H_NONE
        self.last_pos = QPointF(); self.show_grid = False; self.dragging_enabled = True

    def set_image(self, pixmap): self.pixmap_original = pixmap; self.update()
    def update_params(self, params): self.params = params; self.dragging_enabled = not params.get('no_mat', False); self.update()
    def set_grid_enabled(self, enabled): self.show_grid = enabled; self.update()

    def get_view_metrics(self):
        if not self.params: return 0, 0, 0
        w, h = self.width() - 20, self.height() - 20
        scale = get_fit_metrics(w, h, self.params['outer_w'], self.params['outer_h'])
        return scale, self.width() / 2, self.height() / 2

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.params:
            QPainter(self).drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Load Art to Edit Mat")
            return

        scale, cx, cy = self.get_view_metrics()
        if scale == 0: return
        p = self.params; painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        total_w = (p['img_w'] + p['mat_left'] + p['mat_right']) * scale
        total_h = (p['img_h'] + p['mat_top'] + p['mat_bottom']) * scale
        start_x, start_y = cx - total_w / 2, cy - total_h / 2
        
        r_hole = QRectF(start_x + p['mat_left']*scale, start_y + p['mat_top']*scale, p['img_w']*scale, p['img_h']*scale)
        face_px = p['frame_face'] * scale

        painter.setBrush(p['col_frame']); painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(start_x - face_px, start_y - face_px, total_w + 2*face_px, total_h + 2*face_px))
        
        if not p.get('no_mat', False):
            painter.setBrush(p['col_mat']); painter.drawRect(QRectF(start_x, start_y, total_w, total_h))
        
        if self.pixmap_original:
            t_w, t_h = math.ceil(r_hole.width()), math.ceil(r_hole.height())
            scaled = self.pixmap_original.scaled(QSize(t_w, t_h), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            sx, sy = (scaled.width() - r_hole.width()) / 2, (scaled.height() - r_hole.height()) / 2
            painter.save(); painter.setClipRect(r_hole)
            painter.drawPixmap(int(r_hole.x() - sx), int(r_hole.y() - sy), scaled)
            painter.restore()
        else:
            painter.setBrush(QColor(50,50,50)); painter.drawRect(r_hole)

        if self.show_grid: draw_physical_grid(painter, r_hole, scale, p['unit'], r_hole.width(), r_hole.height())

        if self.dragging_enabled:
            pen = QPen(QColor(255, 255, 0, 255), 3) if self.hover_handle != self.H_NONE else QPen(QColor(0, 255, 255, 150), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            h_map = {self.H_TOP: (r_hole.topLeft(), r_hole.topRight()), self.H_BOT: (r_hole.bottomLeft(), r_hole.bottomRight()),
                     self.H_LEFT: (r_hole.topLeft(), r_hole.bottomLeft()), self.H_RIGHT: (r_hole.topRight(), r_hole.bottomRight())}
            if self.hover_handle != self.H_NONE:
                p1, p2 = h_map[self.hover_handle]; painter.drawLine(p1, p2)
            else:
                for k, (p1, p2) in h_map.items(): painter.drawLine(p1, p2)

    def mouseMoveEvent(self, event):
        if not self.params or not self.dragging_enabled: return
        pos = event.pos(); scale, cx, cy = self.get_view_metrics()
        p = self.params
        total_w = (p['img_w'] + p['mat_left'] + p['mat_right']) * scale
        total_h = (p['img_h'] + p['mat_top'] + p['mat_bottom']) * scale
        start_x, start_y = cx - total_w / 2, cy - total_h / 2
        r_hole = QRectF(start_x + p['mat_left']*scale, start_y + p['mat_top']*scale, p['img_w']*scale, p['img_h']*scale)

        if self.active_handle == self.H_NONE:
            tol = 10; self.hover_handle = self.H_NONE
            if abs(pos.y() - r_hole.top()) < tol and r_hole.left() < pos.x() < r_hole.right(): self.hover_handle = self.H_TOP
            elif abs(pos.y() - r_hole.bottom()) < tol and r_hole.left() < pos.x() < r_hole.right(): self.hover_handle = self.H_BOT
            elif abs(pos.x() - r_hole.left()) < tol and r_hole.top() < pos.y() < r_hole.bottom(): self.hover_handle = self.H_LEFT
            elif abs(pos.x() - r_hole.right()) < tol and r_hole.top() < pos.y() < r_hole.bottom(): self.hover_handle = self.H_RIGHT
            cursors = {self.H_TOP: Qt.CursorShape.SizeVerCursor, self.H_BOT: Qt.CursorShape.SizeVerCursor,
                       self.H_LEFT: Qt.CursorShape.SizeHorCursor, self.H_RIGHT: Qt.CursorShape.SizeHorCursor}
            self.setCursor(cursors.get(self.hover_handle, Qt.CursorShape.ArrowCursor))
            self.update()
        else:
            dy = (pos.y() - self.last_pos.y()) / scale; dx = (pos.x() - self.last_pos.x()) / scale
            vals = [p['mat_top'], p['mat_bottom'], p['mat_left'], p['mat_right']]
            if self.active_handle == self.H_TOP: vals[0] += dy
            elif self.active_handle == self.H_BOT: vals[1] -= dy
            elif self.active_handle == self.H_LEFT: vals[2] += dx
            elif self.active_handle == self.H_RIGHT: vals[3] -= dx
            vals = [max(0.5, v) for v in vals]
            if p.get('link_all', False):
                master = vals[self.active_handle - 1]; vals = [master] * 4
            self.matDimensionsChanged.emit(*vals); self.last_pos = pos

    def mousePressEvent(self, event):
        if self.hover_handle != self.H_NONE and self.dragging_enabled: self.active_handle = self.hover_handle; self.last_pos = event.pos()
    def mouseReleaseEvent(self, event): self.active_handle = self.H_NONE; self.update()

class FramePreviewLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("border: 1px solid #444;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.params = {}
        self.show_grid = False

    def update_params(self, params): self.params = params; self.refresh_render()
    def set_grid_enabled(self, enabled): self.show_grid = enabled; self.refresh_render()

    def refresh_render(self):
        if not self.params or not self.params.get('pixmap'):
            self.setText("No Image"); return

        p = self.params
        w, h = self.width() - 4, self.height() - 4
        scale = get_fit_metrics(w, h, p['outer_w'], p['outer_h'])
        if scale == 0: return

        render_w, render_h = int(p['outer_w'] * scale), int(p['outer_h'] * scale)
        face_px = int(p['frame_face'] * scale)

        final = QPixmap(render_w, render_h)
        final.fill(Qt.GlobalColor.transparent)
        painter = QPainter(final)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. DRAW FRAME (Color or Texture)
        outer_rect = QRectF(0, 0, render_w, render_h)
        inner_rect = QRectF(face_px, face_px, render_w - 2*face_px, render_h - 2*face_px)
        
        otl, otr, obl, obr = outer_rect.topLeft(), outer_rect.topRight(), outer_rect.bottomLeft(), outer_rect.bottomRight()
        itl, itr, ibl, ibr = inner_rect.topLeft(), inner_rect.topRight(), inner_rect.bottomLeft(), inner_rect.bottomRight()
        
        polys = [QPolygonF([otl, otr, itr, itl]), QPolygonF([obl, obr, ibr, ibl]), 
                 QPolygonF([otl, obl, ibl, itl]), QPolygonF([otr, obr, ibr, itr])] 

        frame_tex = p.get('frame_texture')
        painter.setPen(Qt.PenStyle.NoPen)
        
        if frame_tex:
            tex_h = frame_tex.height()
            if tex_h > 0 and face_px > 0:
                scale_y = face_px / tex_h
                brush_h = QBrush(frame_tex); brush_h.setTransform(QTransform().scale(1.0, scale_y))
                brush_v = QBrush(frame_tex); brush_v.setTransform(QTransform().rotate(90).scale(1.0, scale_y))
                
                painter.setBrush(brush_h); painter.drawPolygon(polys[0]); painter.drawPolygon(polys[1])
                painter.setBrush(brush_v); painter.drawPolygon(polys[2]); painter.drawPolygon(polys[3])
                
                painter.setPen(QPen(QColor(0,0,0,50), 1))
                painter.drawLine(otl, itl); painter.drawLine(otr, itr); painter.drawLine(obl, ibl); painter.drawLine(obr, ibr)
        else:
            painter.setBrush(p['col_frame']); painter.drawRect(outer_rect)

        # 2. Mat
        if not p.get('no_mat', False):
            painter.setBrush(p['col_mat']); painter.setPen(Qt.PenStyle.NoPen); painter.drawRect(inner_rect)

        # 3. Image
        # Draw Image relative to PAPER size (p['print_w/h']), centered on the aperture.
        aperture_cx = inner_rect.center().x() + (p['mat_left'] - p['mat_right']) * scale / 2
        aperture_cy = inner_rect.center().y() + (p['mat_top'] - p['mat_bottom']) * scale / 2
        
        paper_w_px = p['print_w'] * scale
        paper_h_px = p['print_h'] * scale
        
        paper_rect = QRectF(0, 0, paper_w_px, paper_h_px)
        paper_rect.moveCenter(QPointF(aperture_cx, aperture_cy))
        
        orig = p['pixmap']
        crop_px = QRectF(p['crop_rect'].x()*orig.width(), p['crop_rect'].y()*orig.height(), 
                         p['crop_rect'].width()*orig.width(), p['crop_rect'].height()*orig.height()).toRect()
        
        if crop_px.isValid():
            t_w, t_h = math.ceil(paper_rect.width()), math.ceil(paper_rect.height())
            scaled = orig.copy(crop_px).scaled(QSize(t_w, t_h), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            
            painter.save()
            img_clip_rect = QRectF(inner_rect.x() + p['mat_left']*scale, inner_rect.y() + p['mat_top']*scale, 
                                   p['img_w']*scale, p['img_h']*scale)
            painter.setClipRect(img_clip_rect)
            
            sx = (scaled.width() - paper_rect.width()) / 2
            sy = (scaled.height() - paper_rect.height()) / 2
            
            painter.drawPixmap(int(paper_rect.x() - sx), int(paper_rect.y() - sy), scaled)
            painter.restore()

        if self.show_grid:
            draw_physical_grid(painter, QRectF(0,0,render_w, render_h), scale, p['unit'], render_w, render_h)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(10, 20, f"Outer: {UnitUtils.format_dual(p['outer_w'], p['unit'])} x {UnitUtils.format_dual(p['outer_h'], p['unit'])}")

        painter.end()
        self.setPixmap(final)

    def resizeEvent(self, event): self.refresh_render(); super().resizeEvent(event)

# --- MAIN WINDOW ---
class FrameApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pro Frame & Mat Studio v14.0")
        self.resize(1280, 800)
        self.pixmap_full = None
        self.mat_color = DEFAULT_MAT_COLOR
        self.frame_color = DEFAULT_FRAME_COLOR
        self.frame_texture = None
        self.current_crop = QRectF(0,0,1,1)
        self.unit = "in"
        self.last_calc = {}
        self.updating_ui = False
        self.unit_inputs = [] 
        self.setup_ui()
        self.load_rick_roll()

    def setup_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QHBoxLayout(central); main_layout.setSpacing(20); main_layout.setContentsMargins(20, 20, 20, 20)

        panel_container = QWidget(); panel_layout = QVBoxLayout(panel_container); panel_container.setFixedWidth(320)
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setFixedWidth(280) 
        
        self.controls = QWidget()
        self.c_layout = QVBoxLayout(self.controls)
        self.setup_controls_content()
        
        scroll_area.setWidget(self.controls)
        panel_layout.addWidget(scroll_area)
        main_layout.addWidget(panel_container)
        self.setup_visualization_area(main_layout)
        self.update_ui_visibility()

    def setup_controls_content(self):
        gb_mode = QGroupBox("Workflow Mode"); l_mode = QVBoxLayout()
        self.rb_mode_frame = QRadioButton("Fixed Frame (Fit Art)"); self.rb_mode_frame.setChecked(True)
        self.rb_mode_frame.toggled.connect(self.update_ui_visibility)
        self.rb_mode_art = QRadioButton("Fixed Art (Build Frame)"); self.rb_mode_art.toggled.connect(self.update_ui_visibility)
        l_mode.addWidget(self.rb_mode_frame); l_mode.addWidget(self.rb_mode_art)
        gb_mode.setLayout(l_mode); self.c_layout.addWidget(gb_mode)

        h_top = QHBoxLayout()
        btn_import = QPushButton("Import Photo"); btn_import.clicked.connect(self.import_image)
        btn_import.setStyleSheet("background-color: #0078d7; font-weight: bold; padding: 8px; color: white;")
        h_top.addWidget(btn_import)
        
        v_units = QVBoxLayout()
        self.rb_imp = QRadioButton("Inches"); self.rb_met = QRadioButton("MM"); self.rb_imp.setChecked(True)
        self.bg_units = QButtonGroup(self); self.bg_units.addButton(self.rb_imp); self.bg_units.addButton(self.rb_met)
        self.rb_imp.toggled.connect(self.toggle_units); self.rb_met.toggled.connect(self.toggle_units)
        v_units.addWidget(self.rb_imp); v_units.addWidget(self.rb_met)
        h_top.addLayout(v_units); self.c_layout.addLayout(h_top)

        # Updated GroupBox title
        self.gb_frame = QGroupBox("Frame Aperture (Visible Opening)"); gl_f = QGridLayout()
        self.spin_iw = self._add_spin(gl_f, 0, "Aperture Width:", 16.0)
        self.spin_ih = self._add_spin(gl_f, 1, "Aperture Height:", 20.0)
        self.gb_frame.setLayout(gl_f); self.c_layout.addWidget(self.gb_frame)

        self.gb_art_specs = QGroupBox("Art Physical Dimensions"); gl_a = QGridLayout()
        self.rb_driver_w = QRadioButton("W"); self.rb_driver_w.setChecked(True)
        self.rb_driver_h = QRadioButton("H")
        bg_d = QButtonGroup(self); bg_d.addButton(self.rb_driver_w); bg_d.addButton(self.rb_driver_h)
        bg_d.buttonClicked.connect(self.recalc_aspect)
        self.spin_art_w = self._add_spin(gl_a, 0, "Art W:", 10.0, extra=self.rb_driver_w)
        self.spin_art_h = self._add_spin(gl_a, 1, "Art H:", 8.0, extra=self.rb_driver_h)
        self.spin_art_w.valueChanged.connect(self.on_art_w_changed)
        self.spin_art_h.valueChanged.connect(self.on_art_h_changed)
        self.gb_art_specs.setLayout(gl_a); self.c_layout.addWidget(self.gb_art_specs)

        self.gb_profile = QGroupBox("Frame Profile"); gl_p = QGridLayout()
        self.spin_face = self._add_spin(gl_p, 0, "Face Width:", 0.75)
        self.spin_rabbet = self._add_spin(gl_p, 1, "Rabbet Width:", 0.25)
        self.gb_profile.setLayout(gl_p); self.c_layout.addWidget(self.gb_profile)

        self.gb_mat_rules = QGroupBox("Mat Rules"); l_mr = QFormLayout()
        self.combo_fix = QComboBox(); self.combo_fix.addItems(["No Fixed Side", "Fix Top", "Fix Bottom", "Fix Left", "Fix Right"])
        self.combo_fix.currentIndexChanged.connect(self.recalc)
        self.spin_fix_val = self._create_spin(2.0); self.spin_min_gutter = self._create_spin(1.5)
        self.chk_link = QCheckBox("Match Opposite?"); self.chk_link.stateChanged.connect(self.recalc)
        self.combo_align = QComboBox(); self.combo_align.addItems(["Center", "Align Top/Left", "Align Bottom/Right"])
        self.combo_align.currentIndexChanged.connect(self.recalc)
        l_mr.addRow("Constraint:", self.combo_fix); l_mr.addRow("Fixed Size:", self.spin_fix_val)
        l_mr.addRow("", self.chk_link); l_mr.addRow("Min Gutter:", self.spin_min_gutter)
        l_mr.addRow("Alignment:", self.combo_align)
        self.gb_mat_rules.setLayout(l_mr); self.c_layout.addWidget(self.gb_mat_rules)

        self.gb_mat_dims = QGroupBox("Visible Mat Borders"); gl_md = QGridLayout()
        self.spin_mat_t = self._create_spin(2.0); self.spin_mat_b = self._create_spin(2.0)
        self.spin_mat_l = self._create_spin(2.0); self.spin_mat_r = self._create_spin(2.0)
        self.chk_link_all = QCheckBox("Link All Sides"); self.chk_link_all.setChecked(True)
        self.chk_no_mat = QCheckBox("No Mat (Direct to Frame)")
        
        for s in [self.spin_mat_t, self.spin_mat_b, self.spin_mat_l, self.spin_mat_r]: s.valueChanged.connect(self.sync_mats)
        self.chk_link_all.stateChanged.connect(self.sync_mats)
        self.chk_no_mat.stateChanged.connect(self.toggle_no_mat)
        
        gl_md.addWidget(self.chk_no_mat, 0, 0, 1, 2)
        gl_md.addWidget(QLabel("Top:"), 1, 0); gl_md.addWidget(self.spin_mat_t, 1, 1)
        gl_md.addWidget(QLabel("Bottom:"), 2, 0); gl_md.addWidget(self.spin_mat_b, 2, 1)
        gl_md.addWidget(QLabel("Left:"), 3, 0); gl_md.addWidget(self.spin_mat_l, 3, 1)
        gl_md.addWidget(QLabel("Right:"), 4, 0); gl_md.addWidget(self.spin_mat_r, 4, 1)
        gl_md.addWidget(self.chk_link_all, 5, 0, 1, 2)
        self.gb_mat_dims.setLayout(gl_md); self.c_layout.addWidget(self.gb_mat_dims)

        h_col = QHBoxLayout(); 
        b_mc = QPushButton("Mat Color"); b_mc.clicked.connect(self.pick_mat)
        b_fc = QPushButton("Frame Color"); b_fc.clicked.connect(self.pick_frame)
        self.b_ft = QPushButton("Load Frame Texture"); self.b_ft.clicked.connect(self.load_frame_texture)
        
        h_col.addWidget(b_mc); h_col.addWidget(b_fc)
        self.c_layout.addLayout(h_col); self.c_layout.addWidget(self.b_ft)

        gb_mnt = QGroupBox("Mounting"); l_mnt = QFormLayout()
        self.spin_print_border = self._create_spin(0.25); l_mnt.addRow("Print Border:", self.spin_print_border)
        gb_mnt.setLayout(l_mnt); self.c_layout.addWidget(gb_mnt)

        self.lbl_stats = QLabel("Load image..."); self.lbl_stats.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; margin-top: 10px;")
        self.lbl_stats.setWordWrap(True); self.c_layout.addWidget(self.lbl_stats)
        
        btn_pdf = QPushButton("Export Mat Blueprint (PDF)"); btn_pdf.setStyleSheet("background-color: #d83b01; font-weight: bold; margin-top: 20px; padding: 10px; color: white;")
        btn_pdf.clicked.connect(self.export_pdf); self.c_layout.addWidget(btn_pdf); self.c_layout.addStretch()

    def _create_spin(self, val):
        s = QDoubleSpinBox(); s.setRange(0, 99999); s.setValue(val); s.valueChanged.connect(self.recalc)
        self.unit_inputs.append(s); return s

    def _add_spin(self, layout, row, label, val, extra=None):
        s = self._create_spin(val)
        layout.addWidget(QLabel(label), row, 0); layout.addWidget(s, row, 1)
        if extra: layout.addWidget(extra, row, 2)
        return s

    def setup_visualization_area(self, parent_layout):
        src_wid = QWidget(); src_l = QVBoxLayout(src_wid); src_l.setContentsMargins(0, 20, 0, 0)
        h_head = QHBoxLayout(); h_head.addWidget(QLabel("<b>Source / Mat Editor</b>")); h_head.addStretch()
        self.chk_grid_src = QCheckBox("Show Grid"); self.chk_grid_src.stateChanged.connect(self.toggle_grids)
        h_head.addWidget(self.chk_grid_src); src_l.addLayout(h_head)
        
        self.stack_editors = QStackedWidget()
        self.editor_cropper = SourceCropper(); self.editor_cropper.cropChanged.connect(self.on_crop_change)
        self.stack_editors.addWidget(self.editor_cropper)
        self.editor_mat = InteractiveMatEditor(); self.editor_mat.matDimensionsChanged.connect(self.update_mat_spinboxes)
        self.stack_editors.addWidget(self.editor_mat)
        src_l.addWidget(self.stack_editors)

        res_wid = QWidget(); res_l = QVBoxLayout(res_wid); res_l.setContentsMargins(0, 20, 0, 0)
        h_p_head = QHBoxLayout(); h_p_head.addWidget(QLabel("<b>Final Preview</b>")); h_p_head.addStretch()
        self.chk_grid_prev = QCheckBox("Show Grid"); self.chk_grid_prev.stateChanged.connect(self.toggle_grids)
        h_p_head.addWidget(self.chk_grid_prev); res_l.addLayout(h_p_head)
        self.preview = FramePreviewLabel(); res_l.addWidget(self.preview)

        parent_layout.addWidget(src_wid, 1); parent_layout.addWidget(res_wid, 1)

    def load_rick_roll(self):
        fn = "rick_default.png"
        if os.path.exists(fn) and os.path.getsize(fn) == 0: os.remove(fn)

        if not os.path.exists(fn):
            print(f"Downloading: {RICK_ROLL_URL}")
            try:
                ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
                req = Request(RICK_ROLL_URL, headers={'User-Agent': 'Mozilla/5.0'})
                with urlopen(req, context=ctx) as u, open(fn, 'wb') as f: f.write(u.read())
                print("Download success.")
            except Exception as e:
                print(f"Download Error: {e}")
                # FALLBACK: ASCII RICK
                pm = QPixmap(800, 600); pm.fill(QColor(20, 20, 20))
                p = QPainter(pm)
                font = QFont("Consolas", 14); font.setStyleHint(QFont.StyleHint.Monospace)
                p.setFont(font); p.setPen(QColor(0, 255, 0))
                p.drawText(QRectF(0,0,800,600), Qt.AlignmentFlag.AlignCenter, RICK_ASCII)
                p.end(); pm.save(fn)

        if os.path.exists(fn):
            self.pixmap_full = QPixmap(fn)
            self.editor_cropper.set_image(self.pixmap_full)
            self.editor_mat.set_image(self.pixmap_full)
            self.current_crop = QRectF(0,0,1,1)
            self.recalc_aspect()

    # --- LOGIC ---
    def update_ui_visibility(self):
        fixed = self.rb_mode_frame.isChecked()
        self.gb_frame.setVisible(fixed); self.gb_mat_rules.setVisible(fixed)
        self.gb_art_specs.setVisible(not fixed); self.gb_mat_dims.setVisible(not fixed)
        self.stack_editors.setCurrentWidget(self.editor_cropper if fixed else self.editor_mat)
        self.recalc()

    def toggle_no_mat(self):
        is_no = self.chk_no_mat.isChecked()
        for s in [self.spin_mat_t, self.spin_mat_b, self.spin_mat_l, self.spin_mat_r, self.chk_link_all]: s.setEnabled(not is_no)
        self.updating_ui = True
        val = 0.0 if is_no else 0.5 * (25.4 if self.unit == "mm" else 1.0)
        for s in [self.spin_mat_t, self.spin_mat_b, self.spin_mat_l, self.spin_mat_r]: s.setValue(val)
        self.updating_ui = False
        self.recalc()

    def on_art_w_changed(self):
        if not self.updating_ui: 
            if self.spin_art_w.hasFocus(): self.rb_driver_w.setChecked(True)
            self.recalc_aspect()
    def on_art_h_changed(self):
        if not self.updating_ui:
            if self.spin_art_h.hasFocus(): self.rb_driver_h.setChecked(True)
            self.recalc_aspect()

    def recalc_aspect(self):
        if not self.pixmap_full: self.recalc(); return
        aspect = self.pixmap_full.width() / self.pixmap_full.height()
        self.updating_ui = True
        if self.rb_driver_w.isChecked():
            if self.spin_art_w.value() > 0: self.spin_art_h.setValue(self.spin_art_w.value() / aspect)
        else:
            if self.spin_art_h.value() > 0: self.spin_art_w.setValue(self.spin_art_h.value() * aspect)
        self.updating_ui = False
        self.recalc()

    def sync_mats(self):
        if self.chk_link_all.isChecked() and not self.updating_ui:
            self.updating_ui = True
            val = self.spin_mat_t.value() if isinstance(self.sender(), QCheckBox) else self.sender().value()
            for s in [self.spin_mat_t, self.spin_mat_b, self.spin_mat_l, self.spin_mat_r]: s.setValue(val)
            self.updating_ui = False
        self.recalc()

    def update_mat_spinboxes(self, t, b, l, r):
        self.updating_ui = True
        self.spin_mat_t.setValue(t); self.spin_mat_b.setValue(b); self.spin_mat_l.setValue(l); self.spin_mat_r.setValue(r)
        self.updating_ui = False
        self.recalc()

    def import_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg)")
        if path: 
            self.pixmap_full = QPixmap(path)
            self.editor_cropper.set_image(self.pixmap_full); self.editor_mat.set_image(self.pixmap_full)
            self.current_crop = QRectF(0,0,1,1); self.recalc_aspect()

    def load_frame_texture(self):
        dlg = TextureSamplerDialog(self)
        if dlg.exec():
            tex = dlg.get_texture()
            if tex:
                self.frame_texture = tex
                self.b_ft.setText("Texture Loaded (Clear?)")
                self.recalc()

    def toggle_units(self):
        if not self.sender().isChecked(): return
        target = "mm" if self.rb_met.isChecked() else "in"
        if target == self.unit: return
        
        factor = 25.4 if target == "mm" else 1/25.4
        self.updating_ui = True
        for s in self.unit_inputs: s.setValue(s.value() * factor)
        self.unit = target; self.updating_ui = False; self.recalc()

    def toggle_grids(self):
        for e in [self.editor_cropper, self.editor_mat]: e.set_grid_enabled(self.chk_grid_src.isChecked())
        self.preview.set_grid_enabled(self.chk_grid_prev.isChecked())
        self.editor_cropper.update_params(self.last_calc) 

    def on_crop_change(self, rect): self.current_crop = rect; self.recalc()
    def pick_mat(self): 
        c = QColorDialog.getColor(self.mat_color); 
        if c.isValid(): self.mat_color = c; self.recalc()
    def pick_frame(self): 
        c = QColorDialog.getColor(self.frame_color); 
        if c.isValid(): 
            self.frame_color = c; self.frame_texture = None; self.b_ft.setText("Load Frame Texture"); self.recalc()

    def recalc(self):
        if self.updating_ui: return
        face, rabbet, p_border = self.spin_face.value(), self.spin_rabbet.value(), self.spin_print_border.value()
        tol = 3.0/25.4 if self.unit == "in" else 3.0
        to_in = 1.0 if self.unit == "in" else 1/25.4

        if self.rb_mode_frame.isChecked():
            # FRAME MODE: Inputs are now VISIBLE APERTURE SIZE
            vis_w, vis_h = self.spin_iw.value(), self.spin_ih.value()
            if vis_w <= 0 or vis_h <= 0: return
            
            # Mat Rules
            m_t = m_b = m_l = m_r = self.spin_min_gutter.value()
            fix_val = self.spin_fix_val.value(); idx = self.combo_fix.currentIndex()
            if idx == 1: m_t = fix_val
            elif idx == 2: m_b = fix_val
            elif idx == 3: m_l = fix_val
            elif idx == 4: m_r = fix_val
            
            if self.chk_link.isChecked():
                if idx == 1: m_b = m_t
                elif idx == 2: m_t = m_b
                elif idx == 3: m_r = m_l
                elif idx == 4: m_l = m_r

            # Fit Art
            avail_w, avail_h = vis_w - m_l - m_r, vis_h - m_t - m_b
            if avail_w <= 0 or avail_h <= 0: self.lbl_stats.setText("Mat too large!"); return

            final_w, final_h = avail_w, avail_h
            if self.pixmap_full:
                aspect = (self.current_crop.width() * self.pixmap_full.width()) / (self.current_crop.height() * self.pixmap_full.height())
                if (avail_w / avail_h) > aspect: final_w = avail_h * aspect
                else: final_h = avail_w / aspect

            # Align
            rem_w, rem_h = avail_w - final_w, avail_h - final_h
            align = self.combo_align.currentIndex()
            xl = rem_w/2 if align == 0 else (rem_w if align == 2 else 0)
            yt = rem_h/2 if align == 0 else (rem_h if align == 2 else 0)
            
            fmt, fmb, fml, fmr = m_t + yt, vis_h - (m_t+yt) - final_h, m_l + xl, vis_w - (m_l+xl) - final_w
            
            # Glass size calculation
            glass_w = vis_w + 2*rabbet
            glass_h = vis_h + 2*rabbet
            
            mat_cut_w, mat_cut_h = glass_w - tol, glass_h - tol
            ow, oh = glass_w + 2*(face-rabbet), glass_h + 2*(face-rabbet)
        else:
            # ART MODE
            final_w, final_h = self.spin_art_w.value() - 2*(rabbet if self.chk_no_mat.isChecked() else p_border), self.spin_art_h.value() - 2*(rabbet if self.chk_no_mat.isChecked() else p_border)
            if final_w <= 0 or final_h <= 0: self.lbl_stats.setText("Border/Overlap too large!"); return
            
            if self.chk_no_mat.isChecked(): fmt = fmb = fml = fmr = 0
            else: fmt, fmb, fml, fmr = self.spin_mat_t.value(), self.spin_mat_b.value(), self.spin_mat_l.value(), self.spin_mat_r.value()
            
            vis_w = final_w + fml + fmr
            vis_h = final_h + fmt + fmb
            
            # Glass size calculation
            glass_w = vis_w + 2*rabbet
            glass_h = vis_h + 2*rabbet
            
            mat_cut_w, mat_cut_h = glass_w - tol, glass_h - tol
            ow, oh = glass_w + 2*(face-rabbet), glass_h + 2*(face-rabbet)

        hidden = rabbet - (tol/2.0)
        
        self.last_calc = {
            'unit': self.unit, 'cut_w': mat_cut_w * to_in, 'cut_h': mat_cut_h * to_in,
            'mat_top': fmt * to_in, 'mat_bottom': fmb * to_in, 'mat_left': fml * to_in, 'mat_right': fmr * to_in,
            'phys_top': (fmt+hidden)*to_in, 'phys_bot': (fmb+hidden)*to_in, 'phys_left': (fml+hidden)*to_in, 'phys_right': (fmr+hidden)*to_in,
            'img_w': final_w * to_in, 'img_h': final_h * to_in,
            'print_w': (final_w + 2*p_border)*to_in, 'print_h': (final_h + 2*p_border)*to_in, 'p_border': p_border*to_in,
            'outer_w': ow * to_in, 'outer_h': oh * to_in, 'frame_face': face * to_in, 
            'pixmap': self.pixmap_full, 'crop_rect': self.current_crop, 'col_mat': self.mat_color, 'col_frame': self.frame_color,
            'frame_texture': self.frame_texture,
            'no_mat': self.chk_no_mat.isChecked() if self.rb_mode_art.isChecked() else False,
            'link_all': self.chk_link_all.isChecked()
        }
        
        for w in [self.preview, self.editor_cropper, self.editor_mat]: w.update_params(self.last_calc)
        
        u = self.unit
        self.lbl_stats.setText(
            f"<b>OUTER FRAME SIZE:</b><br>{UnitUtils.format_dual(ow * to_in, u)} x {UnitUtils.format_dual(oh * to_in, u)}<br><br>"
            f"<b>MAT CUT SIZE:</b><br>{UnitUtils.format_dual(self.last_calc['cut_w'], u)} x {UnitUtils.format_dual(self.last_calc['cut_h'], u)}<br><br>"
            f"<b>APERTURE:</b><br>{UnitUtils.format_dual(self.last_calc['img_w'], u)} x {UnitUtils.format_dual(self.last_calc['img_h'], u)}<br><br>"
            f"<b>PRINT SIZE:</b><br>{UnitUtils.format_dual(self.last_calc['print_w'], u)} x {UnitUtils.format_dual(self.last_calc['print_h'], u)}"
        )

    def draw_dimension(self, p, start, end, text, offset, is_vert):
        p.setPen(QPen(Qt.GlobalColor.black, 3)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.setFont(QFont(p.font().family(), 10))
        if is_vert:
            x_line = start.x() + offset
            p.drawLine(QPointF(start.x()-10, start.y()), QPointF(x_line+10, start.y())) 
            p.drawLine(QPointF(start.x()-10, end.y()), QPointF(x_line+10, end.y()))      
            p.drawLine(QPointF(x_line, start.y()), QPointF(x_line, end.y()))
            self.draw_arrow(p, QPointF(x_line, start.y()), "up"); self.draw_arrow(p, QPointF(x_line, end.y()), "down")
            p.save(); p.translate(x_line - 30 if offset < 0 else x_line + 30, (start.y() + end.y())/2); p.rotate(-90)
            p.drawText(QRectF(-1000, -150 if offset<0 else 20, 2000, 140), Qt.AlignmentFlag.AlignHCenter | (Qt.AlignmentFlag.AlignBottom if offset<0 else Qt.AlignmentFlag.AlignTop), text)
            p.restore()
        else:
            y_line = start.y() + offset
            p.drawLine(QPointF(start.x(), start.y()-10), QPointF(start.x(), y_line+10)) 
            p.drawLine(QPointF(end.x(), start.y()-10), QPointF(end.x(), y_line+10))      
            p.drawLine(QPointF(start.x(), y_line), QPointF(end.x(), y_line))
            self.draw_arrow(p, QPointF(start.x(), y_line), "left"); self.draw_arrow(p, QPointF(end.x(), y_line), "right")
            p.drawText(QRectF(start.x(), y_line - 150 if offset < 0 else y_line + 10, end.x()-start.x(), 140), Qt.AlignmentFlag.AlignHCenter | (Qt.AlignmentFlag.AlignBottom if offset < 0 else Qt.AlignmentFlag.AlignTop), text)

    def draw_arrow(self, p, tip, direction):
        s = 15; a = QPolygonF([tip])
        if direction == "left": a.append(tip+QPointF(s,-s/3)); a.append(tip+QPointF(s,s/3))
        elif direction == "right": a.append(tip+QPointF(-s,-s/3)); a.append(tip+QPointF(-s,s/3))
        elif direction == "up": a.append(tip+QPointF(-s/3,s)); a.append(tip+QPointF(s/3,s))
        elif direction == "down": a.append(tip+QPointF(-s/3,-s)); a.append(tip+QPointF(s/3,-s))
        p.setBrush(Qt.GlobalColor.black); p.drawPolygon(a)

    def draw_row(self, p, y, label, vis, phys):
        p.drawText(100, y, label); p.drawText(1000, y, f"Visible {vis}"); p.drawText(4000, y, "|"); p.drawText(4200, y, f"Physical {phys}")

    def export_pdf(self):
        if not self.last_calc: return
        fn, _ = QFileDialog.getSaveFileName(self, "Save PDF", "Mat_Blueprint.pdf", "PDF Files (*.pdf)")
        if not fn: return
        d = self.last_calc; u = d['unit']
        writer = QPdfWriter(fn); writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        painter = QPainter(); painter.begin(writer)
        
        font = painter.font(); font.setPointSize(14); font.setBold(True); painter.setFont(font)
        painter.drawText(100, 150, f"MAT BLUEPRINT")
        font.setPointSize(10); font.setBold(False); painter.setFont(font)
        
        y = 300; h = 160
        for line in [f"CUT SIZE: {UnitUtils.format_dual(d['cut_w'], u)} x {UnitUtils.format_dual(d['cut_h'], u)}",
                     f"APERTURE: {UnitUtils.format_dual(d['img_w'], u)} x {UnitUtils.format_dual(d['img_h'], u)}",
                     f"PRINT SIZE: {UnitUtils.format_dual(d['print_w'], u)} x {UnitUtils.format_dual(d['print_h'], u)}"]:
            painter.drawText(100, int(y), line); y += h
        
        y += h*0.5; painter.drawText(100, int(y), "BORDERS:"); y += h
        for label, k_vis, k_phys in [("TOP:", 'mat_top', 'phys_top'), ("BOTTOM:", 'mat_bottom', 'phys_bot'),
                                     ("LEFT:", 'mat_left', 'phys_left'), ("RIGHT:", 'mat_right', 'phys_right')]:
            self.draw_row(painter, int(y), label, UnitUtils.format_dual(d[k_vis], u), UnitUtils.format_dual(d[k_phys], u))
            y += h

        avail_w, avail_h = writer.width(), writer.height() - y - 500
        scale = min(avail_w * 0.8 / d['cut_w'], avail_h * 0.8 / d['cut_h'])
        dw, dh = d['cut_w']*scale, d['cut_h']*scale
        ox, oy = (avail_w - dw)/2, y + (avail_h - dh)/2
        ax, ay = ox + d['phys_left']*scale, oy + d['phys_top']*scale
        aw, ah = d['img_w']*scale, d['img_h']*scale
        
        painter.setPen(QPen(Qt.GlobalColor.black, 5)); painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawRect(QRectF(ox, oy, dw, dh))
        painter.setBrush(QColor(230, 230, 230)); painter.drawRect(QRectF(ax, ay, aw, ah))
        
        self.draw_dimension(painter, QPointF(ax, ay), QPointF(ax+aw, ay), f"Top: {UnitUtils.format_dual(d['phys_top'], u)}", -200, False)
        self.draw_dimension(painter, QPointF(ax, ay+ah), QPointF(ax+aw, ay+ah), f"Bottom: {UnitUtils.format_dual(d['phys_bot'], u)}", 200, False)
        self.draw_dimension(painter, QPointF(ax, ay), QPointF(ax, ay+ah), f"Left: {UnitUtils.format_dual(d['phys_left'], u)}", -200, True)
        self.draw_dimension(painter, QPointF(ax+aw, ay), QPointF(ax+aw, ay+ah), f"Right: {UnitUtils.format_dual(d['phys_right'], u)}", 200, True)
        
        painter.end()
        QMessageBox.information(self, "Export", f"Blueprint saved to {fn}")

if __name__ == "__main__":
    QImageReader.setAllocationLimit(0)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)
    window = FrameApp()
    window.showMaximized() 
    sys.exit(app.exec())