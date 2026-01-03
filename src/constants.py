import os
from PyQt6.QtGui import QColor

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MAT_COLOR = QColor("#FBFBF9")
DEFAULT_FRAME_COLOR = QColor(60, 40, 30)
DEFAULT_TEXTURE_PATH = os.path.join(BASE_DIR, "textures", "walnut.png")
QUICK_MAT_COLORS = ["#FBFBF9", "#F5F5F8", "#FFFFF0", "#B2BEB1", "#2C2C2C"]
QUICK_FRAME_COLORS = ["#7F6350", "#5D432C", "#694B37", "#BC9E82", "#F5F5DC", "#1A1A1A"]
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
