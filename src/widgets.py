import math
from PyQt6.QtWidgets import QLabel, QSizePolicy, QWidget, QVBoxLayout, QToolButton, QFrame, QGridLayout
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QPointF, QSize, QPropertyAnimation, QParallelAnimationGroup, QAbstractAnimation
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QRegion, QPolygonF, QBrush, QTransform

from .utils import get_fit_metrics, UnitUtils, draw_physical_grid

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
        if not crop_rect.isEmpty():
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
        scale = get_fit_metrics(self.width()-20, self.height()-20, self.params['outer_w'], self.params['outer_h'])
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

        if not p.get('no_mat', False):
            painter.setBrush(p['col_mat']); painter.setPen(Qt.PenStyle.NoPen); painter.drawRect(inner_rect)

        # Image centered on visible aperture
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

class CollapsibleBox(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)

        self.toggle_button = QToolButton(text=title, checkable=True, checked=True)
        self.toggle_button.setStyleSheet("QToolButton { border: none; font-weight: bold; background-color: #333; padding: 5px; }")
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
        self.toggle_button.pressed.connect(self.on_pressed)

        self.content_area = QWidget()
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        
        self.content_area = QWidget()
        # Initial State: Visible

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.toggle_button)
        self.main_layout.addWidget(self.content_area)

        self.on_pressed() # Initialize state

    def on_pressed(self):
        checked = not self.toggle_button.isChecked()
        # No animation, just toggle visibility
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.content_area.setVisible(checked)
        # Force layout update to prevent artifacts
        if self.parentWidget(): self.parentWidget().adjustSize()

    def set_content_layout(self, layout):
        old_layout = self.content_area.layout()
        if old_layout:
            import sip
            sip.delete(old_layout)
        self.content_area.setLayout(layout)

class MetricCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        # High visibility style
        self.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px;
                margin-top: 10px;
            }
            QLabel { color: #ddd; font-size: 11px; }
            QLabel.title { font-size: 14px; font-weight: bold; color: #aaa; }
            QLabel.primary { font-size: 24px; font-weight: bold; color: #4facfe; }
            QLabel.label { color: #888; font-weight: bold; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setProperty("class", "title")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_title)
        
        self.lbl_primary = QLabel("-- x --")
        self.lbl_primary.setWordWrap(True)
        self.lbl_primary.setProperty("class", "primary")
        self.lbl_primary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_primary)
        
        # Details Grid
        self.grid_details = QGridLayout()
        self.grid_details.setSpacing(4)
        
        # Row 1: Cut Size | Aperture
        self.grid_details.addWidget(QLabel("Cut Size:"), 0, 0, Qt.AlignmentFlag.AlignRight)
        self.lbl_cut = QLabel("--"); self.grid_details.addWidget(self.lbl_cut, 0, 1)
        
        self.grid_details.addWidget(QLabel("Aperture:"), 0, 2, Qt.AlignmentFlag.AlignRight)
        self.lbl_aperture = QLabel("--"); self.grid_details.addWidget(self.lbl_aperture, 0, 3)
        
        # Row 2: Print Size
        self.grid_details.addWidget(QLabel("Print Size:"), 1, 0, Qt.AlignmentFlag.AlignRight)
        self.lbl_print = QLabel("--"); self.grid_details.addWidget(self.lbl_print, 1, 1, 1, 3)
        
        # Row 3: Mat Borders
        self.grid_details.addWidget(QLabel("Mat T/B:"), 2, 0, Qt.AlignmentFlag.AlignRight)
        self.lbl_mat_tb = QLabel("--"); self.grid_details.addWidget(self.lbl_mat_tb, 2, 1)
        
        self.grid_details.addWidget(QLabel("Mat L/R:"), 2, 2, Qt.AlignmentFlag.AlignRight)
        self.lbl_mat_lr = QLabel("--"); self.grid_details.addWidget(self.lbl_mat_lr, 2, 3)
        
        layout.addLayout(self.grid_details)

    def update_metrics(self, data):
        # data = {outer_w, outer_h, cut_w, cut_h, img_w, img_h, print_w, print_h, mat_t, mat_b, mat_l, mat_r, unit, no_mat}
        u = data.get('unit', 'in')
        
        ow, oh = data.get('outer_w', 0), data.get('outer_h', 0)
        self.lbl_primary.setText(f"{UnitUtils.format_dual(ow, u)} x {UnitUtils.format_dual(oh, u)}")
        
        cw, ch = data.get('cut_w', 0), data.get('cut_h', 0)
        self.lbl_cut.setText(f"{UnitUtils.format_dual(cw, u)} x {UnitUtils.format_dual(ch, u)}")
        
        iw, ih = data.get('img_w', 0), data.get('img_h', 0)
        self.lbl_aperture.setText(f"{UnitUtils.format_dual(iw, u)} x {UnitUtils.format_dual(ih, u)}")
        
        pw, ph = data.get('print_w', 0), data.get('print_h', 0)
        self.lbl_print.setText(f"{UnitUtils.format_dual(pw, u)} x {UnitUtils.format_dual(ph, u)}")
        
        if data.get('no_mat', False):
            self.lbl_mat_tb.setText("N/A")
            self.lbl_mat_lr.setText("N/A")
        else:
            # Convert mat dimensions to inch for display normalization if needed, 
            # but usually they are passed as raw floats.
            # Assuming data passed in is already in inches, except for the unit flag.
            
            mt, mb = data.get('mat_t', 0), data.get('mat_b', 0)
            ml, mr = data.get('mat_l', 0), data.get('mat_r', 0)
            
            self.lbl_mat_tb.setText(f"{UnitUtils.format_dual(mt, u)} / {UnitUtils.format_dual(mb, u)}")
            self.lbl_mat_lr.setText(f"{UnitUtils.format_dual(ml, u)} / {UnitUtils.format_dual(mr, u)}")
