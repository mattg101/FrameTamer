import math
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPen, QFont, QColor
from .constants import GRID_MAJOR_COLOR, GRID_MINOR_COLOR
from .colors import COLORS
import colorsys

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
    
    @staticmethod
    def format_pdf(val_in, mode):
        """Format for PDF: fractions (1/16) with LCD for inches, 0.5mm rounding for mm."""
        # Round mm to nearest 0.5
        mm_val = val_in * 25.4
        mm_rounded = round(mm_val * 2) / 2  # Round to 0.5
        mm_str = f"{mm_rounded:.1f}mm" if mm_rounded != int(mm_rounded) else f"{int(mm_rounded)}mm"
        
        # Round inches to nearest 1/16 and convert to fraction
        sixteenths = round(val_in * 16)
        whole = sixteenths // 16
        frac = sixteenths % 16
        
        # Reduce fraction to lowest common denominator
        def gcd(a, b):
            while b: a, b = b, a % b
            return a
        
        if frac == 0:
            in_str = f'{whole}"'
        else:
            g = gcd(frac, 16)
            num = frac // g
            den = 16 // g
            if whole == 0:
                in_str = f'{num}/{den}"'
            else:
                in_str = f'{whole}-{num}/{den}"'
        
        return f"{in_str} ({mm_str})" if mode == "in" else f"{mm_str} ({in_str})"

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
    @staticmethod
    def get_closest_name(qcolor):
        r1, g1, b1 = qcolor.red(), qcolor.green(), qcolor.blue()
        best_match = "Custom"
        min_dist = float('inf')
        
        # Simple weighted Euclidean distance (better than raw RGB for human perception)
        # Weights: R: 0.3, G: 0.59, B: 0.11 (standard luminance weights, but for distance we use:
        # Red: 2, Green: 4, Blue: 3 - a common fast approximation)
        for name, (r2, g2, b2) in COLORS.items():
            rmean = (r1 + r2) / 2
            r = r1 - r2
            g = g1 - g2
            b = b1 - b2
            dist = math.sqrt((((512+rmean)*r*r)/256) + 4*g*g + (((767-rmean)*b*b)/256))
            
            if dist < min_dist:
                min_dist = dist
                best_match = name
        
        # Higher threshold for descriptive names (80)
        if min_dist < 80:
            return best_match
            
        # Descriptive Fallback for true outliers
        h, l, s = colorsys.rgb_to_hls(r1/255.0, g1/255.0, b1/255.0)
        
        # Hue Name
        hue_map = [
            (0.05, "Red"), (0.15, "Orange"), (0.20, "Yellow"), 
            (0.45, "Green"), (0.55, "Cyan"), (0.75, "Blue"), 
            (0.85, "Purple"), (0.95, "Magenta"), (1.0, "Red")
        ]
        hue_name = "Red"
        for thresh, name in hue_map:
            if h <= thresh:
                hue_name = name
                break
        
        # Qualifiers
        lum = ""
        if l < 0.15: lum = "Deep "
        elif l < 0.35: lum = "Dark "
        elif l > 0.85: lum = "Pale "
        elif l > 0.65: lum = "Light "
        
        sat = ""
        if s < 0.15: 
            if l < 0.2: return "Black"
            if l > 0.8: return "White"
            return f"{lum}Gray-ish".strip()
        
        if s < 0.4: sat = "Muted "
        elif s > 0.85: sat = "Vibrant "
        
        return f"{sat}{lum}{hue_name}".strip()

    @staticmethod
    def get_average_color(qpixmap):
        """Calculates average color of a QPixmap/QImage."""
        if not qpixmap or qpixmap.isNull():
            return QColor(255, 255, 255)
        img = qpixmap.toImage()
        img = img.scaled(100, 100) # scale down for speed
        r, g, b, count = 0, 0, 0, 0
        for x in range(img.width()):
            for y in range(img.height()):
                c = QColor(img.pixel(x, y))
                r += c.red()
                g += c.green()
                b += c.blue()
                count += 1
        if count == 0: return QColor(255, 255, 255)
        return QColor(r // count, g // count, b // count)
