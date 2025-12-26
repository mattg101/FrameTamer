import math
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPen, QFont, QColor
from .constants import GRID_MAJOR_COLOR, GRID_MINOR_COLOR

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
