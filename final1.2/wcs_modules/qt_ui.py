"""
Modern Qt6 User Interface for WCS Tool
=======================================
Professional dark-themed GUI with draggable / resizable terminal panel.
Supports two modes:
  * Instrumentation Only  --  instrument + build
  * Full Pipeline         --  instrument + build + extract + simulate + report
"""

import sys
import os
import ctypes
import webbrowser
from typing import Optional, Dict, List

from .logging_config import setup_logging, rotate_log_file, get_logger

logger = get_logger(__name__)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QRadioButton, QButtonGroup,
    QGroupBox, QTextEdit, QProgressBar, QMessageBox,
    QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QGridLayout, QFrame, QSpinBox, QScrollArea,
    QSizePolicy, QFileDialog, QDialog, QComboBox, QSplitter,
    QMenu, QStatusBar, QTreeWidget, QTreeWidgetItem, QStyle
)
from PyQt6.QtCore import Qt, QThread, QTimer, QElapsedTimer, pyqtSignal, QSettings
from PyQt6.QtGui import QFont, QPalette, QColor, QTextCursor, QAction



# ============================================================================== 
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize
#  Style constants
# ==============================================================================

_FONT       = "Segoe UI"
_FONT_MONO  = "Consolas"
_CLR_BG     = "#1B2631"
_CLR_PANEL  = "#212F3D"
_CLR_SURF   = "#2C3E50"
_CLR_BORDER = "#34495E"
_CLR_TEXT   = "#ECF0F1"
_CLR_MUTED  = "#7F8C8D"
_CLR_ACCENT = "#3498DB"
_CLR_GREEN  = "#27AE60"
_CLR_YELLOW = "#F39C12"
_CLR_RED    = "#E74C3C"
_CLR_WHITE = "#92B0C7"

_APP_VERSION = "1.0.0"
_APP_NAME    = "WoCaSe"
_APP_FULL    = "Worst-Case Estimator"
_COMPANY     = "Schaeffler"

_ICON_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "assets", "lego.ico"
)

_MENU_ICON_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "assets", "menu.png"
)

_ARROW_UP_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "assets", "arrow_up.png"
).replace("\\", "/")

_ARROW_DN_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "assets", "arrow_down.png"
).replace("\\", "/")

_GROUP_CSS = f"""
    QGroupBox {{
        font-size: 13px; font-weight: bold;
        color: {_CLR_TEXT};
        border: 1px solid {_CLR_BORDER};
        border-radius: 8px;
        margin-top: 18px;
        margin-bottom: 4px;
        background: transparent;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        background: transparent;
        color: {_CLR_TEXT};
    }}
"""

_INPUT_CSS = f"""
    QLineEdit {{
        border: 1px solid {_CLR_BORDER}; border-radius: 6px;
        padding: 7px 12px;
        background: {_CLR_SURF}; color: white;
        font-size: 11pt;
    }}
    QLineEdit:focus {{ border-color: {_CLR_ACCENT}; }}
"""

_CHECK_CSS = f"""
    QCheckBox {{ color: {_CLR_TEXT}; spacing: 8px; font-size: 10pt; }}
    QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 4px; }}
    QCheckBox::indicator:unchecked {{
        border: 2px solid {_CLR_MUTED}; background: {_CLR_SURF};
    }}
    QCheckBox::indicator:checked {{
        border: 2px solid {_CLR_GREEN}; background: {_CLR_GREEN};
    }}

    /* Disabled states (pale/greyed look) */
    QCheckBox::indicator:unchecked:disabled {{
        border: 2px solid #566573;        /* darker grey border */
        background: #566573;              /* pale/dim fill */
    }}
    QCheckBox::indicator:checked:disabled {{
        border: 2px solid #566573;        /* darker grey border */
        background: #566573;              /* pale grey-green fill */
    }}

    QCheckBox:disabled {{ color: #566573; }}
"""

_SPIN_CSS = f"""
    QSpinBox {{
        border: 2px solid {_CLR_WHITE}; border-radius: 7px;
        padding: 6px 10px; background: {_CLR_SURF}; color: white;
        font-size: 10pt;
        padding-right: 44px;  /* if you have two blocks top/bottom */
        /* soften the selection */
        selection-background-color: {_CLR_SURF};   /* sau rgba(0,0,0,0) */
        selection-color: {_CLR_TEXT};
    }}

    QSpinBox::up-button, QSpinBox::down-button {{
        width: 25px;
        border: none;
    }}

    QSpinBox::up-button {{
        border-top-right-radius: 4px;
        border-left: 2px solid {_CLR_WHITE};
        border-bottom: 2px solid {_CLR_WHITE};
    }}

    QSpinBox::down-button {{
        border-top: 2px solid {_CLR_WHITE};
        border-bottom-right-radius: 4px;
        border-left: 2px solid {_CLR_WHITE};
    }}  




    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background: {_CLR_ACCENT};
       
    }}
    QSpinBox::up-button:pressed {{  
        background: {_CLR_GREEN};    /* sus = verde */
    }}
    QSpinBox::down-button:pressed {{
        background: {_CLR_GREEN};      /* down = red */
    }}

    QSpinBox:disabled {{ color: #566573; }}
 """

# Standard light-theme spinbox that looks like a native desktop widget
_SPIN_NATIVE_CSS = f"""
    QSpinBox {{
        border: 1px solid {_CLR_BORDER}; border-radius: 6px;
        padding: 7px 12px;
        padding-right: 28px;
        background: {_CLR_SURF}; color: white;
        font-size: 11pt;
        selection-background-color: {_CLR_ACCENT};
        selection-color: white;
    }}
    QSpinBox:focus {{ border-color: {_CLR_ACCENT}; }}
    QSpinBox:disabled {{
        color: #566573;
        border-color: #566573;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        width: 20px;
        border: none;
        background: transparent;
        subcontrol-origin: border;
    }}
    QSpinBox::up-button {{
        subcontrol-position: top right;
        border-top-right-radius: 6px;
        border-left: 1px solid {_CLR_BORDER};
        border-bottom: 1px solid {_CLR_BORDER};
    }}
    QSpinBox::down-button {{
        subcontrol-position: bottom right;
        border-bottom-right-radius: 6px;
        border-left: 1px solid {_CLR_BORDER};
        border-top: 1px solid {_CLR_BORDER};
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background: {_CLR_ACCENT};
    }}
    QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{
        background: {_CLR_GREEN};
    }}
    QSpinBox::up-arrow {{
        image: url({_ARROW_UP_PATH});
        width: 14px; height: 14px;
    }}
    QSpinBox::down-arrow {{
        image: url({_ARROW_DN_PATH});
        width: 14px; height: 14px;
    }}
"""

# ==============================================================================
#  Bench Upload Dialog
# ==============================================================================

class BenchUploadDialog(QDialog):
    """Minimal dialog — just enter the project folder name from bench_results."""


    _EXCEL_NAME = "RuntimeMeasureReduction.xlsx"

    def __init__(self, parent=None, project_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Train Simulator  —  Import Bench Data")
        self.setMinimumSize(400, 200)
        self.resize(560, 260)
        self._original_ok_text = "Import && Train"
        self._build_ui(project_name)

    def _on_import_clicked(self):
        self._btn_ok.setText("Load")
        self._btn_ok.setEnabled(False)
        QApplication.processEvents()
        self.accept()

    def _build_ui(self, project_name: str):
        from . import path_utils
        lo = QVBoxLayout(self)
        lo.setSpacing(14)
        lo.setContentsMargins(24, 20, 24, 20)

        # --- Info ---
        banner = QLabel(
            "Enter the <b>project folder name</b> from the centralized "
            "bench results location.<br>"
            "The tool reads <code>RuntimeMeasureReduction.xlsx</code> and "
            "extracts calibrations from <code>icsp_dem_cnf.c</code> automatically.")
        banner.setWordWrap(True)
        banner.setFont(QFont(_FONT, 9))
        banner.setStyleSheet(f"color: {_CLR_TEXT}; padding: 0;")
        lo.addWidget(banner)

        # --- Project name input ---
        r = QHBoxLayout()
        lbl = QLabel("Project:")
        lbl.setFont(QFont(_FONT, 10, QFont.Weight.Bold))
        r.addWidget(lbl)

        self._inp_proj = QLineEdit(project_name)
        self._inp_proj.setMinimumHeight(36)
        self._inp_proj.setFont(QFont(_FONT, 11))
        self._inp_proj.setPlaceholderText("e.g. PROJ2_0U0_OB6_024")
        self._inp_proj.setStyleSheet(f"""
            QLineEdit {{
                background: {_CLR_SURF}; color: {_CLR_TEXT};
                border: 2px solid {_CLR_BORDER}; border-radius: 6px;
                padding: 4px 10px;
            }}
            QLineEdit:focus {{ border-color: {_CLR_ACCENT}; }}
        """)
        r.addWidget(self._inp_proj, stretch=1)
        lo.addLayout(r)

        # --- Resolved path preview ---
        self._lbl_path = QLabel("")
        self._lbl_path.setFont(QFont(_FONT, 8))
        self._lbl_path.setWordWrap(True)
        self._lbl_path.setStyleSheet(f"color: {_CLR_MUTED}; padding: 0 0 0 70px;")
        lo.addWidget(self._lbl_path)
        self._inp_proj.textChanged.connect(self._update_preview)
        self._update_preview(project_name)

        lo.addStretch()

        # --- Buttons ---
        r_btn = QHBoxLayout()
        r_btn.addStretch()


        # self._btn_ok = QPushButton("Import && Train")
        self._btn_ok = QPushButton(self._original_ok_text)
        self._btn_ok.setMinimumHeight(38)
        self._btn_ok.setMinimumWidth(160)
        self._btn_ok.setFont(QFont(_FONT, 10, QFont.Weight.Bold))
        self._btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_ok.setStyleSheet(f"""
            QPushButton {{
                background: {_CLR_ACCENT}; color: #fff;
                border: none; border-radius: 6px; padding: 0 18px;
            }}
            QPushButton:hover {{ background: #3B8ED0; }}
        """)
        self._btn_ok.clicked.connect(self._on_import_clicked)
        r_btn.addWidget(self._btn_ok)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setMinimumHeight(38)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: {_CLR_SURF}; color: {_CLR_TEXT};
                border: 1px solid {_CLR_BORDER}; border-radius: 6px;
                padding: 0 18px;
            }}
            QPushButton:hover {{ background: #415B76; }}
        """)
        btn_cancel.clicked.connect(self.reject)
        r_btn.addWidget(btn_cancel)
        lo.addLayout(r_btn)

    def _update_preview(self, text: str):
        """Show resolved paths and validation status using real project location."""
        from . import path_utils
        name = text.strip()
        if not name:
            self._lbl_path.setText("")
            return
        proj_dir = path_utils.create_case_path(name)
        if proj_dir is None:
            self._lbl_path.setText(f"Invalid format: {name}")
            self._lbl_path.setStyleSheet(f"color: { _CLR_RED}; padding: 0 0 0 70px; font-size: 8pt;")
            return
        xlsx = os.path.join(proj_dir, self._EXCEL_NAME)
        ok_dir = os.path.isdir(proj_dir)
        ok_xl = os.path.isfile(xlsx)
        parts = []
        parts.append(f"{'✓' if ok_dir else '✗'} {proj_dir}")
        parts.append(f"{'✓' if ok_xl else '✗'} {self._EXCEL_NAME}")
        color = _CLR_GREEN if (ok_dir and ok_xl) else _CLR_RED
        self._lbl_path.setText("  |  ".join(parts))
        self._lbl_path.setStyleSheet(
            f"color: {color}; padding: 0 0 0 70px; font-size: 8pt;")

    def get_project_name(self) -> str:
        return self._inp_proj.text().strip()


# ==============================================================================
#  Output redirector  (routes stdout/stderr to the terminal widget)
# ==============================================================================

class _Redirect:
    def __init__(self, sig):
        self._sig = sig

    def write(self, t):
        s = t.rstrip()
        if s:
            self._sig.emit(s)

    def flush(self):
        pass


# ==============================================================================
#  Worker thread
# ==============================================================================

class PipelineWorker(QThread):
    progress        = pyqtSignal(str)
    finished        = pyqtSignal(bool, str)
    command_output  = pyqtSignal(str)
    simulation_done = pyqtSignal(object)

    def __init__(self, op: str, params: dict):
        super().__init__()
        self._op = op
        self._p  = params

    def run(self):
        try:
            from . import main as wcs
            import sys as _sys
            old_out, old_err = _sys.stdout, _sys.stderr
            _sys.stdout = _Redirect(self.command_output)
            _sys.stderr = _Redirect(self.command_output)
            try:
                kw = {
                    'target_name':         self._p.get('target_name'),
                    'run_simulation':      self._p.get('run_simulation', False),
                    'sim_generate_excel':  self._p.get('sim_generate_excel', True),
                    'sim_run_monte_carlo': self._p.get('sim_run_monte_carlo', True),
                    'sim_mc_cycles':       self._p.get('sim_mc_cycles', 50_000),
                    'sim_yellow_threshold': self._p.get('sim_yellow_threshold', 500),
                    'progress_callback':   lambda m: self.command_output.emit(m),
                }
                if self._op == "system_file":
                    self.progress.emit("Starting System File process...")
                    self.command_output.emit(
                        f"\n[CMD] Processing: {self._p['proj_name']}\n")
                    try:
                        res = wcs.process_system_file(
                            proj_name=self._p['proj_name'],
                            td5_path=self._p['td5_path'],
                            build_type=self._p['build_type'],
                            rule=self._p['rule'], **kw)
                    except Exception as e:
                        self.command_output.emit(f"\n[ERROR] {e}")
                        self.finished.emit(False, str(e))
                        return
                    self.simulation_done.emit(res)
                    self.finished.emit(True, "Completed successfully!")

                elif self._op == "mks":
                    self.progress.emit("Starting MKS process...")
                    self.command_output.emit(
                        f"\n[CMD] Processing MKS: {self._p['release_name']}\n")
                    try:
                        res = wcs.process_mks_release(
                            release_name=self._p['release_name'],
                            td5_path=self._p['td5_path'],
                            build_type=self._p['build_type'],
                            rule=self._p['rule'], **kw)
                    except Exception as e:
                        self.command_output.emit(f"\n[ERROR] {e}")
                        self.finished.emit(False, str(e))
                        return
                    self.simulation_done.emit(res)
                    self.finished.emit(True, "Completed successfully!")
            finally:
                _sys.stdout, _sys.stderr = old_out, old_err
        except Exception as e:
            self.command_output.emit(f"\n[ERROR] {e}")
            self.finished.emit(False, str(e))


# ==============================================================================
#  Contact Support Dialog
# ==============================================================================


class ContactSupportDialog(QDialog):
    """Simple dialog with direct contact links – Teams chat and Outlook email."""

    _TEAMS_URL   = "https://teams.microsoft.com/l/chat/0/0?users=yosif.al-yafeai@mail.schaeffler.com"
    _OUTLOOK_URL = "mailto:yosif.al-yafeai@mail.schaeffler.com?subject=WoCaSe%20Support%20Request"
    

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Contact Support")
        self.setFixedSize(440, 300)
        self.setStyleSheet(
            f"QDialog {{ background:{_CLR_BG}; color:{_CLR_TEXT}; "
            f"font-family:'Segoe UI'; }}"
        )
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)

        # ── Header ──────────────────────────────────────────────────────────
        title = QLabel("Contact Support")
        title.setStyleSheet(
            f"font-size:17px; font-weight:600; color:{_CLR_ACCENT};"
        )
        root.addWidget(title)

        info = QLabel(
            "Need help? Reach out directly via Microsoft Teams or Outlook."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{_CLR_MUTED}; font-size:12px;")
        root.addWidget(info)

        root.addSpacing(6)

        # ── Teams button ────────────────────────────────────────────────────
        btn_teams = QPushButton(" Open MS Teams ")
        btn_teams.setFixedHeight(46)
        btn_teams.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_teams.setStyleSheet(
            f"QPushButton {{"
            f"  background:{_CLR_ACCENT}; color:#fff;"
            f"  border:none; border-radius:6px;"
            f"  font-size:13px; font-weight:600;"
            f"}}"
            f"QPushButton:hover {{ background:#2980b9; }}"
        )
        btn_teams.setToolTip("sg275887@user.schaeffler.com")
        btn_teams.clicked.connect(
            lambda: webbrowser.open(self._TEAMS_URL)
        )
        root.addWidget(btn_teams)

        # ── Outlook button ───────────────────────────────────────────────────
        btn_mail = QPushButton("  Send Email (Outlook)")
        btn_mail.setFixedHeight(46)
        btn_mail.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_mail.setStyleSheet(
            f"QPushButton {{"
            f"  background:{_CLR_SURF}; color:{_CLR_TEXT};"
            f"  border:1px solid {_CLR_BORDER}; border-radius:6px;"
            f"  font-size:13px; font-weight:600;"
            f"}}"
            f"QPushButton:hover {{ background:{_CLR_BORDER}; }}"
        )
        btn_mail.setToolTip("yosif.al-yafeai@mail.schaeffler.com")
        btn_mail.clicked.connect(
            lambda: webbrowser.open(self._OUTLOOK_URL)
        )
        root.addWidget(btn_mail)

        root.addStretch()

        # ── Close button ─────────────────────────────────────────────────────
        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(32)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(
            f"QPushButton {{"
            f"  background:transparent; color:{_CLR_MUTED};"
            f"  border:1px solid {_CLR_BORDER}; border-radius:5px;"
            f"  font-size:12px;"
            f"}}"
            f"QPushButton:hover {{ color:{_CLR_TEXT}; border-color:{_CLR_MUTED}; }}"
        )
        btn_close.clicked.connect(self.accept)
        root.addWidget(btn_close)



class BenchImportWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, excel_path: str, project_path: str, project_name: str):
        super().__init__()
        self.excel_path = excel_path
        self.project_path = project_path
        self.project_name = project_name

    def run(self):
        try:
            from dem_simulator.bench_store import ingest_single_project
            key = ingest_single_project(
                excel_path=self.excel_path,
                project_path=self.project_path,
                project_name=self.project_name,
            )
            self.finished.emit(True, key)
        except Exception as exc:
            self.finished.emit(False, str(exc))

# ==============================================================================
#  Main window
# ==============================================================================


class MainWindowApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self._worker          = None
        self._sim_result      = None
        self._results_tab_idx: Optional[int] = None
        self._elapsed         = QElapsedTimer()
        self._tick_timer      = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._update_elapsed)
        self._is_running      = False
        self._refresh_timer   = QTimer(self)   # debounce for _refresh_targets
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(400)   # 400 ms after the last keypress
        self._refresh_timer.timeout.connect(self._refresh_targets_debounced)
        self._build_ui()

    # --------------------------------------------------------------------------
    #  Root layout
    # --------------------------------------------------------------------------

    def _build_ui(self):
        self.setWindowTitle(f"{_APP_NAME}  -  {_APP_FULL}")
        # self.setGeometry(70, 50, 1120, 880)
        self.setMinimumSize(540, 480)
        self._apply_theme()

        # --- Menu bar ---
        self._build_menu_bar()

        # --- Status bar ---
        sb = QStatusBar()
        sb.setFont(QFont(_FONT, 8))
        sb.setStyleSheet(f"""
            QStatusBar {{
                background: {_CLR_PANEL};
                color: {_CLR_MUTED};
                border-top: 1px solid {_CLR_BORDER};
                padding: 2px 8px;
            }}
            QStatusBar::item {{ border: none; }}
        """)
        self._status_msg = QLabel("Ready")
        self._status_msg.setFont(QFont(_FONT, 8))
        self._status_msg.setStyleSheet(f"color: {_CLR_MUTED};")
        sb.addWidget(self._status_msg, 1)
        self._status_label = QLabel(f"{_COMPANY}  |  {_APP_NAME} v{_APP_VERSION}")
        self._status_label.setFont(QFont(_FONT, 8))
        self._status_label.setStyleSheet(f"color: {_CLR_MUTED};")
        sb.addPermanentWidget(self._status_label)
        self.setStatusBar(sb)

        # --- Project Navigator (left sidebar) ---
        self._sidebar = self._build_sidebar()

        # --- Main content (right side) ---
        main_panel = QWidget()
        ml = QVBoxLayout(main_panel)
        ml.setSpacing(8)
        ml.setContentsMargins(12, 8, 0, 0)

        # tabs
        self._tabs = QTabWidget()
        self._tabs.setFont(QFont(_FONT, 10))
        self._tabs.setDocumentMode(False)
        self._tabs.setStyleSheet(f"""
        /* Pane (content area) with rounded corners */
        QTabWidget::pane {{
            border: 1px solid {_CLR_BORDER};
            border-radius: 14px;
            background: {_CLR_BG};
            margin-top: 10px;      /* leaves room for the pill tabs */
            padding: 8px;          /* avoids clipping inside rounded pane */
        }}

        /* Prevent native base from drawing under our custom tabs */
        QTabBar {{ qproperty-drawBase: 0; }}

        /* PILL TABS (oval) */
        QTabBar::tab {{
            height: 32px;                  /* pill height */
            padding: 0 24px;               /* horizontal space */
            margin: 6px 6px;               /* spacing between pills */
            border: 1px solid {_CLR_BORDER};
            border-radius: 16px;           /* half of height → oval/pill */
            background: {_CLR_SURF};
            color: {_CLR_MUTED};
            font-weight: bold;
            font-size: 10pt;
        }}

        /* Selected pill */
        QTabBar::tab:selected {{
            background: {_CLR_ACCENT};
            color: white;
            border-color: {_CLR_ACCENT};
        }}

        /* Hover on unselected pill */
        QTabBar::tab:hover:!selected {{
            background: #415B76;
            color: white;
            border-color: #415B76;
        }}
    """)

        self._tabs.addTab(self._tab_instrument(), "  Instrumentation")
        self._results_widget  = self._tab_results()
        self._results_tab_idx = None
        self._toggle_results_tab(self._chk_sim.isChecked())
        self._tabs.addTab(self._tab_bench_train(), "  Train Simulator")

        ml.addWidget(self._tabs, stretch=1)

        # footer: progress bar + run button + clear
        self._btn_run = QPushButton("Run Instrumentation")
        self._btn_run.setFont(QFont(_FONT, 11, QFont.Weight.Bold))
        self._btn_run.setMinimumHeight(46)
        self._btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_run.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {_CLR_GREEN}, stop:1 #2ECC71);
                color: white; border: none; border-radius: 10px;
                padding: 0 28px; font-size: 12pt;
            }}
            QPushButton:hover    {{ background: #229954; }}
            QPushButton:pressed  {{ background: #1E8449; }}
            QPushButton:disabled {{ background: #566573; }}
        """)
        self._btn_run.setToolTip("Run the selected workflow")
        self._btn_run.clicked.connect(self._run)

        self._progress = QProgressBar()
        self._progress.setMinimumHeight(8)
        self._progress.setMaximumHeight(16)
        self._progress.setVisible(False)
        self._progress.setTextVisible(False)
        # self._progress.setSizePolicy(
        #     QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        _sp_prog = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        _sp_prog.setRetainSizeWhenHidden(True)
        self._progress.setSizePolicy(_sp_prog)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {_CLR_BORDER}; border-radius: 6px;
                min-height: 8px; max-height: 14px; background: {_CLR_SURF};
            }}
            QProgressBar::chunk {{ background: {_CLR_ACCENT}; border-radius: 5px; }}
        """)

        _ICONS_DIR = os.path.join(os.path.dirname(__file__), 'assets')

        run_col = QVBoxLayout()
        run_col.setSpacing(3)
        run_col.addWidget(self._progress)
        run_col.addWidget(self._btn_run)

        self._lbl_elapsed = QLabel("")
        self._lbl_elapsed.setFont(QFont(_FONT_MONO, 11, QFont.Weight.Bold))
        self._lbl_elapsed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_elapsed.setMinimumWidth(90)
        self._lbl_elapsed.setStyleSheet(
            f"color:{_CLR_TEXT}; background:{_CLR_SURF};"
            f"border:2px solid {_CLR_MUTED}; border-radius:8px; padding:4px 10px;"
        )

        self._lbl_elapsed.setVisible(False)

        foot = QHBoxLayout()
        foot.setSpacing(12)
        foot.setContentsMargins(17, 0, 17, 0)
        foot.addLayout(run_col, stretch=1)
        foot.addWidget(self._lbl_elapsed)
        ml.addLayout(foot)

        # --- Horizontal splitter: sidebar | main content ---
        root = QWidget()
        self.setCentralWidget(root)
        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter = self._h_splitter
        h_splitter.setChildrenCollapsible(True)
        h_splitter.setHandleWidth(3)
        h_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {_CLR_BORDER};
            }}
            QSplitter::handle:hover {{
                background: {_CLR_ACCENT};
            }}
        """)
        h_splitter.addWidget(self._sidebar)
        h_splitter.addWidget(main_panel)
        h_splitter.setStretchFactor(0, 0)   # sidebar: fixed
        h_splitter.setStretchFactor(1, 1)   # main: stretches
        h_splitter.setSizes([220, 800])
        h_splitter.splitterMoved.connect(self._on_h_splitter_moved)

        root_lay.addWidget(h_splitter)

        # sync initial state
        self._on_sim_toggle(self._chk_sim.isChecked())


    def _on_bench_import_done(self, ok: bool, msg: str, name: str):
        QApplication.restoreOverrideCursor()
        self._status_msg.setText("Ready")

        if hasattr(self, "_last_bench_dialog") and self._last_bench_dialog:
            dlg = self._last_bench_dialog
            if hasattr(dlg, "_btn_ok"):
                dlg._btn_ok.setText(dlg._original_ok_text)
                dlg._btn_ok.setEnabled(True)

        if ok:
            QMessageBox.information(
                self, "Import Successful",
                f"Project '{msg}' imported successfully!\n\n"
                "• Calibration values extracted from C sources\n"
                "• Bench measurements parsed from Excel\n"
                "• Cost coefficients auto-fitted\n\n"
                "The simulator is now trained for this project.")
            self._add_project_to_list(name, mode="Bench Import", status="success")
        else:
            QMessageBox.critical(self, "Import Failed", msg)
            self._add_project_to_list(name, mode="Bench Import", status="failed")
            

    # --------------------------------------------------------------------------
    #  Menu bar
    # --------------------------------------------------------------------------

    def _build_menu_bar(self):
        mb = self.menuBar()
        mb.setFont(QFont(_FONT, 9))

        # Generate a crisp anti-aliased checkmark PNG for QMenu::indicator
        import tempfile
        from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor
        from PyQt6.QtCore import QPointF
        _ck_px = QPixmap(14, 14)
        _ck_px.fill(Qt.GlobalColor.transparent)
        _ck_p = QPainter(_ck_px)
        _ck_p.setRenderHint(QPainter.RenderHint.Antialiasing)
        _ck_pen = QPen(QColor("#ffffff"), 2.0)
        _ck_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        _ck_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        _ck_p.setPen(_ck_pen)
        _ck_p.drawPolyline([QPointF(2.5, 7.0), QPointF(5.5, 10.5), QPointF(11.5, 3.5)])
        _ck_p.end()
        _CHECKMARK_PATH = os.path.join(tempfile.gettempdir(), "wcs_menu_check.png").replace(os.sep, '/')
        _ck_px.save(_CHECKMARK_PATH, "PNG")

        mb.setStyleSheet(f"""
            QMenuBar {{
                background: {_CLR_PANEL};
                color: {_CLR_TEXT};
                border-bottom: 1px solid {_CLR_BORDER};
                padding: 2px 6px;
            }}
            QMenuBar::item {{
                background: transparent;
                padding: 6px 14px;
                border-radius: 4px;
            }}
            QMenuBar::item:selected {{
                background: {_CLR_SURF};
            }}
            QMenu {{
                background: {_CLR_PANEL};
                color: {_CLR_TEXT};
                border: 1px solid {_CLR_BORDER};
                border-radius: 6px;
                padding: 4px 0;
            }}
            QMenu::item {{
                padding: 8px 28px 8px 16px;
            }}
            QMenu::item:selected {{
                background: {_CLR_ACCENT};
                color: white;
                border-radius: 4px;
            }}
            QMenu::separator {{
                height: 1px;
                background: {_CLR_BORDER};
                margin: 4px 10px;
            }}
            QMenu::indicator {{
                width: 14px;
                height: 14px;
                margin-left: 6px;
                border-radius: 3px;
            }}
            QMenu::indicator:non-exclusive:unchecked {{
                border: 1.5px solid {_CLR_MUTED};
                background: transparent;
                border-radius: 3px;
            }}
            QMenu::indicator:non-exclusive:checked {{
                border: 1.5px solid {_CLR_ACCENT};
                background: {_CLR_ACCENT};
                border-radius: 3px;
                image: url({_CHECKMARK_PATH});
            }}
        """)

        # --- Hamburger toggle (before File) ---
        self._btn_hamburger = QPushButton()
        self._btn_hamburger.setIcon(QIcon(_MENU_ICON_PATH))
        self._btn_hamburger.setIconSize(QSize(24, 24))
        self._btn_hamburger.setFixedSize(34, 28)
        self._btn_hamburger.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_hamburger.setToolTip("Toggle Explorer  (Ctrl+B)")
        self._btn_hamburger.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 0;
                margin: 0 2px;
            }}
            QPushButton:hover {{
                background: {_CLR_SURF};
            }}
            QPushButton:pressed {{
                background: {_CLR_BORDER};
            }}
        """)
        self._btn_hamburger.clicked.connect(lambda: self._toggle_sidebar(None))
        mb.setCornerWidget(self._btn_hamburger, Qt.Corner.TopLeftCorner)

        # --- File ---
        m_file = mb.addMenu("&File")

        act_import = QAction("Import Project…", self)
        act_import.setShortcut("Ctrl+I")
        act_import.triggered.connect(self._import_project)
        m_file.addAction(act_import)

        m_file.addSeparator()

        act_clear = QAction("Clear Terminal", self)
        act_clear.setShortcut("Ctrl+L")
        act_clear.triggered.connect(lambda: self._term_widget.clear())
        m_file.addAction(act_clear)

        m_file.addSeparator()

        act_exit = QAction("Exit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)

        # --- Edit ---
        m_edit = mb.addMenu("&Edit")

        act_undo = QAction("Undo", self)
        act_undo.setShortcut("Ctrl+Z")
        act_undo.triggered.connect(lambda: self._edit_action("undo"))
        m_edit.addAction(act_undo)

        act_redo = QAction("Redo", self)
        act_redo.setShortcut("Ctrl+Y")
        act_redo.triggered.connect(lambda: self._edit_action("redo"))
        m_edit.addAction(act_redo)

        m_edit.addSeparator()

        act_cut = QAction("Cut", self)
        act_cut.setShortcut("Ctrl+X")
        act_cut.triggered.connect(lambda: self._edit_action("cut"))
        m_edit.addAction(act_cut)

        act_copy = QAction("Copy", self)
        act_copy.setShortcut("Ctrl+C")
        act_copy.triggered.connect(lambda: self._edit_action("copy"))
        m_edit.addAction(act_copy)

        act_paste = QAction("Paste", self)
        act_paste.setShortcut("Ctrl+V")
        act_paste.triggered.connect(lambda: self._edit_action("paste"))
        m_edit.addAction(act_paste)

        act_del = QAction("Delete", self)
        act_del.setShortcut("Del")
        act_del.triggered.connect(lambda: self._edit_action("delete"))
        m_edit.addAction(act_del)

        m_edit.addSeparator()

        act_sel = QAction("Select All", self)
        act_sel.setShortcut("Ctrl+A")
        act_sel.triggered.connect(lambda: self._edit_action("selectAll"))
        m_edit.addAction(act_sel)

        m_edit.addSeparator()

        act_find = QAction("Find / Replace…", self)
        act_find.setShortcut("Ctrl+H")
        act_find.triggered.connect(self._show_find_replace)
        m_edit.addAction(act_find)

        # --- Tools ---
        m_tools = mb.addMenu("&Tools")
        act_bench = QAction("Train Simulator from Bench…", self)
        act_bench.triggered.connect(self._open_bench_dialog)
        m_tools.addAction(act_bench)

        act_store = QAction("Set Bench Store Path…", self)
        act_store.triggered.connect(self._copy_store_db)
        m_tools.addAction(act_store)

        # --- View ---
        m_view = mb.addMenu("&View")
        act_nav = QAction("Project Navigator", self)
        act_nav.setCheckable(True)
        act_nav.setChecked(True)
        act_nav.setShortcut("Ctrl+B")
        act_nav.toggled.connect(self._toggle_sidebar)
        m_view.addAction(act_nav)
        self._act_nav = act_nav

        m_view.addSeparator()

        act_dem = QAction("Enable DEM Simulation", self)
        act_dem.setCheckable(True)
        act_dem.setChecked(False)
        act_dem.setShortcut("Ctrl+D")
        act_dem.setToolTip("Enable DEM Simulation after build  (Ctrl+D)")
        act_dem.toggled.connect(lambda on: self._chk_sim.setChecked(on))
        # keep in sync when checkbox changes from the UI
        m_view.addAction(act_dem)
        self._act_dem = act_dem

        # --- Help ---
        m_help = mb.addMenu("&Help")
        act_support = QAction("Contact Support", self)
        act_support.setShortcut("Ctrl+Shift+S")
        act_support.triggered.connect(self._show_contact_support)
        m_help.addAction(act_support)

        m_help.addSeparator()

        act_about = QAction(f"About {_APP_NAME}", self)
        act_about.triggered.connect(self._show_about)
        m_help.addAction(act_about)
    # --------------------------------------------------------------------------
    #  Project Navigator (sidebar)
    # --------------------------------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        wrapper = QWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)

        # --- Collapsible panel ---
        self._sidebar_panel = QWidget()
        self._sidebar_panel.setMinimumWidth(0)
        self._sidebar_panel.setStyleSheet(f"""
            QWidget#sidebarPanel {{
                background: {_CLR_BG};
                border-right: 1px solid {_CLR_BORDER};
            }}
        """)
        self._sidebar_panel.setObjectName("sidebarPanel")

        lo = QVBoxLayout(self._sidebar_panel)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        # ── Header row (styled to match pill-tab aesthetics) ──
        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(12, 10, 8, 10)
        hdr_row.setSpacing(6)

        hdr_icon = QLabel("📂")
        hdr_icon.setFont(QFont(_FONT, 11))
        hdr_icon.setStyleSheet("background: transparent;")
        hdr_row.addWidget(hdr_icon)

        hdr_lbl = QLabel("EXPLORER")
        hdr_lbl.setFont(QFont(_FONT, 9, QFont.Weight.Bold))
        hdr_lbl.setStyleSheet(f"""
            color: {_CLR_MUTED};
            background: transparent;
            letter-spacing: 1px;
        """)
        hdr_row.addWidget(hdr_lbl)
        hdr_row.addStretch()

        _HDR_BTN_CSS = f"""
            QPushButton {{
                background: transparent; color: {_CLR_MUTED};
                border: none; border-radius: 5px;
            }}
            QPushButton:hover {{
                background: {_CLR_SURF}; color: {_CLR_TEXT};
            }}
        """

        btn_minimize = QPushButton("−")
        btn_minimize.setFixedSize(24, 24)
        btn_minimize.setFont(QFont(_FONT, 12))
        btn_minimize.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_minimize.setToolTip("Minimize Explorer")
        btn_minimize.setStyleSheet(_HDR_BTN_CSS)
        btn_minimize.clicked.connect(lambda: self._toggle_sidebar(None))
        hdr_row.addWidget(btn_minimize)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setFont(QFont(_FONT, 10))
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setToolTip("Close Explorer")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {_CLR_MUTED};
                border: none; border-radius: 5px;
            }}
            QPushButton:hover {{
                background: rgba(231, 76, 60, 0.25); color: {_CLR_RED};
            }}
        """)
        btn_close.clicked.connect(lambda: self._toggle_sidebar(None))
        hdr_row.addWidget(btn_close)

        hdr_w = QWidget()
        hdr_w.setObjectName("sidebarHdr")
        hdr_w.setStyleSheet(f"""
            QWidget#sidebarHdr {{
                background: {_CLR_BG};
                border-bottom: 1px solid {_CLR_BORDER};
            }}
        """)
        hdr_w.setLayout(hdr_row)
        lo.addWidget(hdr_w)

        # ── Section label (like VS Code's sidebar section headers) ──
        sec_lbl = QLabel("  PROJECT NAVIGATOR")
        sec_lbl.setFont(QFont(_FONT, 8, QFont.Weight.Bold))
        sec_lbl.setFixedHeight(28)
        sec_lbl.setStyleSheet(f"""
            background: {_CLR_PANEL};
            color: {_CLR_MUTED};
            padding-left: 12px;
            border-bottom: 1px solid {_CLR_BORDER};
        """)
        lo.addWidget(sec_lbl)

        # ── Tree widget (refined styling) ──
        _ICONS_DIR_TREE = os.path.join(os.path.dirname(__file__), 'assets')

        self._folder_icon = QIcon(os.path.join(_ICONS_DIR_TREE, 'folder.png'))
        self._file_icon = QIcon(os.path.join(_ICONS_DIR_TREE, 'file.png'))

        # Generate small 12x12 chevron arrows programmatically (no PNG needed)
        from PyQt6.QtGui import QPixmap, QPainter, QPolygon, QBrush
        from PyQt6.QtCore import QPoint
        import tempfile, os as _os

        def _make_arrow_png(direction: str) -> str:
            """Draw a small triangle arrow and save to a temp PNG, return path."""
            px = QPixmap(12, 12)
            px.fill(Qt.GlobalColor.transparent)
            p = QPainter(px)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(_CLR_MUTED)))
            if direction == "right":
                poly = QPolygon([QPoint(3, 2), QPoint(10, 6), QPoint(3, 10)])
            else:  # down
                poly = QPolygon([QPoint(2, 3), QPoint(10, 3), QPoint(6, 10)])
            p.drawPolygon(poly)
            p.end()
            path = _os.path.join(tempfile.gettempdir(), f"wcs_arrow_{direction}.png")
            px.save(path, "PNG")
            return path.replace(_os.sep, '/')

        _chevron_right = _make_arrow_png("right")
        _chevron_down  = _make_arrow_png("down")




        self._proj_tree = QTreeWidget()
        self._proj_tree.setHeaderHidden(True)
        self._proj_tree.setFont(QFont(_FONT, 9))
        # self._proj_tree.setIndentation(14)
        self._proj_tree.setIndentation(18)
        self._proj_tree.setIconSize(QSize(16, 16))
        self._proj_tree.setAnimated(True)
        self._proj_tree.setRootIsDecorated(True)
        self._proj_tree.setExpandsOnDoubleClick(True)
        self._proj_tree.setStyleSheet(f"""
            QTreeWidget {{
                background: {_CLR_BG};
                color: {_CLR_TEXT};
                border: none;
                outline: none;
                padding: 4px 0;
            }}
            QTreeWidget::item {{
                padding: 3px 8px;
                border: none;
                border-radius: 0;
            }}
            QTreeWidget::item:hover {{
                background: rgba(52, 152, 219, 0.10);
            }}
            QTreeWidget::item:selected {{
                background: rgba(52, 152, 219, 0.22);
                color: {_CLR_TEXT};
            }}
            QTreeWidget::item:selected:active {{
                background: rgba(52, 152, 219, 0.30);
                color: white;
            }}

            /* Scrollbar styling to match tool theme */
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {_CLR_BORDER};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {_CLR_MUTED};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
            }}

            /* Branch / expand indicators - always transparent background */
            QTreeWidget::branch {{
                background: {_CLR_BG};
            }}
            QTreeWidget::branch:selected {{
                background: {_CLR_BG};
            }}
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {{
                image: url({_chevron_right});
                background: {_CLR_BG};
            }}
            QTreeWidget::branch:has-children:!has-siblings:closed:selected,
            QTreeWidget::branch:closed:has-children:has-siblings:selected {{
                image: url({_chevron_right});
                background: {_CLR_BG};
            }}
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {{
                image: url({_chevron_down});
                background: {_CLR_BG};
            }}
            QTreeWidget::branch:open:has-children:!has-siblings:selected,
            QTreeWidget::branch:open:has-children:has-siblings:selected {{
                image: url({_chevron_down});
                background: {_CLR_BG};
            }}
        """)
        self._proj_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self._proj_tree.customContextMenuRequested.connect(
            self._sidebar_context_menu)
        self._proj_tree.itemDoubleClicked.connect(self._sidebar_load_project)
        self._proj_tree.itemExpanded.connect(self._on_tree_item_expanded)
        lo.addWidget(self._proj_tree, stretch=1)

        # ── Footer (compact action bar) ──
        foot_w = QWidget()
        foot_w.setObjectName("sidebarFoot")
        foot_w.setStyleSheet(f"""
            QWidget#sidebarFoot {{
                background: {_CLR_BG};
                border-top: 1px solid {_CLR_BORDER};
            }}
        """)
        btn_row = QHBoxLayout(foot_w)
        btn_row.setContentsMargins(8, 6, 8, 6)
        btn_row.setSpacing(0)

        _SIDE_BTN_DANGER_CSS = f"""
            QPushButton {{
                background: transparent;
                color: {_CLR_MUTED};
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 8pt;
            }}
            QPushButton:hover {{
                background: rgba(231, 76, 60, 0.15);
                color: {_CLR_RED};
                border-color: rgba(231, 76, 60, 0.35);
            }}
        """

        _SIDE_BTN_DANGER_LEFT_CSS = _SIDE_BTN_DANGER_CSS.replace(
            "border-radius: 6px;", "border-radius: 6px; margin-right: 4px;"
        )
        _SIDE_BTN_DANGER_RIGHT_CSS = _SIDE_BTN_DANGER_CSS.replace(
            "border-radius: 6px;", "border-radius: 6px; margin-left: 4px;"
        )

        btn_remove = QPushButton("✕ Remove")
        btn_remove.setFont(QFont(_FONT, 8))
        btn_remove.setMinimumHeight(26)
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove.setStyleSheet(_SIDE_BTN_DANGER_LEFT_CSS)
        btn_remove.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_remove.clicked.connect(self._sidebar_remove_project)
        btn_row.addWidget(btn_remove, stretch=1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {_CLR_BORDER}; margin: 4px 0;")
        btn_row.addWidget(sep)

        btn_clear_all = QPushButton("⟲ Clear All")
        btn_clear_all.setFont(QFont(_FONT, 8))
        btn_clear_all.setMinimumHeight(26)
        btn_clear_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear_all.setStyleSheet(_SIDE_BTN_DANGER_RIGHT_CSS)
        btn_clear_all.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_clear_all.clicked.connect(self._sidebar_clear_all)
        btn_row.addWidget(btn_clear_all, stretch=1)
        lo.addWidget(foot_w)

        wl.addWidget(self._sidebar_panel)

        # Load saved projects
        self._load_project_history()

        return wrapper

    def _toggle_sidebar(self, checked=None):
        """Toggle sidebar visibility via splitter sizes only (no setVisible)."""
        if checked is None:
            current_width = (
                self._h_splitter.sizes()[0]
                if hasattr(self, "_h_splitter")
                else 200
            )
            showing = current_width == 0
        else:
            showing = bool(checked)

        # Always keep the panel visible — control size via splitter only
        self._sidebar_panel.setVisible(True)

        if hasattr(self, "_h_splitter"):
            if showing:
                self._h_splitter.setSizes([220, 800])
            else:
                self._h_splitter.setSizes([0, 1000])

        if hasattr(self, "_act_nav"):
            self._act_nav.blockSignals(True)
            self._act_nav.setChecked(showing)
            self._act_nav.blockSignals(False)

    def _on_h_splitter_moved(self, pos: int, index: int):
        """Sync menu checkmark when the user manually drags the sidebar splitter."""
        sidebar_width = self._h_splitter.sizes()[0]
        showing = sidebar_width > 0

        # Only sync the menu — never call setVisible here (causes layout snap)
        if hasattr(self, "_act_nav"):
            self._act_nav.blockSignals(True)
            self._act_nav.setChecked(showing)
            self._act_nav.blockSignals(False)

    # --------------------------------------------------------------------------
    #  Import project folder
    # --------------------------------------------------------------------------

    def _import_project(self):
        """Let the user pick a project folder and add it to the navigator."""
        path = QFileDialog.getExistingDirectory(
            self, "Select Project Folder", r"D:\casdev\td5",
            QFileDialog.Option.ShowDirsOnly)
        if not path:
            return
        name = os.path.basename(path)
        self._add_project_to_list(name, mode="Import", status="", path=path)
        self._t(f"\n[IMPORT] Project '{name}' imported from: {path}")
        self._status_msg.setText(f"Imported: {name}")
        QTimer.singleShot(4000, lambda: self._status_msg.setText("Ready"))

    # --------------------------------------------------------------------------
    #  Sidebar: project history persistence
    # --------------------------------------------------------------------------

    def _load_project_history(self):
        """Load project history from QSettings."""
        settings = QSettings(_COMPANY, _APP_NAME)
        projects = settings.value("project_history", [])
        if projects:
            for entry in projects:
                self._add_project_to_list(
                    entry.get("name", ""),
                    entry.get("mode", ""),
                    entry.get("status", ""),
                    entry.get("path", ""),
                    save=False,
                )
            # Re-save so resolved paths are persisted for next launch
            self._save_project_history()

    def _save_project_history(self):
        """Persist project history to QSettings."""
        settings = QSettings(_COMPANY, _APP_NAME)
        projects = []
        root = self._proj_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                projects.append(data)
        settings.setValue("project_history", projects)

    def _add_project_to_list(self, name: str, mode: str = "",
                              status: str = "pending", path: str = "",
                              save: bool = True):
        """Add a project entry to the tree. Populates subdirs from disk."""
        if not name:
            return

        # Avoid duplicates — update status if already exists
        root = self._proj_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get("name") == name:
                data["status"] = status
                item.setData(0, Qt.ItemDataRole.UserRole, data)
                item.setText(0, name)
                item.setToolTip(0, f"Project: {name}\nMode: {mode}\nStatus: {status}")
                if save:
                    self._save_project_history()
                return

        proj_item = QTreeWidgetItem([name])
        proj_item.setIcon(0, self._folder_icon)
        proj_item.setData(0, Qt.ItemDataRole.UserRole, {
            "name": name, "mode": mode, "status": status, "path": path,
        })
        proj_item.setToolTip(0, f"Project: {name}\nMode: {mode}\nStatus: {status}")

        # Populate subdirectories from disk
        proj_dir = path if path else ""
        if not proj_dir:
            # 1) Try create_case_path (the real project resolver)
            try:
                from .path_utils import create_case_path
                resolved = create_case_path(name)
                if resolved and os.path.isdir(resolved):
                    proj_dir = resolved
            except Exception as exc:
                logger.debug("create_case_path failed for %r: %s", name, exc)
        if not proj_dir:
            # 2) Fallback: try known root directories
            for candidate in [
                os.path.join(r"d:\casdev\td5", name),
                os.path.join(r"d:\casdev\td5\BM\bench_results", name),
            ]:
                if os.path.isdir(candidate):
                    proj_dir = candidate
                    break

        # Store resolved path back into item data so expand works later
        if proj_dir:
            d = proj_item.data(0, Qt.ItemDataRole.UserRole)
            d["path"] = proj_dir
            proj_item.setData(0, Qt.ItemDataRole.UserRole, d)

        if proj_dir and os.path.isdir(proj_dir):
            # Add dummy child if folder has ANY content (files or subdirs)
            try:
                _has_content = len(os.listdir(proj_dir)) > 0
            except Exception as exc:
                logger.debug("Cannot list dir %r: %s", proj_dir, exc)
                _has_content = False
            if _has_content:
                dummy = QTreeWidgetItem(["..."])
                dummy.setData(0, Qt.ItemDataRole.UserRole, {"type": "_placeholder"})
                proj_item.addChild(dummy)

        self._proj_tree.insertTopLevelItem(0, proj_item)
        self._proj_tree.setCurrentItem(proj_item)
        if save:
            self._save_project_history()

    def _populate_tree(self, parent: QTreeWidgetItem, dir_path: str):
        """Add immediate children of dir_path to parent (lazy — one level only)."""
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return

        dirs_first = []
        files_second = []
        for entry in entries:
            full = os.path.join(dir_path, entry)
            if os.path.isdir(full):
                dirs_first.append((entry, full))
            else:
                files_second.append((entry, full))

        for entry_name, full_path in dirs_first:
            child = QTreeWidgetItem([entry_name])
            child.setIcon(0, self._folder_icon)
            child.setData(0, Qt.ItemDataRole.UserRole, {"type": "dir", "path": full_path, "loaded": False})
            child.setToolTip(0, full_path)
            parent.addChild(child)
            # Add a dummy child if folder has ANY content (files or subdirs)
            try:
                _has_content = len(os.listdir(full_path)) > 0
            except Exception as exc:
                logger.debug("Cannot list dir %r: %s", full_path, exc)
                _has_content = False
            if _has_content:
                dummy = QTreeWidgetItem(["..."])
                dummy.setData(0, Qt.ItemDataRole.UserRole, {"type": "_placeholder"})
                child.addChild(dummy)

        for entry_name, full_path in files_second:
            child = QTreeWidgetItem([entry_name])
            child.setIcon(0, self._file_icon)
            child.setData(0, Qt.ItemDataRole.UserRole, {"type": "file", "path": full_path})
            child.setToolTip(0, full_path)
            parent.addChild(child)

    def _on_tree_item_expanded(self, item: QTreeWidgetItem):
        """Lazy-load children when a node is expanded for the first time."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        # Top-level project item
        if "name" in data and not data.get("loaded", False):
            proj_dir = data.get("path", "")
            name = data.get("name", "")
            if not proj_dir:
                try:
                    from .path_utils import create_case_path
                    resolved = create_case_path(name)
                    if resolved and os.path.isdir(resolved):
                        proj_dir = resolved
                except Exception as exc:
                    logger.debug("create_case_path failed for %r: %s", name, exc)
            if not proj_dir:
                for candidate in [
                    os.path.join(r"d:\casdev\td5", name),
                    os.path.join(r"d:\casdev\td5\BM\bench_results", name),
                ]:
                    if os.path.isdir(candidate):
                        proj_dir = candidate
                        break
            if proj_dir and os.path.isdir(proj_dir):
                item.takeChildren()  # remove placeholder
                self._populate_tree(item, proj_dir)
                data["loaded"] = True
                data["path"] = proj_dir
                item.setData(0, Qt.ItemDataRole.UserRole, data)
            return

        # Sub-directory item
        if data.get("type") == "dir" and not data.get("loaded", False):
            item.takeChildren()  # remove placeholder
            self._populate_tree(item, data["path"])
            data["loaded"] = True
            item.setData(0, Qt.ItemDataRole.UserRole, data)

    def _sidebar_load_project(self, item: QTreeWidgetItem):
        """Double-click a project to load its name into the input field."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if "name" in data:
            # Top-level project item — show wait cursor immediately
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self._inp.setText(data.get("name", ""))
            self._tabs.setCurrentIndex(0)
            self._status_msg.setText("Ready")
        elif data.get("type") == "file":
            # Open file with OS default
            path = data.get("path", "")
            if path and os.path.isfile(path):
                os.startfile(path)

    def _sidebar_remove_project(self):
        """Remove selected top-level project from the tree."""
        item = self._proj_tree.currentItem()
        if not item:
            return
        # Find top-level parent
        while item.parent():
            item = item.parent()
        idx = self._proj_tree.indexOfTopLevelItem(item)
        if idx >= 0:
            self._proj_tree.takeTopLevelItem(idx)
            self._save_project_history()

    def _sidebar_clear_all(self):
        """Clear all projects from the tree."""
        if self._proj_tree.topLevelItemCount() == 0:
            return
        reply = QMessageBox.question(
            self, "Clear History",
            "Remove all projects from the navigator?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._proj_tree.clear()
            self._save_project_history()

    def _sidebar_context_menu(self, pos):
        """Right-click context menu on sidebar items."""
        item = self._proj_tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {_CLR_PANEL};
                color: {_CLR_TEXT};
                border: 1px solid {_CLR_BORDER};
                border-radius: 8px;
                padding: 4px 0;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 16px;
                border-radius: 4px;
                margin: 1px 4px;
            }}
            QMenu::item:selected {{
                background: rgba(52, 152, 219, 0.22);
                color: white;
            }}
            QMenu::separator {{
                height: 1px;
                background: {_CLR_BORDER};
                margin: 4px 8px;
            }}
        """)

        if data and "name" in data:
            act_load = menu.addAction("Load Project")
            act_refresh = menu.addAction("Refresh Tree")
            menu.addSeparator()
            act_rm = menu.addAction("Remove")
            chosen = menu.exec(self._proj_tree.mapToGlobal(pos))
            if chosen == act_load:
                self._sidebar_load_project(item)
            elif chosen == act_refresh:
                self._sidebar_refresh_project(item)
            elif chosen == act_rm:
                idx = self._proj_tree.indexOfTopLevelItem(item)
                if idx >= 0:
                    self._proj_tree.takeTopLevelItem(idx)
                    self._save_project_history()
        elif data and data.get("type") == "file":
            act_open = menu.addAction("Open File")
            chosen = menu.exec(self._proj_tree.mapToGlobal(pos))
            if chosen == act_open:
                path = data.get("path", "")
                if path and os.path.isfile(path):
                    os.startfile(path)
        elif data and data.get("type") == "dir":
            act_open = menu.addAction("Open in Explorer")
            chosen = menu.exec(self._proj_tree.mapToGlobal(pos))
            if chosen == act_open:
                path = data.get("path", "")
                if path and os.path.isdir(path):
                    os.startfile(path)

    def _sidebar_refresh_project(self, item: QTreeWidgetItem):
        """Re-scan subdirectories for a project item."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or "name" not in data:
            return
        # Remove old children
        while item.childCount() > 0:
            item.removeChild(item.child(0))
        # Re-populate
        proj_dir = data.get("path", "")
        name = data.get("name", "")
        if not proj_dir:
            try:
                from .path_utils import create_case_path
                resolved = create_case_path(name)
                if resolved and os.path.isdir(resolved):
                    proj_dir = resolved
            except Exception as exc:
                logger.debug("create_case_path failed for %r: %s", name, exc)
        if not proj_dir:
            for candidate in [
                os.path.join(r"d:\casdev\td5", name),
                os.path.join(r"d:\casdev\td5\BM\bench_results", name),
            ]:
                if os.path.isdir(candidate):
                    proj_dir = candidate
                    break
        if proj_dir and os.path.isdir(proj_dir):
            self._populate_tree(item, proj_dir)
            data["loaded"] = False  # reset so expand re-loads children lazily

    # --------------------------------------------------------------------------
    #  About dialog
    # --------------------------------------------------------------------------

    def _show_about(self):
        QMessageBox.about(
            self,
            f"About {_APP_NAME}",
            f"<h2 style='color:{_CLR_ACCENT};'>{_APP_NAME}</h2>"
            f"<p><b>{_APP_FULL}</b></p>"
            f"<p>Version {_APP_VERSION}</p>"
            f"<hr>"
            f"<p>TD5 Instrumentation & DEM Simulation Tool</p>"
            f"<p style='color:{_CLR_MUTED};'>"
            f"© {_COMPANY}. All rights reserved.</p>"
        )

    def _show_contact_support(self):
        ContactSupportDialog(self).exec()

    # --------------------------------------------------------------------------
    #  Edit helpers
    # --------------------------------------------------------------------------

    def _edit_action(self, action: str):
        """Forward edit actions to the currently focused widget."""
        w = QApplication.focusWidget()
        if w is None:
            return
        methods = {
            "undo":      "undo",
            "redo":      "redo",
            "cut":       "cut",
            "copy":      "copy",
            "paste":     "paste",
            "delete":    "del_",           # mapped below
            "selectAll": "selectAll",
        }
        if action == "delete":
            if hasattr(w, "textCursor"):
                cur = w.textCursor()
                cur.removeSelectedText()
            elif hasattr(w, "del_"):
                w.del_()
        else:
            method = methods.get(action)
            if method and hasattr(w, method):
                getattr(w, method)()

    def _show_find_replace(self):
        """Simple Find/Replace dialog for the terminal widget."""

        dlg = QDialog(self)
        dlg.setWindowTitle("Find / Replace")
        dlg.setMinimumWidth(400)
        lo = QVBoxLayout(dlg)
        lo.setSpacing(10)
        lo.setContentsMargins(16, 16, 16, 16)

        # Find row
        fr = QHBoxLayout()
        lbl_f = QLabel("Find:")
        lbl_f.setMinimumWidth(60)
        fr.addWidget(lbl_f)
        inp_find = QLineEdit()
        inp_find.setMinimumHeight(32)
        inp_find.setStyleSheet(_INPUT_CSS)
        fr.addWidget(inp_find, stretch=1)
        lo.addLayout(fr)

        # Replace row
        rr = QHBoxLayout()
        lbl_r = QLabel("Replace:")
        lbl_r.setMinimumWidth(60)
        rr.addWidget(lbl_r)
        inp_repl = QLineEdit()
        inp_repl.setMinimumHeight(32)
        inp_repl.setStyleSheet(_INPUT_CSS)
        rr.addWidget(inp_repl, stretch=1)
        lo.addLayout(rr)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_find = QPushButton("Find Next")
        btn_find.setMinimumHeight(32)
        btn_find.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_find.setStyleSheet(f"""
            QPushButton {{
                background: {_CLR_ACCENT}; color: white;
                border: none; border-radius: 6px; padding: 0 16px;
            }}
            QPushButton:hover {{ background: #2980B9; }}
        """)
        btn_row.addWidget(btn_find)

        btn_replace = QPushButton("Replace")
        btn_replace.setMinimumHeight(32)
        btn_replace.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_replace.setStyleSheet(f"""
            QPushButton {{
                background: {_CLR_SURF}; color: {_CLR_TEXT};
                border: 1px solid {_CLR_BORDER}; border-radius: 6px;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background: #415B76; }}
        """)
        btn_row.addWidget(btn_replace)

        btn_all = QPushButton("Replace All")
        btn_all.setMinimumHeight(32)
        btn_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_all.setStyleSheet(f"""
            QPushButton {{
                background: {_CLR_SURF}; color: {_CLR_TEXT};
                border: 1px solid {_CLR_BORDER}; border-radius: 6px;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background: #415B76; }}
        """)
        btn_row.addWidget(btn_all)
        lo.addLayout(btn_row)

        def _find_next():
            txt = inp_find.text()
            if not txt:
                return
            te = self._term_widget
            if not te.find(txt):
                # wrap: go to start, try again
                cur = te.textCursor()
                cur.movePosition(QTextCursor.MoveOperation.Start)
                te.setTextCursor(cur)
                te.find(txt)

        def _replace_one():
            te = self._term_widget
            cur = te.textCursor()
            if cur.hasSelection() and cur.selectedText() == inp_find.text():
                cur.insertText(inp_repl.text())
            _find_next()

        def _replace_all():
            txt = inp_find.text()
            repl = inp_repl.text()
            if not txt:
                return
            te = self._term_widget
            content = te.toPlainText()
            count = content.count(txt)
            te.setPlainText(content.replace(txt, repl))
            self._status_msg.setText(f"Replaced {count} occurrence(s)")

        btn_find.clicked.connect(_find_next)
        btn_replace.clicked.connect(_replace_one)
        btn_all.clicked.connect(_replace_all)

        dlg.show()

    # --------------------------------------------------------------------------
    #  Tab 1: Instrumentation
    # --------------------------------------------------------------------------

    def _tab_instrument(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)

        # --- Top panel: controls (in a scroll area so splitter can shrink it) ---
        top_inner = QWidget()
        tl = QVBoxLayout(top_inner)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)

        src = self._grp_source()
        src.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        tl.addWidget(src)

        sim = self._grp_sim_options()
        sim.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        tl.addWidget(sim)

        top = QScrollArea()
        top.setWidget(top_inner)
        top.setWidgetResizable(True)
        top.setFrameShape(QFrame.Shape.NoFrame)
        top.setMinimumHeight(60)
        top.setStyleSheet(f"""
            QScrollArea {{ background: {_CLR_BG}; border: none; }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.15); border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.3); }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent; height: 0; border: none;
            }}
            QScrollBar:horizontal {{ height: 0; }}
        """)
        top_inner.setStyleSheet(f"background: {_CLR_BG};")

        # --- Bottom panel: terminal ---
        bot = QWidget()
        bl = QVBoxLayout(bot)
        bl.setContentsMargins(0, 4, 0, 0)
        bl.setSpacing(2)

        term_hdr = QHBoxLayout()
        term_hdr.setContentsMargins(0, 0, 0, 0)
        lbl_term = QLabel("Terminal Output")
        lbl_term.setFont(QFont(_FONT, 10, QFont.Weight.Bold))
        lbl_term.setStyleSheet(f"color:{_CLR_ACCENT}; padding:2px 0;")
        term_hdr.addWidget(lbl_term)
        term_hdr.addStretch()

        _ICONS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
        btn_clr = QPushButton("")
        btn_clr.setObjectName("btnClear")
        btn_clr.setToolTip("Clear terminal output")
        btn_clr.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clr.setFixedSize(28, 28)
        btn_clr.setIcon(QIcon(os.path.join(_ICONS_DIR, "clear.png")))
        btn_clr.setIconSize(QSize(20, 20))
        btn_clr.setFlat(True)
        btn_clr.setStyleSheet(f"""
            QPushButton#btnClear {{
                background: transparent;
                border: none;
                padding: 3px;
                border-radius: 6px;
            }}
            QPushButton#btnClear:hover {{
                background: {_CLR_SURF};
            }}
            QPushButton#btnClear:pressed {{
                background: {_CLR_BORDER};
            }}
        """)
        btn_clr.clicked.connect(lambda: self._term_widget.clear())
        term_hdr.addWidget(btn_clr)

        bl.addLayout(term_hdr)

        self._term_widget = QTextEdit()
        self._term_widget.setReadOnly(True)
        self._term_widget.setFont(QFont(_FONT_MONO, 10))
        self._term_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._term_widget.setStyleSheet(f"""
            QTextEdit {{
                background: #0A0E14; color: #00E676;
                border: 1px solid {_CLR_BORDER}; border-radius: 8px;
                padding: 12px;
                selection-background-color: {_CLR_ACCENT};
            }}
        """)
        bl.addWidget(self._term_widget, stretch=1)

        # --- Splitter: drag handle between controls and terminal ---
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {_CLR_BORDER};
                border-radius: 3px;
                margin: 2px 40px;
            }}
            QSplitter::handle:hover {{
                background: {_CLR_ACCENT};
            }}
        """)
        splitter.addWidget(top)
        splitter.addWidget(bot)
        # Initial ratio: ~40% controls, ~60% terminal
        splitter.setStretchFactor(0, 0)   # top: don't stretch
        splitter.setStretchFactor(1, 1)   # bottom: takes extra space
        splitter.setSizes([400, 500])

        outer.addWidget(splitter)

        return page

    # --------------------------------------------------------------------------
    #  Tab 2: Simulation Results
    # --------------------------------------------------------------------------

    def _tab_results(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background: {_CLR_BG};")
        lay = QVBoxLayout(page)
        lay.setSpacing(10)
        lay.setContentsMargins(10, 10, 10, 10)

        self._lbl_no_results = QLabel(
            "No simulation results yet.\n"
            "Enable DEM Simulation and run the pipeline to see results here."
        )
        self._lbl_no_results.setFont(QFont(_FONT, 12))
        self._lbl_no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_no_results.setStyleSheet(f"color:{_CLR_MUTED}; padding:40px;")
        lay.addWidget(self._lbl_no_results)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: {_CLR_BG}; border: none; }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.15); border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.3); }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent; height: 0; border: none;
            }}
            QScrollBar:horizontal {{ height: 0; }}
        """)

        self._res_body = QWidget()
        self._res_body.setStyleSheet(f"background: {_CLR_BG};")
        rc = QVBoxLayout(self._res_body)
        rc.setSpacing(10)

        # extracted calibration values
        g1 = QGroupBox("Extracted Calibration Values")
        g1.setStyleSheet(_GROUP_CSS)
        gr = QGridLayout()
        gr.setContentsMargins(12, 26, 12, 12)
        gr.setHorizontalSpacing(26)
        gr.setVerticalSpacing(8)
        self._cfg_labels: dict = {}
        for i, (title, key) in enumerate([
            ("NrFmy",       "nr_fmy"),
            ("NrEve",       "nr_eve"),
            ("NrFrfDataTot","nr_frf_data_tot"),
            ("NrBlockFrf",  "nr_block_frf"),
            ("NrFrfPre",    "nr_frf_pre"),
            ("NrLamp",      "nr_lamp"),
            ("EveAsyn",     "nr_clc_fmy_eve_asyn"),
            ("Post",        "nr_clc_fmy_post"),
        ]):
            r, c = i // 4, (i % 4) * 2
            lb = QLabel(title + ":")
            lb.setFont(QFont(_FONT, 9, QFont.Weight.Bold))
            lb.setStyleSheet(f"color:{_CLR_MUTED};")
            gr.addWidget(lb, r, c)
            vl = QLabel("--")
            vl.setFont(QFont(_FONT_MONO, 11, QFont.Weight.Bold))
            vl.setStyleSheet(f"color:{_CLR_ACCENT};")
            gr.addWidget(vl, r, c + 1)
            self._cfg_labels[key] = vl
        g1.setLayout(gr)
        rc.addWidget(g1)

        # WCS grid
        g2 = QGroupBox("WCS Grid -- Simulated Runtime (us)")
        g2.setStyleSheet(_GROUP_CSS)
        g2l = QVBoxLayout()
        g2l.setContentsMargins(12, 26, 12, 12)
        self._tbl = QTableWidget(3, 6)
        self._tbl.setHorizontalHeaderLabels(
            ["(20,10)", "(10,10)", "(10,5)", "(5,5)", "(5,4)", "(5,3)"])
        self._tbl.setVerticalHeaderLabels(["S1", "S2", "S3"])
        self._tbl.setFont(QFont(_FONT_MONO, 11))
        self._tbl.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self._tbl.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Fixed)
        self._tbl.setMinimumHeight(100)
        self._tbl.setMaximumHeight(200)
        self._tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tbl.setStyleSheet(f"""
            QTableWidget {{
                background:{_CLR_PANEL}; color:{_CLR_TEXT};
                gridline-color:{_CLR_BORDER};
                border:1px solid {_CLR_BORDER}; border-radius:6px;
            }}
            QHeaderView::section {{
                background:{_CLR_SURF}; color:{_CLR_ACCENT};
                padding:5px; border:1px solid {_CLR_BORDER}; font-weight:bold;
            }}
        """)
        g2l.addWidget(self._tbl)
        g2.setLayout(g2l)
        rc.addWidget(g2)

        # analysis stats
        g3 = QGroupBox("Analysis Summary")
        g3.setStyleSheet(_GROUP_CSS)
        sg = QGridLayout()
        sg.setContentsMargins(12, 26, 12, 12)
        sg.setHorizontalSpacing(26)
        sg.setVerticalSpacing(8)
        self._stat_labels: dict = {}
        for i, (title, key, unit) in enumerate([
            ("RMSE Total",   "rmse_total",   "us"),
            ("S1 RMSE",      "rmse_s1",      "us"),
            ("S2 RMSE",      "rmse_s2",      "us"),
            ("S3 RMSE",      "rmse_s3",      "us"),
            ("MC Peak",      "mc_peak",      "us"),
            ("MC Mean",      "mc_mean",      "us"),
            ("MC P99",       "mc_p99",       "us"),
            ("PTU Variants", "num_variants", ""),
        ]):
            r, c = i // 4, (i % 4) * 2
            lb = QLabel(title + ":")
            lb.setFont(QFont(_FONT, 9, QFont.Weight.Bold))
            lb.setStyleSheet(f"color:{_CLR_MUTED};")
            sg.addWidget(lb, r, c)
            vl = QLabel("--")
            vl.setFont(QFont(_FONT_MONO, 11, QFont.Weight.Bold))
            vl.setStyleSheet(f"color:{_CLR_ACCENT};")
            sg.addWidget(vl, r, c + 1)
            self._stat_labels[key] = (vl, unit)
        g3.setLayout(sg)
        rc.addWidget(g3)

        # report path
        g4 = QGroupBox("Generated Report")
        g4.setStyleSheet(_GROUP_CSS)
        g4l = QHBoxLayout()
        g4l.setContentsMargins(12, 26, 12, 12)
        self._lbl_report = QLabel("No report generated yet.")
        self._lbl_report.setFont(QFont(_FONT, 9))
        self._lbl_report.setStyleSheet(f"color:{_CLR_MUTED};")
        self._lbl_report.setWordWrap(True)
        g4l.addWidget(self._lbl_report, stretch=1)
        self._btn_open = QPushButton("Open Report")
        self._btn_open.setFont(QFont(_FONT, 10))
        self._btn_open.setMinimumHeight(36)
        self._btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open.setEnabled(False)
        self._btn_open.setStyleSheet(f"""
            QPushButton {{
                background:{_CLR_ACCENT}; color:white;
                border:none; border-radius:8px; padding:8px 18px;
            }}
            QPushButton:hover    {{ background:#2980B9; }}
            QPushButton:disabled {{ background:#566573; }}
        """)
        self._btn_open.clicked.connect(self._open_report)
        g4l.addWidget(self._btn_open)
        g4.setLayout(g4l)
        rc.addWidget(g4)

        # warnings
        self._grp_warn = QGroupBox("Warnings")
        warn_css = _GROUP_CSS.replace(_CLR_TEXT, _CLR_YELLOW)
        self._grp_warn.setStyleSheet(warn_css)
        wl = QVBoxLayout()
        wl.setContentsMargins(12, 26, 12, 12)
        self._lbl_warn = QLabel("")
        self._lbl_warn.setFont(QFont(_FONT, 9))
        self._lbl_warn.setStyleSheet(f"color:{_CLR_YELLOW};")
        self._lbl_warn.setWordWrap(True)
        wl.addWidget(self._lbl_warn)
        self._grp_warn.setLayout(wl)
        self._grp_warn.setVisible(False)
        rc.addWidget(self._grp_warn)

        rc.addStretch()
        scroll.setWidget(self._res_body)
        self._res_body.setVisible(False)
        lay.addWidget(scroll)
        return page

    # --------------------------------------------------------------------------
    #  Tab 3: Train Simulator
    # --------------------------------------------------------------------------

    def _tab_bench_train(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background: {_CLR_BG};")
        lay = QVBoxLayout(page)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 24, 24, 24)

        # --- Header ---
        hdr = QLabel("Train Simulator from Bench Data")
        hdr.setFont(QFont(_FONT, 16, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {_CLR_ACCENT};")
        lay.addWidget(hdr)

        desc = QLabel(
            "Import real bench measurement results to calibrate the DEM simulator.\n"
            "The tool reads <b>RuntimeMeasureReduction.xlsx</b> and extracts "
            "calibration parameters from <b>icsp_dem_cnf.c</b> automatically."
        )
        desc.setFont(QFont(_FONT, 10))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {_CLR_MUTED}; padding-bottom: 8px;")
        lay.addWidget(desc)

        # --- Import group ---
        g = QGroupBox("Bench Import")
        g.setStyleSheet(_GROUP_CSS)
        gl = QVBoxLayout()
        gl.setContentsMargins(12, 26, 12, 12)
        gl.setSpacing(12)

        btn_import = QPushButton("Import Bench Data && Train")
        btn_import.setFont(QFont(_FONT, 11, QFont.Weight.Bold))
        btn_import.setMinimumHeight(44)
        btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_import.setToolTip(
            "Import real bench results to train the simulator.\n"
            "Enter the project name from the centralized folder —\n"
            "the tool reads the Excel and C sources automatically.")
        btn_import.setStyleSheet(f"""
            QPushButton {{
                background: {_CLR_ACCENT}; color: white;
                border: none; border-radius: 8px;
                padding: 0 24px; font-size: 11pt;
            }}
            QPushButton:hover {{ background: #2980B9; }}
            QPushButton:pressed {{ background: #2471A3; }}
        """)
        btn_import.clicked.connect(self._open_bench_dialog)
        gl.addWidget(btn_import)

        # --- Store path ---
        store_row = QHBoxLayout()
        store_row.setSpacing(8)
        lbl_store = QLabel("Store path:")
        lbl_store.setFont(QFont(_FONT, 9))
        lbl_store.setStyleSheet(f"color: {_CLR_MUTED};")
        store_row.addWidget(lbl_store)

        btn_store = QPushButton("Copy Store to Local…")
        btn_store.setFont(QFont(_FONT, 9))
        btn_store.setMinimumHeight(30)
        btn_store.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_store.setStyleSheet(f"""
            QPushButton {{
                background: {_CLR_SURF}; color: {_CLR_TEXT};
                border: 1px solid {_CLR_BORDER}; border-radius: 6px;
                padding: 0 14px;
            }}
            QPushButton:hover {{ background: #415B76; }}
        """)
        btn_store.clicked.connect(self._copy_store_db)
        store_row.addWidget(btn_store)
        store_row.addStretch()
        gl.addLayout(store_row)

        g.setLayout(gl)
        lay.addWidget(g)

        lay.addStretch()
        return page

    # --------------------------------------------------------------------------
    #  Group: Project Source
    # --------------------------------------------------------------------------

    def _grp_source(self) -> QGroupBox:
        from PyQt6.QtWidgets import QListView

        g = QGroupBox("Project Source")
        g.setStyleSheet(_GROUP_CSS)
        lo = QVBoxLayout()
        lo.setContentsMargins(12, 26, 12, 12)
        lo.setSpacing(15)

        # ---- Row 1: radio buttons ----
        rr = QHBoxLayout()
        self._src_grp = QButtonGroup()
        self._rad_sf = QRadioButton("System File")
        self._rad_sf.setFont(QFont(_FONT, 10))
        self._rad_sf.setChecked(True)
        self._rad_sf.toggled.connect(self._src_changed)
        self._src_grp.addButton(self._rad_sf)
        rr.addWidget(self._rad_sf)
        self._rad_mks = QRadioButton("MKS")
        self._rad_mks.setFont(QFont(_FONT, 10))
        self._rad_mks.toggled.connect(self._src_changed)
        self._src_grp.addButton(self._rad_mks)
        rr.addWidget(self._rad_mks)
        rr.addStretch()
        lo.addLayout(rr)

        # ---- Row 2: Project Name  (label + input + browse) ----
        proj_row = QHBoxLayout()
        proj_row.setSpacing(8)
        self._lbl_input = QLabel("Project Name:")
        self._lbl_input.setFont(QFont(_FONT, 10))
        self._lbl_input.setMinimumWidth(100)
        self._lbl_input.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        proj_row.addWidget(self._lbl_input)

        self._inp = QLineEdit()
        self._inp.setFont(QFont(_FONT, 11))
        self._inp.setPlaceholderText("e.g.  PROJ3_0U0_P16_624")
        self._inp.setMinimumHeight(38)
        self._inp.setStyleSheet(_INPUT_CSS)
        # self._inp.setToolTip(
        #     "Enter the project name or browse with the folder button")
        # Warning icon inside Project Name field, right side
        self._td5_warn_action = self._inp.addAction(
            QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning),
            QLineEdit.ActionPosition.TrailingPosition
        )
        self._td5_warn_action.setToolTip(
            "Only TD5 project structures are supported by this tool."
        )
        self._td5_warn_action.setVisible(False)

        proj_row.addWidget(self._inp, stretch=1)

        btn_b = QPushButton("...")
        btn_b.setFont(QFont(_FONT, 13))
        btn_b.setMinimumSize(44, 38)
        btn_b.setMaximumWidth(50)
        btn_b.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_b.setToolTip("Browse for project folder")
        btn_b.setStyleSheet(f"""
            QPushButton {{
                background:{_CLR_SURF}; color:white;
                border:1px solid {_CLR_BORDER}; border-radius:6px;
            }}
            QPushButton:hover {{ background:#415B76; border-color:{_CLR_ACCENT}; }}
        """)
        btn_b.clicked.connect(self._browse)
        proj_row.addWidget(btn_b)

        # self._lbl_td5_warn_text = QLabel("TD5 only")
        # self._lbl_td5_warn_text.setFont(QFont(_FONT, 8, QFont.Weight.Bold))
        # self._lbl_td5_warn_text.setStyleSheet(
        #     f"color:{_CLR_YELLOW}; background: transparent;")
        # self._lbl_td5_warn_text.setVisible(False)
        # proj_row.addWidget(self._lbl_td5_warn_text)

        # self._lbl_td5_warn = QLabel("⚠")
        # self._lbl_td5_warn.setFont(QFont(_FONT, 14, QFont.Weight.Bold))
        # self._lbl_td5_warn.setFixedWidth(24)
        # self._lbl_td5_warn.setAlignment(
        #     Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        # self._lbl_td5_warn.setStyleSheet(
        #     f"color:{_CLR_YELLOW}; background: transparent;")
        # self._lbl_td5_warn.setToolTip(
        #     "Only TD5 project structures are supported by this tool.")
        # self._lbl_td5_warn.setVisible(False)
        # proj_row.addWidget(self._lbl_td5_warn)

        lo.addLayout(proj_row)

        _ICONS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
        # ---- Row 3: Target + Build Type (side by side) ----
        _CMB_CSS_MODERN = f"""
        QComboBox {{
            background: {_CLR_SURF};
            border: 2px solid {_CLR_BORDER};
            border-radius: 8px;
            padding: 4px 32px 8px 12px;
            color: {_CLR_TEXT};
            selection-background-color: transparent;
        }}
        QComboBox:hover {{ border-color: {_CLR_BORDER}; }}
        QComboBox:focus, QComboBox:pressed {{ border-color: {_CLR_ACCENT}; }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 28px;
            border-left: none;
            margin: 0px 6px 0px 0px;
        }}
        QComboBox::down-arrow {{
            image: url({os.path.join(_ICONS_DIR, 'chevron_down.png').replace(os.sep, '/')});
            width: 12px; height: 12px;
        }}
        QComboBox QAbstractItemView {{
            background: #ffffff;
            outline: none;
            border: 2px solid #2F7BFF;
            border-radius: 8px;
            padding: 4px;
        }}
        QComboBox QAbstractItemView::item {{
            min-height: 36px; padding: 8px 12px; color: #1C1C1C;
        }}
        QComboBox QAbstractItemView::item:hover {{ background: #EEF5FF; }}
        QComboBox QAbstractItemView::item:selected {{
            background: #E0EDFF; color: #0E4ECB;
        }}
        """

        target_row = QHBoxLayout()
        target_row.setSpacing(4)  # spacing mai mic pentru a apropia label-ul de dropdown
        lbl_tgt = QLabel("Target:")
        lbl_tgt.setFont(QFont(_FONT, 10))
        lbl_tgt.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        target_row.addWidget(lbl_tgt)
        self._cmb_target = QComboBox()
        self._cmb_target.setFont(QFont(_FONT, 10))
        self._cmb_target.setMinimumHeight(40)
        self._cmb_target.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._cmb_target.addItem("FS_PROJ2_0U0")
        self._cmb_target.setToolTip(
            "Visible targets auto-detected from .tdxml files.\n"
            "Each target may have different build types.")
        self._cmb_target.setView(QListView())
        self._cmb_target.view().setSpacing(2)
        self._cmb_target.setStyleSheet(_CMB_CSS_MODERN)
        self._cmb_target.currentIndexChanged.connect(self._on_target_changed)
        target_row.addWidget(self._cmb_target)

        # Target vertical: orizontal sus, status jos
        target_col = QVBoxLayout()
        target_col.setSpacing(0)
        target_col.addLayout(target_row)
        self._lbl_tgt_status = QLabel("")
        self._lbl_tgt_status.setFont(QFont(_FONT, 8))
        self._lbl_tgt_status.setStyleSheet(f"color: {_CLR_MUTED}; margin-left: 45px; margin-top: 6px;")
        target_col.addWidget(self._lbl_tgt_status, alignment=Qt.AlignmentFlag.AlignLeft)

        # In combo_row, add target_col, not the other way around!
        combo_row = QHBoxLayout()
        combo_row.setSpacing(16)
        combo_row.addLayout(target_col)

#####################################################################

        # Build Type (label + combo horizontally, status below)
        buildtype_row = QHBoxLayout()
        buildtype_row.setSpacing(4)
        lbl_bt = QLabel("Build Type:")
        lbl_bt.setFont(QFont(_FONT, 10))
        lbl_bt.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        buildtype_row.addWidget(lbl_bt)
        self._cmb_buildtype = QComboBox()
        self._cmb_buildtype.setFont(QFont(_FONT, 10))
        self._cmb_buildtype.setMinimumHeight(40)
        self._cmb_buildtype.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._cmb_buildtype.addItem("NORMAL")
        self._cmb_buildtype.setToolTip(
            "Build types for the selected target.\n"
            "Auto-detected from .tdxml files.")
        self._cmb_buildtype.setView(QListView())
        self._cmb_buildtype.view().setSpacing(2)
        self._cmb_buildtype.setStyleSheet(_CMB_CSS_MODERN)
        buildtype_row.addWidget(self._cmb_buildtype)

        buildtype_col = QVBoxLayout()
        buildtype_col.setSpacing(0)
        buildtype_col.addLayout(buildtype_row)
        self._lbl_bt_status = QLabel("")
        self._lbl_bt_status.setFont(QFont(_FONT, 8))
        self._lbl_bt_status.setStyleSheet(f"color: {_CLR_MUTED}; margin-left: 68px; margin-top: 6px;")
        buildtype_col.addWidget(self._lbl_bt_status, alignment=Qt.AlignmentFlag.AlignLeft)

        combo_row.addLayout(buildtype_col)

        lo.addLayout(combo_row)

        g.setLayout(lo)

        # Internal storage: target -> buildtypes mapping
        self._target_buildtypes: Dict[str, List[str]] = {}
        self._inp.textChanged.connect(self._on_inp_text_changed)
        self._inp.textChanged.connect(self._restore_ready)

        return g

    # --------------------------------------------------------------------------
    #  Group: DEM Simulation options
    # --------------------------------------------------------------------------

    def _grp_sim_options(self) -> QGroupBox:
        g = QGroupBox("DEM Simulation")
        g.setStyleSheet(_GROUP_CSS)
        lo = QVBoxLayout()
        lo.setContentsMargins(12, 26, 12, 12)
        lo.setSpacing(6)

        r1 = QHBoxLayout()

        self._chk_sim = QCheckBox("Enable DEM Simulation after build")
        self._chk_sim.setFont(QFont(_FONT, 10))
        self._chk_sim.setChecked(False)
        self._chk_sim.setStyleSheet(_CHECK_CSS)
        self._chk_sim.setToolTip(
            "OFF: instrument & build only\n"
            "ON:  also extract, simulate, and generate report")
        self._chk_sim.toggled.connect(self._on_sim_toggle)
        r1.addWidget(self._chk_sim)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color:{_CLR_BORDER};")
        r1.addWidget(sep)

        lbl_thr = QLabel("Threshold:")
        lbl_thr.setFont(QFont(_FONT, 9))
        lbl_thr.setStyleSheet(f"color:{_CLR_MUTED};")
        r1.addWidget(lbl_thr)

        self._inp_threshold = QSpinBox()
        self._inp_threshold.setFont(QFont(_FONT_MONO, 9))
        self._inp_threshold.setMinimumWidth(70)
        self._inp_threshold.setMaximumWidth(100)
        self._inp_threshold.setMinimumHeight(40)
        self._inp_threshold.setRange(1, 10_000)
        self._inp_threshold.setValue(500)
        self._inp_threshold.setSingleStep(50)
        self._inp_threshold.setToolTip(
            "Values ≥ this threshold are highlighted yellow.\n"
            "Values below are highlighted green.")
        self._inp_threshold.setStyleSheet(_SPIN_NATIVE_CSS)
        self._inp_threshold.setEnabled(False)
        self._inp_threshold.valueChanged.connect(self._recolor_wcs_grid)
        r1.addWidget(self._inp_threshold)

        lbl_thr_unit = QLabel("µs")
        lbl_thr_unit.setFont(QFont(_FONT, 9))
        lbl_thr_unit.setStyleSheet(f"color:{_CLR_MUTED};")
        r1.addWidget(lbl_thr_unit)
        r1.addStretch()
        lo.addLayout(r1)

        # Row 2: Excel checkbox + Monte Carlo + cycles
        r2 = QHBoxLayout()
        r2.setSpacing(6)

        self._chk_xl = QCheckBox("Generate Excel report")
        self._chk_xl.setFont(QFont(_FONT, 10))
        self._chk_xl.setChecked(True)
        self._chk_xl.setStyleSheet(_CHECK_CSS)
        self._chk_xl.setEnabled(False)
        r2.addWidget(self._chk_xl)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet(f"color:{_CLR_BORDER};")
        r2.addWidget(sep2)

        self._chk_mc = QCheckBox("Monte Carlo")
        self._chk_mc.setFont(QFont(_FONT, 10))
        self._chk_mc.setChecked(True)
        self._chk_mc.setStyleSheet(_CHECK_CSS)
        self._chk_mc.setEnabled(False)
        r2.addWidget(self._chk_mc)

        lbl_c = QLabel("Cycles:")
        lbl_c.setFont(QFont(_FONT, 9))
        lbl_c.setStyleSheet(f"color:{_CLR_MUTED};")
        r2.addWidget(lbl_c)

        self._spin_mc = QSpinBox()
        self._spin_mc.setFont(QFont(_FONT_MONO, 9))
        self._spin_mc.setMinimumWidth(80)
        self._spin_mc.setMaximumWidth(130)
        self._spin_mc.setMinimumHeight(40)
        self._spin_mc.setRange(1_000, 500_000)
        self._spin_mc.setSingleStep(10_000)
        self._spin_mc.setValue(50_000)
        self._spin_mc.setEnabled(False)
        self._spin_mc.setStyleSheet(_SPIN_NATIVE_CSS)
        r2.addWidget(self._spin_mc)
        r2.addStretch()
        lo.addLayout(r2)

        g.setLayout(lo)
        return g

    # --------------------------------------------------------------------------
    #  Status bar helper
    # --------------------------------------------------------------------------

    def _restore_ready(self, _=None):
        """Restore 'Ready' message only if no pipeline is running."""
        if getattr(self, '_is_running', False):
            return  # don't overwrite 'Running pipeline…'
        self._status_msg.setText("Ready")

    # --------------------------------------------------------------------------
    #  Dark theme
    # --------------------------------------------------------------------------

    def _apply_theme(self):
        p = QPalette()
        for role, clr in [
            (QPalette.ColorRole.Window,        _CLR_BG),
            (QPalette.ColorRole.WindowText,    _CLR_TEXT),
            (QPalette.ColorRole.Base,          _CLR_SURF),
            (QPalette.ColorRole.AlternateBase, _CLR_BG),
            (QPalette.ColorRole.Text,          _CLR_TEXT),
            (QPalette.ColorRole.Button,        _CLR_SURF),
            (QPalette.ColorRole.ButtonText,    _CLR_TEXT),
        ]:
            p.setColor(role, QColor(clr))
        self.setPalette(p)
        self.setStyleSheet(f"""
            QRadioButton {{ color:{_CLR_TEXT}; font-size:10pt; spacing:8px; }}
            QRadioButton::indicator {{ width:18px; height:18px; }}
            QRadioButton::indicator:unchecked {{
                border:2px solid {_CLR_MUTED}; border-radius:9px;
                background:{_CLR_SURF};
            }}
            QRadioButton::indicator:checked {{
                border:2px solid {_CLR_ACCENT}; border-radius:9px;
                background:{_CLR_ACCENT};
            }}
            QLabel {{ color:{_CLR_TEXT}; }}
            QToolTip {{
                background:{_CLR_PANEL}; color:{_CLR_TEXT};
                border:1px solid {_CLR_ACCENT}; padding:6px; font-size:10pt;
            }}
        """)

    # --------------------------------------------------------------------------
    #  Slots
    # --------------------------------------------------------------------------

    def _on_sim_toggle(self, on: bool):
        self._chk_mc.setEnabled(on)
        self._spin_mc.setEnabled(on)
        self._chk_xl.setEnabled(on)
        self._inp_threshold.setEnabled(on)
        self._btn_run.setText(
            "Run Full Pipeline" if on else "Run Instrumentation")
        self._toggle_results_tab(on)
        # keep View menu in sync
        if hasattr(self, "_act_dem"):
            self._act_dem.blockSignals(True)
            self._act_dem.setChecked(on)
            self._act_dem.blockSignals(False)

    def _toggle_results_tab(self, show: bool):
        if show and self._results_tab_idx is None:
            self._results_tab_idx = 1
            self._tabs.insertTab(1, self._results_widget, "  Simulation Results")
        elif not show and self._results_tab_idx is not None:
            self._tabs.removeTab(self._results_tab_idx)
            self._results_tab_idx = None


    def _src_changed(self):
        if self._rad_sf.isChecked():
            self._lbl_input.setText("Project Name:")
            self._inp.setPlaceholderText("e.g.  PROJ2_0U0_OB6_024")
        else:
            self._lbl_input.setText("Release Name:")
            self._inp.setPlaceholderText("Enter MKS release name...")

    def _browse(self):
        if self._rad_sf.isChecked():
            path = QFileDialog.getExistingDirectory(
                self, "Select Project Folder", r"D:\casdev\td5",
                QFileDialog.Option.ShowDirsOnly)
            if path:
                self._inp.setText(os.path.basename(path))

    def _on_inp_text_changed(self, text: str):
        """Restart debounce timer on every keystroke."""
        if not text.strip():
            self._set_td5_warning(False)
        self._refresh_timer.start()  # reset the countdown on every character

    
    def _set_td5_warning(self, visible: bool, reason: str = ""):
        if not hasattr(self, "_td5_warn_action"):
            return

        if visible:
            tip = (
                "TD5 structure not detected for this project.\n"
                "The tool supports TD5 projects only."
            )
            if reason:
                tip = f"{tip}\n\nDetails: {reason}"

            self._td5_warn_action.setToolTip(tip)
            self._td5_warn_action.setVisible(True)

            self._inp.setStyleSheet(f"""
                QLineEdit {{
                    border: 1px solid {_CLR_YELLOW}; border-radius: 6px;
                    padding: 7px 12px;
                    background: {_CLR_SURF}; color: white;
                    font-size: 11pt;
                }}
                QLineEdit:focus {{ border-color: {_CLR_ACCENT}; }}
            """)
        else:
            self._td5_warn_action.setVisible(False)
            self._td5_warn_action.setToolTip(
                "Only TD5 project structures are supported by this tool."
            )
            self._inp.setStyleSheet(_INPUT_CSS)

    def _refresh_targets_debounced(self):
        """Called by debounce timer — runs _refresh_targets with wait cursor."""
        name = self._inp.text().strip()
        if not name:
            QApplication.restoreOverrideCursor()
            return
        # setOverrideCursor only if it is not already set (e.g. after double-click)
        already_waiting = QApplication.overrideCursor() is not None
        if not already_waiting:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._refresh_targets(name)
        finally:
            QApplication.restoreOverrideCursor()

    def _refresh_targets(self, text: str):
        """Detect targets + build types from .tdxml and populate both combos."""
        name = text.strip() if isinstance(text, str) else text
        if not name:
            self._set_td5_warning(False)
            return
        try:
            from .path_utils import create_case_path
            case_path = create_case_path(name)
            if not case_path:
                self._set_td5_warning(
                    True,
                    "Project name format is invalid for TD5 naming conventions.",
                )
                return

            if not os.path.isdir(case_path):
                self._set_td5_warning(
                    True,
                    f"Expected TD5 path not found: {case_path}",
                )
                return

            from .td5_builder import find_targets_recursively
            entries = find_targets_recursively(case_path)
            if not entries:
                self._set_td5_warning(
                    True,
                    "No TD5 targets (.tdxml) found in this project structure.",
                )
                return

            self._set_td5_warning(False)

            # Store the per-target mapping
            self._target_buildtypes = {
                te.name: te.buildtypes for te in entries
            }

            # Populate target combo
            prev_target = self._cmb_target.currentText()
            self._cmb_target.blockSignals(True)
            self._cmb_target.clear()
            for te in entries:
                self._cmb_target.addItem(te.name)
            idx = self._cmb_target.findText(prev_target)
            self._cmb_target.setCurrentIndex(max(0, idx))
            self._cmb_target.blockSignals(False)
            n_targets = len(entries)
            self._lbl_tgt_status.setText(
                f"* {n_targets} target{'s' if n_targets != 1 else ''}"
                )

            # Trigger build-type refresh for the selected target
            self._on_target_changed()
        except Exception as exc:
            self._set_td5_warning(True, str(exc))
            logger.debug("_refresh_targets failed for %r: %s", text, exc, exc_info=True)

    def _on_target_changed(self, _index: int = 0):
        """Update the Build Type combo based on the selected target."""
        target = self._cmb_target.currentText()
        bts = self._target_buildtypes.get(target, [])

        prev_bt = self._cmb_buildtype.currentText()
        self._cmb_buildtype.blockSignals(True)
        self._cmb_buildtype.clear()
        if bts:
            for bt in bts:
                self._cmb_buildtype.addItem(bt)
        else:
            self._cmb_buildtype.addItem("NORMAL")
        idx = self._cmb_buildtype.findText(prev_bt)
        self._cmb_buildtype.setCurrentIndex(max(0, idx))
        self._cmb_buildtype.blockSignals(False)

        n = self._cmb_buildtype.count()
        self._lbl_bt_status.setText(f"* {n} type{'s' if n != 1 else ''}")

    # --------------------------------------------------------------------------
    #  Run
    # --------------------------------------------------------------------------

    def _run(self):
        val = self._inp.text().strip()
        if not val:
            QMessageBox.warning(self, "Input Required",
                                "Please enter a project or release name.")
            return

        self._btn_run.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setMaximum(0)
        self._current_project = val
        self._is_running = True

        run_sim = self._chk_sim.isChecked()

        # Add to project navigator
        mode = "System File" if self._rad_sf.isChecked() else "MKS"
        self._add_project_to_list(val, mode=mode, status="running")

        self._term_widget.clear()
        self._t("=" * 76)
        self._t("WCS -- FULL PIPELINE" if run_sim else "WCS -- INSTRUMENTATION ONLY")
        self._t("=" * 76)

        td5  = r"C:\LegacyApp\TD5\4.4.0\eclipse_cli\td5.exe"
        tgt  = self._cmb_target.currentText() or ""
        btyp = self._cmb_buildtype.currentText() or "NORMAL"
        rule = "All"

        params = {
            'td5_path':            td5,
            'target_name':         tgt if tgt else None,
            'build_type':          btyp,
            'rule':                rule,
            'run_simulation':      run_sim,
            'sim_generate_excel':  self._chk_xl.isChecked(),
            'sim_run_monte_carlo': self._chk_mc.isChecked(),
            'sim_mc_cycles':       self._spin_mc.value(),
            'sim_yellow_threshold': self._inp_threshold.value(),
        }

        if self._rad_sf.isChecked():
            op = "system_file"
            params['proj_name'] = val
            self._t(f"\n  Mode      :  System File")
            self._t(f"  Project   :  {val}")
        else:
            op = "mks"
            params['release_name'] = val
            self._t(f"\n  Mode      :  MKS")
            self._t(f"  Release   :  {val}")

        self._t(f"  TD5       :  {td5}")
        self._t(f"  Target    :  {tgt or '(auto-detect)'}")
        self._t(f"  Build     :  {btyp}")
        self._t(f"  Simulate  :  {'Yes' if run_sim else 'No'}")
        if run_sim:
            self._t(
                f"  MC        :  {'Yes' if self._chk_mc.isChecked() else 'No'}"
                f"   Cycles: {self._spin_mc.value():,}"
                f"   Excel: {'Yes' if self._chk_xl.isChecked() else 'No'}")
        self._t("\n" + "=" * 76 + "\n")

        log_path = rotate_log_file(val)
        self._t(f"  Log file  :  {log_path}")

        # Start elapsed timer
        self._elapsed.start()
        self._lbl_elapsed.setText("00:00:00")
        self._lbl_elapsed.setVisible(True)
        self._tick_timer.start()
        self._status_msg.setText("Running pipeline…")

        self._worker = PipelineWorker(op, params)
        self._worker.progress.connect(lambda m: self._t(f"\n>>> {m}"))
        self._worker.command_output.connect(self._t)
        self._worker.simulation_done.connect(self._show_results)
        self._worker.finished.connect(self._done)
        self._worker.start()

    # --------------------------------------------------------------------------
    #  Terminal helper
    # --------------------------------------------------------------------------

    def _t(self, msg: str):
        sb = self._term_widget.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4   # small tolerance
        self._term_widget.append(msg.rstrip())
        if at_bottom:
            cur = self._term_widget.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            self._term_widget.setTextCursor(cur)
            sb.setValue(sb.maximum())

    # --------------------------------------------------------------------------
    #  Show simulation results
    # --------------------------------------------------------------------------

    def _show_results(self, res):
        if res is None:
            return
        self._sim_result = res

        if not res.success:
            self._lbl_no_results.setText(
                f"  Simulation failed: {res.error_message}")
            self._lbl_no_results.setStyleSheet(
                f"color:{_CLR_RED}; padding:20px;")
            return

        self._lbl_no_results.setVisible(False)
        self._res_body.setVisible(True)

        # calibration labels
        for key, lbl in self._cfg_labels.items():
            lbl.setText(str(getattr(res, key, "--")))

        # WCS grid table
        yellow_thr = self._inp_threshold.value()
        for ri, sk in enumerate(["S1", "S2", "S3"]):
            row = res.wcs_grid.get(
                f"scenario_{ri + 1}", res.wcs_grid.get(sk, []))
            for ci, v in enumerate(row):
                it = QTableWidgetItem(f"{v:.0f}")
                it.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter |
                    Qt.AlignmentFlag.AlignVCenter)
                if v >= yellow_thr:
                    it.setBackground(QColor(_CLR_YELLOW))
                    it.setForeground(QColor("#000000"))
                else:
                    it.setBackground(QColor(_CLR_GREEN))
                    it.setForeground(QColor("#FFFFFF"))
                self._tbl.setItem(ri, ci, it)

        # stats
        def _set_stat(key, val):
            if key not in self._stat_labels:
                return
            lbl, unit = self._stat_labels[key]
            if isinstance(val, float):
                lbl.setText(f"{val:.2f} {unit}".strip())
            else:
                lbl.setText(f"{val} {unit}".strip())

        _set_stat("rmse_total", res.rmse_total if res.has_reference else "N/A")
        for sk in ("S1", "S2", "S3"):
            rk = f"scenario_{('S1','S2','S3').index(sk) + 1}"
            rv = res.rmse_per_scenario.get(
                rk, res.rmse_per_scenario.get(sk, 0.0))
            _set_stat(f"rmse_{sk.lower()}", rv if res.has_reference else "N/A")
        _set_stat("mc_peak",      res.mc_peak_us   or "N/A")
        _set_stat("mc_mean",      res.mc_mean_us   or "N/A")
        _set_stat("mc_p99",       res.mc_p99_us    or "N/A")
        _set_stat("num_variants", res.num_variants)

        # report
        if res.excel_path:
            self._lbl_report.setText(f"  {res.excel_path}")
            self._lbl_report.setStyleSheet(f"color:{_CLR_GREEN};")
            self._btn_open.setEnabled(True)
        else:
            self._lbl_report.setText("Excel report was not generated.")
            self._btn_open.setEnabled(False)

        # warnings
        if res.warnings:
            self._grp_warn.setVisible(True)
            self._lbl_warn.setText(
                "\n".join(f"  {w}" for w in res.warnings))
        else:
            self._grp_warn.setVisible(False)

        # switch to results tab
        self._toggle_results_tab(True)
        if self._results_tab_idx is not None:
            self._tabs.setCurrentIndex(self._results_tab_idx)

    def _recolor_wcs_grid(self, _=None):
        """Re-apply cell colors when the user changes the threshold."""
        try:
            yellow_thr = self._inp_threshold.value()
        except (ValueError, AttributeError):
            yellow_thr = 500
        for ri in range(self._tbl.rowCount()):
            for ci in range(self._tbl.columnCount()):
                it = self._tbl.item(ri, ci)
                if it is None:
                    continue
                try:
                    v = float(it.text())
                except ValueError:
                    continue
                if v >= yellow_thr:
                    it.setBackground(QColor(_CLR_YELLOW))
                    it.setForeground(QColor("#000000"))
                else:
                    it.setBackground(QColor(_CLR_GREEN))
                    it.setForeground(QColor("#FFFFFF"))

    def _open_bench_dialog(self):
        dlg = BenchUploadDialog(self)
        self._last_bench_dialog = dlg
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        name = dlg.get_project_name()
        if not name:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Missing", "Please enter a project name.")
            return

        from .path_utils import create_case_path
        excel_name = BenchUploadDialog._EXCEL_NAME
        proj_dir = create_case_path(name)

        if proj_dir is None:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(
                self, "Invalid Name",
                f"Project name '{name}' is invalid.\n"
                f"Please enter a different name.")
            return

        xlsx_path = os.path.join(proj_dir, excel_name)

        # Validate
        if not os.path.isdir(proj_dir):
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(
                self, "Not Found",
                f"Project folder not found:\n{proj_dir}\n\n"
                f"Check the name and make sure the folder exists.")
            return

        if not os.path.isfile(xlsx_path):
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(
                self, "Not Found",
                f"Excel file not found:\n{xlsx_path}\n\n"
                f"Make sure '{excel_name}' exists in the project folder.")
            return

        # UI feedback
        self._status_msg.setText("Loading bench data...")
        self._t("\n" + "═" * 76)
        self._t(f"[BENCH] Importing bench data for: {name}")
        self._t("═" * 76)
        self._t(f"  Folder  : {proj_dir}")
        self._t(f"  Excel   : {excel_name}")
        self._t("  Steps   : parse Excel → extract config → fit costs → save")
        self._t("")

        # Keep cursor busy while worker runs
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        self._bench_worker = BenchImportWorker(xlsx_path, proj_dir, name)
        self._bench_worker.finished.connect(
            lambda ok, msg: self._on_bench_import_done(ok, msg, name)
        )
        self._bench_worker.start()

    def _copy_store_db(self):
        """Copy the centralized bench_store.db to a user-selected location.
        
        The active store ALWAYS remains the centralized network path.
        This button only creates a local backup/copy for offline use.
        """
        import sqlite3

        centralized_dir = r"\\vt1.vitesco.com\SMT\did01146\Aggr_info\ERRM_Error_Management\00_Aggregate_Generic\FinalTests_Results\WCS\bench_results"
        centralized_db = os.path.join(centralized_dir, "bench_store.db")

        if not os.path.isfile(centralized_db):
            QMessageBox.warning(
                self, "Error",
                f"Centralized bench store not found:\n{centralized_db}\n\n"
                "Make sure the network share is accessible."
            )
            return

        # Let user pick destination
        start_dir = os.path.expanduser("~\\Documents")
        if not os.path.isdir(start_dir):
            start_dir = os.path.expanduser("~")

        selected_path, _ = QFileDialog.getSaveFileName(
            self, "Copy Bench Store Database To...",
            os.path.join(start_dir, "bench_store.db"),
            "SQLite Database (*.db);;All Files (*)",
        )
        if not selected_path:
            return

        if not selected_path.lower().endswith(".db"):
            selected_path = selected_path + ".db"

        try:
            # WAL checkpoint to flush all pending writes into the .db file
            ckpt = sqlite3.connect(centralized_db)
            try:
                ckpt.execute("PRAGMA journal_mode=WAL;")
                ckpt.execute("PRAGMA wal_checkpoint(FULL);")
            finally:
                ckpt.close()

            # SQLite backup API for a consistent copy
            os.makedirs(os.path.dirname(selected_path) or ".", exist_ok=True)
            src_conn = sqlite3.connect(centralized_db)
            dst_conn = sqlite3.connect(selected_path)
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()

            self._t(f"\n[BENCH] Central DB copied to:\n  {selected_path}")
            QMessageBox.information(
                self, "Bench Store Copied",
                f"Centralized bench store copied to:\n{selected_path}\n\n"
                f"Note: Training always saves to the central store.\n"
                f"Use this button again to get an updated copy."
            )
        except Exception as exc:
            QMessageBox.warning(self, "Error",
                                f"Failed to copy bench store:\n{exc}")
            self._t(f"\n[BENCH] Error: {exc}")

    def _open_report(self):
        if self._sim_result and self._sim_result.excel_path:
            p = self._sim_result.excel_path
            if os.path.isfile(p):
                os.startfile(p)
            else:
                QMessageBox.warning(self, "Not Found",
                                    f"File not found:\n{p}")

    # --------------------------------------------------------------------------
    #  Finished
    # --------------------------------------------------------------------------

    def _update_elapsed(self):
        ms  = self._elapsed.elapsed()
        h   = ms // 3_600_000
        m   = (ms % 3_600_000) // 60_000
        s   = (ms % 60_000) // 1_000
        self._lbl_elapsed.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _done(self, ok: bool, msg: str):
        self._tick_timer.stop()
        self._update_elapsed()          # show exact final time

        self._progress.setVisible(False)
        self._btn_run.setEnabled(True)

        # Update project status in sidebar
        proj = getattr(self, '_current_project', '')
        if proj:
            self._add_project_to_list(
                proj, status="success" if ok else "failed")

        total_ms = self._elapsed.elapsed()
        h  = total_ms // 3_600_000
        m  = (total_ms % 3_600_000) // 60_000
        s  = (total_ms % 60_000) // 1_000
        duration = f"{h:02d}:{m:02d}:{s:02d}"

        self._t("\n" + "=" * 76)
        self._t(("[SUCCESS] " if ok else "[FAILED] ") + msg)
        self._t(f"  Duration  :  {duration}")
        self._t("=" * 76)
        self._t("\n>>> Ready.\n")
        self._is_running = False
        status = f"{'✓ Completed' if ok else '✗ Failed'} in {duration}"
        self._status_msg.setText(status)

        if ok:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.critical(self, "Error", msg)

    # --------------------------------------------------------------------------
    #  Geometry fix for minimize / restore
    # --------------------------------------------------------------------------

    def changeEvent(self, event):
        """Force layout recalculation when the window state changes."""
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            QTimer.singleShot(0, self._relayout)

    def resizeEvent(self, event):
        """Ensure layout updates on every resize."""
        super().resizeEvent(event)
        cw = self.centralWidget()
        if cw and cw.layout():
            cw.layout().activate()

    def _relayout(self):
        """Recursively invalidate every layout in the widget tree."""
        for w in self.findChildren(QWidget):
            lay = w.layout()
            if lay:
                lay.invalidate()
                lay.activate()
            w.updateGeometry()
        cw = self.centralWidget()
        if cw and cw.layout():
            cw.layout().invalidate()
            cw.layout().activate()
        self.updateGeometry()
        self.update()


# ==============================================================================
#  Launcher
# ==============================================================================

def launch_qt_app():
    """Entry point -- create QApplication, show the window, start event loop."""
    # Windows: set AppUserModelID so the taskbar uses our icon, not Python's
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"{_COMPANY}.{_APP_NAME}.{_APP_VERSION}"
        )
    except Exception as exc:
        logger.debug("SetCurrentProcessExplicitAppUserModelID not available: %s", exc)

    setup_logging()
    # Qt6 enables high-DPI by default; PassThrough avoids rounding artefacts
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(_APP_NAME)
    app.setApplicationVersion(_APP_VERSION)
    app.setOrganizationName(_COMPANY)
    app.setWindowIcon(QIcon(_ICON_PATH))
    app.setStyle("Fusion")
    w = MainWindowApp()
    w.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch_qt_app()

