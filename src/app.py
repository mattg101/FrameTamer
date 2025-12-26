import os
import ssl
import math
from urllib.request import Request, urlopen

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFileDialog, QColorDialog,
                             QGroupBox, QGridLayout, QDoubleSpinBox, QComboBox, QCheckBox, 
                             QSizePolicy, QFormLayout, QButtonGroup, QStackedWidget, 
                             QScrollArea, QFrame, QMessageBox, QRadioButton, QInputDialog)
from PyQt6.QtCore import Qt, QRectF, QPointF, QSize, QSettings
from PyQt6.QtGui import (QPixmap, QPainter, QColor, QPen, QPdfWriter, 
                         QPolygonF, QFont, QImageReader, QPageSize)

from .constants import DEFAULT_MAT_COLOR, DEFAULT_FRAME_COLOR, RICK_ROLL_URL, RICK_ASCII
from .utils import UnitUtils
from .widgets import SourceCropper, InteractiveMatEditor, FramePreviewLabel
from .dialogs import TextureSamplerDialog, TextureLibraryDialog, PresetManagerDialog

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
        self.defaults_mode = False
        
        self.setup_ui()
        self.load_settings()
        self.load_rick_roll()

    def load_settings(self):
        settings = QSettings("MattG", "FrameTamer")
        self.updating_ui = True
        
        # Load numbers
        self.spin_iw.setValue(float(settings.value("aperture_w", 16.0)))
        self.spin_ih.setValue(float(settings.value("aperture_h", 20.0)))
        self.spin_face.setValue(float(settings.value("face_w", 0.75)))
        self.spin_rabbet.setValue(float(settings.value("rabbet_w", 0.25)))
        self.spin_print_border.setValue(float(settings.value("print_border", 0.25)))
        
        # Load colors
        mat_col = settings.value("mat_color")
        if mat_col: self.mat_color = QColor(mat_col)
        frame_col = settings.value("frame_color")
        if frame_col: self.frame_color = QColor(frame_col)
        
        # Load units
        unit = settings.value("unit", "in")
        if unit == "mm": self.rb_met.setChecked(True)
        else: self.rb_imp.setChecked(True)
        self.unit = unit
        
        # Load Mat Rules
        self.combo_fix.setCurrentIndex(int(settings.value("mat_fix_id", 0)))
        self.spin_fix_val.setValue(float(settings.value("mat_fixed_val", 2.0)))
        self.chk_link.setChecked(settings.value("mat_match_opp", "true") == "true")
        self.spin_min_gutter.setValue(float(settings.value("mat_gutter", 0.125)))
        self.combo_align.setCurrentIndex(int(settings.value("mat_align_id", 0)))
        
        self.updating_ui = False
        self.recalc()

    def closeEvent(self, event):
        settings = QSettings("MattG", "FrameTamer")
        settings.setValue("aperture_w", self.spin_iw.value())
        settings.setValue("aperture_h", self.spin_ih.value())
        settings.setValue("face_w", self.spin_face.value())
        settings.setValue("rabbet_w", self.spin_rabbet.value())
        settings.setValue("print_border", self.spin_print_border.value())
        settings.setValue("mat_color", self.mat_color.name())
        settings.setValue("frame_color", self.frame_color.name())
        settings.setValue("unit", self.unit)
        super().closeEvent(event)

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
        # Defaults Editor at Top
        self.btn_defaults_mode = QPushButton("Editor: Defaults Mode [OFF]")
        self.btn_defaults_mode.setCheckable(True)
        self.btn_defaults_mode.clicked.connect(self.toggle_defaults_mode)
        self.btn_defaults_mode.setStyleSheet("padding: 8px; font-weight: bold;")
        self.c_layout.addWidget(self.btn_defaults_mode)

        self.btn_save_defaults = QPushButton("Save Current as Defaults")
        self.btn_save_defaults.clicked.connect(self.save_as_defaults)
        self.btn_save_defaults.setStyleSheet("background-color: #ffc107; color: black; font-weight: bold; padding: 8px;")
        self.btn_save_defaults.hide()
        self.c_layout.addWidget(self.btn_save_defaults)
        
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); line.setFrameShadow(QFrame.Shadow.Sunken)
        self.c_layout.addWidget(line)

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
        v_units = QVBoxLayout()
        self.rb_imp = QRadioButton("Inches"); self.rb_met = QRadioButton("MM"); self.rb_imp.setChecked(True)
        self.bg_units = QButtonGroup(self); self.bg_units.addButton(self.rb_imp); self.bg_units.addButton(self.rb_met)
        self.rb_imp.toggled.connect(self.toggle_units); self.rb_met.toggled.connect(self.toggle_units)
        v_units.addWidget(self.rb_imp); v_units.addWidget(self.rb_met)
        h_top.addLayout(v_units); self.c_layout.addLayout(h_top)

        self.gb_frame = QGroupBox("Frame Aperture (Visible Opening)"); gl_f = QGridLayout()
        self.spin_iw = self._add_spin(gl_f, 0, "Aperture Width:", 16.0)
        self.spin_ih = self._add_spin(gl_f, 1, "Aperture Height:", 20.0)
        
        h_preset = QHBoxLayout()
        self.combo_presets = QComboBox(); self.combo_presets.addItem("Select Preset..."); self.combo_presets.currentIndexChanged.connect(self.on_preset_selected)
        btn_save_preset = QPushButton("Save"); btn_save_preset.setFixedWidth(50); btn_save_preset.clicked.connect(self.save_preset)
        btn_manage_presets = QPushButton("..."); btn_manage_presets.setFixedWidth(30); btn_manage_presets.clicked.connect(self.manage_presets)
        h_preset.addWidget(self.combo_presets); h_preset.addWidget(btn_save_preset); h_preset.addWidget(btn_manage_presets)
        gl_f.addLayout(h_preset, 2, 0, 1, 2)
        
        btn_swap = QPushButton("Swap W/H"); btn_swap.clicked.connect(self.swap_frame_dims)
        gl_f.addWidget(btn_swap, 3, 0, 1, 2)
        self.gb_frame.setLayout(gl_f); self.c_layout.addWidget(self.gb_frame)
        self.refresh_preset_list()

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
        
        h_col.addWidget(b_mc); h_col.addWidget(b_fc)
        self.c_layout.addLayout(h_col)
        
        h_tex = QHBoxLayout()
        self.btn_extract_tex = QPushButton("Extract Texture")
        self.btn_extract_tex.clicked.connect(self.load_frame_texture)
        self.btn_lib_tex = QPushButton("Library")
        self.btn_lib_tex.clicked.connect(self.select_from_library)
        h_tex.addWidget(self.btn_extract_tex); h_tex.addWidget(self.btn_lib_tex)
        self.c_layout.addLayout(h_tex)

        gb_mnt = QGroupBox("Mounting"); l_mnt = QFormLayout()
        self.spin_print_border = self._create_spin(0.25); l_mnt.addRow("Print Border:", self.spin_print_border)
        gb_mnt.setLayout(l_mnt); self.c_layout.addWidget(gb_mnt)

        self.lbl_stats = QLabel("Load image..."); self.lbl_stats.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; margin-top: 10px;")
        self.lbl_stats.setWordWrap(True); self.c_layout.addWidget(self.lbl_stats)
        
        btn_pdf = QPushButton("Export Mat Blueprint (PDF)"); btn_pdf.setStyleSheet("background-color: #d83b01; font-weight: bold; margin-top: 20px; padding: 10px; color: white;")
        btn_pdf.clicked.connect(self.export_pdf); self.c_layout.addWidget(btn_pdf)
        
        self.c_layout.addStretch()

    def _create_spin(self, val):
        s = QDoubleSpinBox(); s.setRange(0, 99999); s.setDecimals(3); s.setValue(val); s.valueChanged.connect(self.recalc)
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
        print(f"Loading/Downloading default image to: {fn}")
        
        # If it's zero size, it's definitely bad
        if os.path.exists(fn) and os.path.getsize(fn) == 0: 
            os.remove(fn)
            
        if not os.path.exists(fn):
            try:
                print("Attempting to download Rick Roll thumbnail...")
                ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
                req = Request(RICK_ROLL_URL, headers={'User-Agent': 'Mozilla/5.0'})
                with urlopen(req, context=ctx) as u, open(fn, 'wb') as f: 
                    f.write(u.read())
                print("Download successful.")
            except Exception as e:
                print(f"Download failed: {e}. Generating ASCII fallback...")
                pm = QPixmap(800, 600); pm.fill(QColor(20, 20, 20)); p = QPainter(pm)
                font = QFont("Consolas", 14); font.setStyleHint(QFont.StyleHint.Monospace)
                p.setFont(font); p.setPen(QColor(0, 255, 0))
                p.drawText(QRectF(0,0,800,600), Qt.AlignmentFlag.AlignCenter, RICK_ASCII)
                p.end()
                pm.save(fn)
                print("ASCII fallback generated and saved.")

        if os.path.exists(fn):
            pm = QPixmap(fn)
            if pm.isNull():
                print(f"Corrupted image found at {fn}. Deleting and using direct ASCII render.")
                os.remove(fn)
                # Render directly to self.pixmap_full instead of saving to file if download failed badly
                self.pixmap_full = QPixmap(800, 600); self.pixmap_full.fill(QColor(20, 20, 20))
                p = QPainter(self.pixmap_full)
                font = QFont("Consolas", 14); font.setStyleHint(QFont.StyleHint.Monospace)
                p.setFont(font); p.setPen(QColor(0, 255, 0))
                p.drawText(QRectF(0,0,800,600), Qt.AlignmentFlag.AlignCenter, RICK_ASCII)
                p.end()
            else:
                self.pixmap_full = pm

            self.editor_cropper.set_image(self.pixmap_full)
            self.editor_mat.set_image(self.pixmap_full)
            self.recalc_aspect()

    # --- LOGIC ---
    def update_ui_visibility(self):
        fixed = self.rb_mode_frame.isChecked()
        self.gb_frame.setVisible(fixed); self.gb_mat_rules.setVisible(fixed)
        self.gb_art_specs.setVisible(not fixed); self.gb_mat_dims.setVisible(not fixed)
        self.stack_editors.setCurrentWidget(self.editor_cropper if fixed else self.editor_mat)
        self.recalc()

    def toggle_defaults_mode(self):
        self.defaults_mode = self.btn_defaults_mode.isChecked()
        self.btn_defaults_mode.setText(f"Editor: Defaults Mode [{'ON' if self.defaults_mode else 'OFF'}]")
        self.btn_save_defaults.setVisible(self.defaults_mode)
        
        # Define fields that are "defaults"
        default_fields = [self.spin_iw, self.spin_ih, self.spin_face, self.spin_rabbet, self.spin_print_border,
                          self.combo_fix, self.spin_fix_val, self.chk_link, self.spin_min_gutter, self.combo_align]
        highlight = "border: 2px solid #ffc107; background: #3a3a20;" if self.defaults_mode else ""
        for f in default_fields: f.setStyleSheet(highlight)

    def save_as_defaults(self):
        settings = QSettings("MattG", "FrameTamer")
        settings.setValue("aperture_w", self.spin_iw.value())
        settings.setValue("aperture_h", self.spin_ih.value())
        settings.setValue("face_w", self.spin_face.value())
        settings.setValue("rabbet_w", self.spin_rabbet.value())
        settings.setValue("print_border", self.spin_print_border.value())
        settings.setValue("mat_color", self.mat_color.name())
        settings.setValue("frame_color", self.frame_color.name())
        settings.setValue("unit", self.unit)
        
        # Mat Rules
        settings.setValue("mat_fix_id", self.combo_fix.currentIndex())
        settings.setValue("mat_fixed_val", self.spin_fix_val.value())
        settings.setValue("mat_match_opp", self.chk_link.isChecked())
        settings.setValue("mat_gutter", self.spin_min_gutter.value())
        settings.setValue("mat_align_id", self.combo_align.currentIndex())
        
        QMessageBox.information(self, "Defaults Saved", "Current values set as application defaults.")

    def refresh_preset_list(self):
        self.updating_ui = True
        self.combo_presets.clear(); self.combo_presets.addItem("Select Preset...")
        settings = QSettings("MattG", "FrameTamer"); presets = settings.value("presets", {})
        for name in sorted(presets.keys()): self.combo_presets.addItem(name)
        self.updating_ui = False

    def on_preset_selected(self, index):
        if self.updating_ui or index <= 0: return
        name = self.combo_presets.currentText()
        settings = QSettings("MattG", "FrameTamer"); presets = settings.value("presets", {})
        if name in presets:
            v = presets[name]; self.updating_ui = True
            self.spin_iw.setValue(float(v.get('w', 16)))
            self.spin_ih.setValue(float(v.get('h', 20)))
            self.spin_rabbet.setValue(float(v.get('r', 0.25)))
            self.updating_ui = False; self.recalc()

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset Name:")
        if ok and name:
            settings = QSettings("MattG", "FrameTamer")
            presets = settings.value("presets", {})
            presets[name] = {'w': self.spin_iw.value(), 'h': self.spin_ih.value(), 'r': self.spin_rabbet.value()}
            settings.setValue("presets", presets); self.refresh_preset_list()

    def manage_presets(self):
        if PresetManagerDialog(self).exec(): self.refresh_preset_list()

    def toggle_no_mat(self):
        is_no = self.chk_no_mat.isChecked()
        for s in [self.spin_mat_t, self.spin_mat_b, self.spin_mat_l, self.spin_mat_r, self.chk_link_all]: s.setEnabled(not is_no)
        self.updating_ui = True
        val = 0.0 if is_no else 0.5 * (25.4 if self.unit == "mm" else 1.0)
        for s in [self.spin_mat_t, self.spin_mat_b, self.spin_mat_l, self.spin_mat_r]: s.setValue(val)
        self.updating_ui = False
        self.recalc()

    def swap_frame_dims(self):
        self.updating_ui = True
        w, h = self.spin_iw.value(), self.spin_ih.value()
        self.spin_iw.setValue(h); self.spin_ih.setValue(w)
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
                self.btn_extract_tex.setText("Texture Loaded")
                self.recalc()

    def select_from_library(self):
        dlg = TextureLibraryDialog(self)
        if dlg.exec():
            tex = dlg.get_selected_texture()
            if tex:
                self.frame_texture = tex
                self.btn_extract_tex.setText("Texture Loaded")
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

    def on_crop_change(self, rect): self.current_crop = rect; self.recalc()
    def pick_mat(self): 
        c = QColorDialog.getColor(self.mat_color); 
        if c.isValid(): self.mat_color = c; self.recalc()
    def pick_frame(self): 
        c = QColorDialog.getColor(self.frame_color); 
        if c.isValid(): 
            self.frame_color = c
            self.frame_texture = None
            self.btn_extract_tex.setText("Extract Texture")
            self.recalc()

    def recalc(self):
        if self.updating_ui: return
        face, rabbet, p_border = self.spin_face.value(), self.spin_rabbet.value(), self.spin_print_border.value()
        tol = 3.0/25.4 if self.unit == "in" else 3.0
        to_in = 1.0 if self.unit == "in" else 1/25.4

        if self.rb_mode_frame.isChecked():
            vis_w, vis_h = self.spin_iw.value(), self.spin_ih.value()
            if vis_w <= 0 or vis_h <= 0: return
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
            avail_w, avail_h = vis_w - m_l - m_r, vis_h - m_t - m_b
            if avail_w <= 0 or avail_h <= 0: self.lbl_stats.setText("Mat too large!"); return
            final_w, final_h = avail_w, avail_h
            if self.pixmap_full:
                aspect = (self.current_crop.width() * self.pixmap_full.width()) / (self.current_crop.height() * self.pixmap_full.height())
                if (avail_w / avail_h) > aspect: final_w = avail_h * aspect
                else: final_h = avail_w / aspect
            rem_w, rem_h = avail_w - final_w, avail_h - final_h
            align = self.combo_align.currentIndex()
            xl = rem_w/2 if align == 0 else (rem_w if align == 2 else 0)
            yt = rem_h/2 if align == 0 else (rem_h if align == 2 else 0)
            fmt, fmb, fml, fmr = m_t + yt, vis_h - (m_t+yt) - final_h, m_l + xl, vis_w - (m_l+xl) - final_w
            glass_w, glass_h = vis_w + 2*rabbet, vis_h + 2*rabbet
            mat_cut_w, mat_cut_h = glass_w - tol, glass_h - tol
            ow, oh = glass_w + 2*(face-rabbet), glass_h + 2*(face-rabbet)
        else:
            final_w, final_h = self.spin_art_w.value() - 2*(rabbet if self.chk_no_mat.isChecked() else p_border), self.spin_art_h.value() - 2*(rabbet if self.chk_no_mat.isChecked() else p_border)
            if final_w <= 0 or final_h <= 0: self.lbl_stats.setText("Border too large!"); return
            if self.chk_no_mat.isChecked(): fmt = fmb = fml = fmr = 0
            else: fmt, fmb, fml, fmr = self.spin_mat_t.value(), self.spin_mat_b.value(), self.spin_mat_l.value(), self.spin_mat_r.value()
            vis_w, vis_h = final_w + fml + fmr, final_h + fmt + fmb
            glass_w, glass_h = vis_w + 2*rabbet, vis_h + 2*rabbet
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
            'frame_texture': self.frame_texture, 'no_mat': self.chk_no_mat.isChecked() if self.rb_mode_art.isChecked() else False, 'link_all': self.chk_link_all.isChecked()
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
        p.setPen(QPen(Qt.GlobalColor.black, 3)); p.setBrush(Qt.BrushStyle.NoBrush); p.setFont(QFont(p.font().family(), 10))
        if is_vert:
            x_line = start.x() + offset
            p.drawLine(QPointF(start.x()-10, start.y()), QPointF(x_line+10, start.y())); p.drawLine(QPointF(start.x()-10, end.y()), QPointF(x_line+10, end.y())); p.drawLine(QPointF(x_line, start.y()), QPointF(x_line, end.y()))
            self.draw_arrow(p, QPointF(x_line, start.y()), "up"); self.draw_arrow(p, QPointF(x_line, end.y()), "down")
            p.save(); p.translate(x_line - 50 if offset < 0 else x_line + 50, (start.y() + end.y())/2); p.rotate(-90)
            p.drawText(QRectF(-1000, -300 if offset<0 else 20, 2000, 280), Qt.AlignmentFlag.AlignHCenter | (Qt.AlignmentFlag.AlignBottom if offset<0 else Qt.AlignmentFlag.AlignTop), text); p.restore()
        else:
            y_line = start.y() + offset
            p.drawLine(QPointF(start.x(), start.y()-10), QPointF(start.x(), y_line+10)); p.drawLine(QPointF(end.x(), start.y()-10), QPointF(end.x(), y_line+10)); p.drawLine(QPointF(start.x(), y_line), QPointF(end.x(), y_line))
            self.draw_arrow(p, QPointF(start.x(), y_line), "left"); self.draw_arrow(p, QPointF(end.x(), y_line), "right")
            p.drawText(QRectF(start.x(), y_line - 300 if offset < 0 else y_line + 10, end.x()-start.x(), 280), Qt.AlignmentFlag.AlignHCenter | (Qt.AlignmentFlag.AlignBottom if offset < 0 else Qt.AlignmentFlag.AlignTop), text)

    def draw_arrow(self, p, tip, direction):
        s = 15; a = QPolygonF([tip])
        if direction == "left": a.append(tip+QPointF(s,-s/3)); a.append(tip+QPointF(s,s/3))
        elif direction == "right": a.append(tip+QPointF(-s,-s/3)); a.append(tip+QPointF(-s,s/3))
        elif direction == "up": a.append(tip+QPointF(-s/3,s)); a.append(tip+QPointF(s/3,s))
        elif direction == "down": a.append(tip+QPointF(-s/3,-s)); a.append(tip+QPointF(s/3,-s))
        p.setBrush(Qt.GlobalColor.black); p.drawPolygon(a)

    def export_pdf(self):
        if not self.last_calc: return
        fn, _ = QFileDialog.getSaveFileName(self, "Save PDF", "Mat_Blueprint.pdf", "PDF Files (*.pdf)")
        if not fn: return
        d = self.last_calc; u = d['unit']
        writer = QPdfWriter(fn); writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        painter = QPainter(writer)
        
        # Page 1: Blueprint
        font = painter.font(); font.setPointSize(14); font.setBold(True); painter.setFont(font)
        painter.drawText(100, 150, "MAT BLUEPRINT [TECHNICAL]")
        font.setPointSize(10); font.setBold(False); painter.setFont(font)
        y = 300; h = 160
        for l in [f"CUT SIZE: {UnitUtils.format_dual(d['cut_w'], u)} x {UnitUtils.format_dual(d['cut_h'], u)}",
                  f"APERTURE: {UnitUtils.format_dual(d['img_w'], u)} x {UnitUtils.format_dual(d['img_h'], u)}",
                  f"PRINT SIZE: {UnitUtils.format_dual(d['print_w'], u)} x {UnitUtils.format_dual(d['print_h'], u)}"]:
            painter.drawText(100, int(y), l); y += h
        
        avail_w, avail_h = writer.width(), writer.height() - y - 2000
        scale = min(avail_w * 0.6 / d['cut_w'], avail_h * 0.6 / d['cut_h'])
        ox, oy = (writer.width() - d['cut_w']*scale)/2, y + (avail_h - d['cut_h']*scale)/2 + 1000
        ax, ay = ox + d['phys_left']*scale, oy + d['phys_top']*scale
        painter.setPen(QPen(Qt.GlobalColor.black, 5)); painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawRect(QRectF(ox, oy, d['cut_w']*scale, d['cut_h']*scale))
        painter.setBrush(QColor(230, 230, 230)); painter.drawRect(QRectF(ax, ay, d['img_w']*scale, d['img_h']*scale))
        self.draw_dimension(painter, QPointF(ax, ay), QPointF(ax+d['img_w']*scale, ay), f"Top: {UnitUtils.format_dual(d['phys_top'], u)}", -500, False)
        self.draw_dimension(painter, QPointF(ax, ay), QPointF(ax, ay+d['img_h']*scale), f"Left: {UnitUtils.format_dual(d['phys_left'], u)}", -500, True)

        # Page 2: Final Preview
        writer.newPage()
        font.setPointSize(14); font.setBold(True); painter.setFont(font)
        painter.drawText(100, 150, "VISUAL PREVIEW")
        
        preview_pixmap = self.preview.pixmap()
        if preview_pixmap:
            pw, ph = writer.width() * 0.8, writer.height() * 0.6
            scaled_p = preview_pixmap.scaled(int(pw), int(ph), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            px = (writer.width() - scaled_p.width()) / 2
            py = (writer.height() - scaled_p.height()) / 2
            painter.drawPixmap(int(px), int(py), scaled_p)

        painter.end()
