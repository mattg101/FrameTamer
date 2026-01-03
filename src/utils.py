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

class ColorUtils:
    COMMON_COLORS = {
        "Cotton White": (251, 251, 249),
        "Bright White": (255, 255, 255),
        "Off-White": (245, 245, 240),
        "Cream": (255, 253, 208),
        "Grey": (128, 128, 128),
        "Black": (0, 0, 0),
        "Navy": (0, 0, 128),
        "Royal Blue": (65, 105, 225),
        "Sky Blue": (135, 206, 235),
        "Forest Green": (34, 139, 34),
        "Sage Green": (156, 175, 136),
        "Lime Green": (85, 255, 0),
        "Deep Red": (139, 0, 0),
        "Burgundy": (128, 0, 32),
        "Tan": (210, 180, 140),
        "Chocolate": (105, 75, 55),
        "Gold": (212, 175, 55),
        "Silver": (192, 192, 192),
        "Orange": (255, 165, 0),
        "Purple": (128, 0, 128),
        "Teal": (0, 128, 128),
        "Hot Pink": (255, 105, 180),
    }

    @staticmethod
    def get_closest_name(qcolor):
        r1, g1, b1 = qcolor.red(), qcolor.green(), qcolor.blue()
        best_match = "Custom"
        min_dist = float('inf')
        
        for name, (r2, g2, b2) in ColorUtils.COMMON_COLORS.items():
            dist = math.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)
            if dist < min_dist:
                min_dist = dist
                best_match = name
        
        # Threshold for a "good" match
        if min_dist < 60:
            if min_dist < 5: return best_match
            return f"{best_match} (~{qcolor.name().upper()})"
        return f"Custom ({qcolor.name().upper()})"
