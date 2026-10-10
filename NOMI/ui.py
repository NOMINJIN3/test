"""NOMI's interface (PySide6): the main window and everything in it.

Sections, in order:
  THEME          colors, fonts, the Qt stylesheet          (referred to as T.*)
  ICONS          line icons drawn in code
  CORE VIEW      the particle core and the ring of orbs
  PANELS         Micro Apps, Calendar, Momentum, Tasks, Skills Deck, Routines
  APP WINDOWS    Jarvis chat, Second Brain, Tasks, Calculator, Terminal, Settings
  SYSTEM MAP     every app, routine, skill and memory drawn as rings
  MAIN WINDOW    NomiUI: wiring, command bar, reply panel, boot screen
"""
from __future__ import annotations

import math
import random
import ast
import html
import operator
import platform
import sys
from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QSize, QTime, QTimer, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QIcon, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient, QShortcut, QTextCursor)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSlider, QSplitter, QTextBrowser, QTextEdit, QTimeEdit, QToolTip, QVBoxLayout, QWidget)
from datetime import date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from config import APP_NAME, DASHBOARD_PORT, EFFORTS, MODELS, VERSION
from core import confirm as confirm_gate
from core import undo as undo_stack
from core.hotkey import Hotkey
from core.llm_client import Jarvis
from core.log import log
from core.stt import Ears
from core.tts import Voice
from core.wake_word import WakeWord
from memory import config_manager as cfg
from memory.memory_manager import Store, day_key, greeting_word, now_ms

T = sys.modules[__name__]  # theme constants below are read as T.ACCENT, T.font(...), …


# ══════════════════════════════════════════════════════════════════════════════
# THEME — Colors, fonts and the Qt stylesheet for NOMI (blue holographic look).
# ══════════════════════════════════════════════════════════════════════════════
BG = "#03070d"
PANEL = "#08111e"
PANEL2 = "#0e1c30"
GLASS = "#0a1626"
LINE = "#16324d"
LINE2 = "#2a6aa3"
FG = "#dceeff"
MUTED = "#6f8aa6"
DIM = "#3f556c"
ACCENT = "#4fb3ff"
ACCENT2 = "#9fdcff"
OK = "#5fe0b0"
WARN = "#ff7b6b"
INK = "#04121f"  # text on accent buttons

# memory categories on the system map
CAT_COLORS = {"note": "#4fb3ff", "task": "#9fdcff", "chat": "#8a96ff", "day": "#5fe0c8"}


def qc(hex_color: str, alpha: float = 1.0) -> QColor:
    c = QColor(hex_color)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def _pick(families: list[str], fallback: str) -> str:
    have = set(QFontDatabase.families())
    for f in families:
        if f in have:
            return f
    return fallback


class Fonts:
    """Resolved once the QApplication exists."""
    display = "Sans Serif"
    body = "Sans Serif"
    mono = "Monospace"

    @classmethod
    def init(cls) -> None:
        cls.display = _pick(["Oxanium", "Orbitron", "Rajdhani", "Segoe UI Semibold", "SF Pro Display", "Helvetica Neue", "Ubuntu", "DejaVu Sans"], "Sans Serif")
        cls.body = _pick(["IBM Plex Sans", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Ubuntu", "Noto Sans", "DejaVu Sans"], "Sans Serif")
        cls.mono = _pick(["IBM Plex Mono", "JetBrains Mono", "Cascadia Mono", "Consolas", "SF Mono", "Menlo", "Ubuntu Mono", "DejaVu Sans Mono"], "Monospace")


def font(kind: str = "body", size: float = 10, weight: int = 400, spacing: float = 0) -> QFont:
    fam = {"display": Fonts.display, "mono": Fonts.mono}.get(kind, Fonts.body)
    f = QFont(fam)
    f.setPointSizeF(size)
    f.setWeight(QFont.Weight(weight))
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def stylesheet() -> str:
    return f"""
    QWidget {{ background: transparent; color: {FG}; }}
    QMainWindow, #Desk {{ background: {BG}; }}
    QToolTip {{ background: {GLASS}; color: {FG}; border: 1px solid {LINE2}; padding: 4px 6px; }}
    #Panel {{ background: {PANEL}; border-bottom: 1px solid {LINE}; }}
    #Col {{ background: {PANEL}; }}
    #ColL {{ border-right: 1px solid {LINE}; }}
    #ColR {{ border-left: 1px solid {LINE}; }}
    QLabel#PanelTitle {{ font-family: "{Fonts.display}"; font-size: 11pt; font-weight: 600; letter-spacing: 3px; }}
    QLabel#Lbl {{ font-family: "{Fonts.mono}"; font-size: 7.5pt; font-weight: 600; color: {MUTED}; letter-spacing: 1.5px; }}
    QLabel#Muted {{ color: {MUTED}; }}
    QPushButton {{ border: 1px solid {LINE2}; padding: 5px 10px; font-family: "{Fonts.mono}"; font-size: 8pt; font-weight: 600; letter-spacing: 1px; color: {FG}; background: transparent; }}
    QPushButton:hover {{ background: rgba(79,179,255,0.13); color: {ACCENT2}; border-color: {ACCENT}; }}
    QPushButton:pressed {{ background: rgba(79,179,255,0.25); }}
    QPushButton:disabled {{ color: {DIM}; border-color: {LINE}; }}
    QPushButton#Primary {{ background: {ACCENT}; border-color: {ACCENT}; color: {INK}; }}
    QPushButton#Primary:hover {{ background: {ACCENT2}; color: {INK}; }}
    QPushButton#Danger {{ background: {WARN}; border-color: {WARN}; color: #1a0705; }}
    QPushButton#Flat {{ border: none; padding: 2px 4px; color: {MUTED}; }}
    QPushButton#Flat:hover {{ color: {FG}; background: rgba(79,179,255,0.13); }}
    QPushButton#Toggle:checked {{ background: rgba(79,179,255,0.13); border-color: {ACCENT}; color: {ACCENT}; }}
    QPushButton#Wake {{ border: 1px solid {LINE}; padding: 3px 7px; font-size: 7.5pt; color: {MUTED}; }}
    QPushButton#Wake:checked {{ background: {OK}; border-color: {OK}; color: {INK}; }}
    QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QComboBox, QTimeEdit {{
        background: rgba(3,8,15,0.85); border: 1px solid {LINE}; padding: 6px 8px; color: {FG};
        selection-background-color: {ACCENT}; selection-color: {INK}; }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QTimeEdit:focus {{ border-color: {ACCENT}; }}
    QComboBox QAbstractItemView {{ background: {GLASS}; border: 1px solid {LINE2}; selection-background-color: rgba(79,179,255,0.25); }}
    QListWidget {{ background: transparent; border: none; outline: 0; }}
    QListWidget::item {{ padding: 7px 8px; border-bottom: 1px solid {LINE}; }}
    QListWidget::item:selected {{ background: rgba(79,179,255,0.13); color: {ACCENT2}; }}
    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {LINE2}; background: rgba(3,8,15,0.8); }}
    QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
    QSlider::groove:horizontal {{ height: 4px; background: {LINE}; }}
    QSlider::sub-page:horizontal {{ background: {ACCENT}; }}
    QSlider::handle:horizontal {{ background: {ACCENT}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {LINE2}; min-height: 30px; border-radius: 4px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ height: 0; }}
    #AppWindow {{ background: {GLASS}; }}
    #Card {{ background: {PANEL2}; border: 1px solid {LINE}; }}
    #Card:hover {{ border-color: {LINE2}; }}
    #Glass {{ background: rgba(10,22,38,0.96); border: 1px solid {LINE2}; }}
    #CmdBar {{ background: rgba(3,7,13,0.97); border-top: 1px solid {LINE}; }}
    #CmdBox {{ background: rgba(8,20,36,0.9); border: 1px solid {LINE2}; }}
    #CmdBox QLineEdit {{ border: none; background: transparent; font-size: 11pt; padding: 8px 2px; }}
    """


# ══════════════════════════════════════════════════════════════════════════════
# ICONS — Line icons drawn with QPainter (24×24 grid), so the app needs no image files.
# ══════════════════════════════════════════════════════════════════════════════
def _draw(p: QPainter, name: str) -> None:
    P = QPointF
    if name == "jarvis":
        p.drawEllipse(P(12, 12), 9, 9); p.drawEllipse(P(12, 12), 4, 4)
        for a, b in (((12, 3), (12, 6)), ((12, 18), (12, 21)), ((3, 12), (6, 12)), ((18, 12), (21, 12))):
            p.drawLine(P(*a), P(*b))
    elif name == "notes":
        path = QPainterPath(P(6, 3)); path.lineTo(15, 3); path.lineTo(19, 7); path.lineTo(19, 21); path.lineTo(6, 21); path.closeSubpath()
        p.drawPath(path); p.drawLine(P(14, 3), P(14, 8)); p.drawLine(P(14, 8), P(19, 8))
        p.drawLine(P(9, 12), P(16, 12)); p.drawLine(P(9, 16), P(14, 16))
    elif name == "tasks":
        for y in (6, 13):
            path = QPainterPath(P(4, y)); path.lineTo(6, y + 2); path.lineTo(9, y - 1); p.drawPath(path)
        for y in (7, 14, 20):
            p.drawLine(P(12, y), P(20, y))
    elif name == "calc":
        p.drawRect(QRectF(5, 3, 14, 18)); p.drawLine(P(8, 7), P(16, 7))
        for x, y in ((8.5, 12), (12, 12), (8.5, 16), (12, 16)):
            p.drawPoint(P(x, y))
        p.drawLine(P(15.5, 11), P(15.5, 18))
    elif name == "term":
        p.drawRect(QRectF(3, 4, 18, 16))
        path = QPainterPath(P(7, 9)); path.lineTo(10, 12); path.lineTo(7, 15); p.drawPath(path); p.drawLine(P(12, 15), P(17, 15))
    elif name == "settings":
        p.drawEllipse(P(12, 12), 3, 3)
        for a, b in (((12, 2), (12, 5)), ((12, 19), (12, 22)), ((2, 12), (5, 12)), ((19, 12), (22, 12)),
                     ((4.9, 4.9), (7, 7)), ((17, 17), (19.1, 19.1)), ((4.9, 19.1), (7, 17)), ((17, 7), (19.1, 4.9))):
            p.drawLine(P(*a), P(*b))
    elif name == "bolt":
        p.setBrush(p.pen().color())
        p.drawPolygon(QPolygonF([P(13, 2), P(4, 14), P(11, 14), P(10, 22), P(19, 10), P(12, 10)]))
    elif name == "play":
        p.setBrush(p.pen().color()); p.drawPolygon(QPolygonF([P(7, 4), P(20, 12), P(7, 20)]))
    elif name == "x":
        p.drawLine(P(6, 6), P(18, 18)); p.drawLine(P(18, 6), P(6, 18))
    elif name == "clock":
        p.drawEllipse(P(12, 12), 9, 9); path = QPainterPath(P(12, 7)); path.lineTo(12, 12); path.lineTo(15, 14); p.drawPath(path)
    elif name == "spark":
        for a, b in (((12, 3), (12, 7)), ((12, 17), (12, 21)), ((3, 12), (7, 12)), ((17, 12), (21, 12)),
                     ((6, 6), (8.5, 8.5)), ((15.5, 15.5), (18, 18)), ((6, 18), (8.5, 15.5)), ((15.5, 8.5), (18, 6))):
            p.drawLine(P(*a), P(*b))
    elif name == "globe":
        p.drawEllipse(P(12, 12), 9, 9); p.drawLine(P(3, 12), P(21, 12)); p.drawEllipse(P(12, 12), 4, 9)
    elif name == "app":
        p.drawRect(QRectF(4, 4, 16, 16)); p.drawLine(P(4, 9), P(20, 9))
    elif name == "mic":
        p.drawRoundedRect(QRectF(9, 3, 6, 11), 3, 3)
        path = QPainterPath(P(5, 11)); path.cubicTo(5, 20, 19, 20, 19, 11); p.drawPath(path); p.drawLine(P(12, 18), P(12, 21))
    elif name in ("spk_on", "spk_off"):
        path = QPainterPath(P(4, 9)); path.lineTo(8, 9); path.lineTo(13, 5); path.lineTo(13, 19); path.lineTo(8, 15); path.lineTo(4, 15); path.closeSubpath(); p.drawPath(path)
        if name == "spk_on":
            p.drawArc(QRectF(11.5, 7.5, 7, 9), -60 * 16, 120 * 16); p.drawArc(QRectF(10, 4, 12, 16), -60 * 16, 120 * 16)
        else:
            p.drawLine(P(16, 9), P(21, 15)); p.drawLine(P(21, 9), P(16, 15))
    elif name == "map":
        p.drawEllipse(P(12, 12), 9, 9); p.drawEllipse(P(12, 12), 5, 5)
        p.setBrush(p.pen().color()); p.drawEllipse(P(12, 12), 1.5, 1.5)
    elif name == "search":
        p.drawEllipse(P(11, 11), 7, 7); p.drawLine(P(16, 16), P(20, 20))
    elif name == "pencil":
        path = QPainterPath(P(4, 20)); path.lineTo(8, 20); path.lineTo(19, 9); path.lineTo(15, 5); path.lineTo(4, 16); path.closeSubpath(); p.drawPath(path)
    elif name == "grid":
        for x, y in ((3, 3), (14, 3), (3, 14), (14, 14)):
            p.drawRect(QRectF(x, y, 7, 7))
    elif name == "info":
        p.drawEllipse(P(12, 12), 9, 9); p.drawLine(P(12, 11), P(12, 17)); p.drawPoint(P(12, 7.6))
    elif name == "calendar":
        p.drawRect(QRectF(3, 5, 18, 16)); p.drawLine(P(3, 10), P(21, 10)); p.drawLine(P(8, 3), P(8, 7)); p.drawLine(P(16, 3), P(16, 7))
    elif name == "trend":
        path = QPainterPath(P(3, 17)); path.lineTo(9, 11); path.lineTo(13, 15); path.lineTo(21, 7); p.drawPath(path)
        path2 = QPainterPath(P(15, 7)); path2.lineTo(21, 7); path2.lineTo(21, 13); p.drawPath(path2)
    elif name == "hex":
        p.drawPolygon(QPolygonF([P(12, 2), P(20.7, 7), P(20.7, 17), P(12, 22), P(3.3, 17), P(3.3, 7)])); p.drawEllipse(P(12, 12), 3, 3)


@lru_cache(maxsize=256)
def _pixmap(name: str, color: str, size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 24, size / 24)
    pen = QPen(QColor(color), 1.7)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    _draw(p, name)
    p.end()
    return pm


def icon(name: str, color: str = "#dceeff", size: int = 48) -> QIcon:
    return QIcon(_pixmap(name, color, size))


def pixmap(name: str, color: str = "#dceeff", size: int = 48) -> QPixmap:
    return _pixmap(name, color, size)


# ══════════════════════════════════════════════════════════════════════════════
# CORE VIEW: PARTICLE CORE + ORB RING — The center of the dashboard: the rotating particle core and the ring of orbs around it.
# ══════════════════════════════════════════════════════════════════════════════
class ParticleCore(QWidget):
    """A wireframe sphere with a dense glowing cluster inside. Spins faster while
    Jarvis thinks and pulses while he speaks."""

    clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.mode = "standby"
        self.t = 0.0
        rnd = random.Random(7)
        n = 420
        self.shell = []
        for i in range(n):  # Fibonacci sphere
            y = 1 - (i / (n - 1)) * 2
            r = math.sqrt(max(0.0, 1 - y * y))
            th = i * 2.399963
            self.shell.append((math.cos(th) * r, y, math.sin(th) * r))
        self.edges = []
        for i, p in enumerate(self.shell):
            near = sorted(((sum((p[k] - q[k]) ** 2 for k in range(3)), j) for j, q in enumerate(self.shell) if j > i))[:2]
            for _, j in near:
                if rnd.random() < 0.55:
                    self.edges.append((i, j))
        cols = [T.qc("#dcf0ff"), T.qc(T.ACCENT), T.qc(T.ACCENT2), T.qc("#788cff"), T.qc("#5fe0c8")]
        self.core = []
        for _ in range(700):
            u, v = rnd.random(), rnd.random()
            th, ph = 2 * math.pi * u, math.acos(2 * v - 1)
            r = 0.42 * rnd.random() ** (1 / 3) * (1.3 if rnd.random() < 0.2 else 1)
            self.core.append((r * math.sin(ph) * math.cos(th), r * math.cos(ph), r * math.sin(ph) * math.sin(th), rnd.choice(cols), rnd.random() * 6.28))
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Talk to Jarvis")
        self.timer = QTimer(self, interval=33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def _tick(self) -> None:
        speed = {"thinking": 3.0, "speaking": 1.6, "listening": 2.2}.get(self.mode, 0.55)
        self.t += 0.004 * speed
        self.update()

    def mousePressEvent(self, e) -> None:
        self.clicked.emit()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        size = min(w, h)
        R, cx, cy = size * 0.44, w / 2, h / 2
        t = self.t
        cyy, syy = math.cos(t), math.sin(t)
        rx = -0.35
        cxx, sxx = math.cos(rx), math.sin(rx)
        if self.mode == "speaking":
            breathe = 1 + 0.05 * abs(math.sin(t * 22))
        elif self.mode == "thinking":
            breathe = 1 + 0.03 * math.sin(t * 14)
        elif self.mode == "listening":
            breathe = 1 + 0.04 * abs(math.sin(t * 10))
        else:
            breathe = 1 + 0.01 * math.sin(t * 3)

        def proj(x, y, z, s=1.0):
            x, y, z = x * s, y * s, z * s
            x1, z1 = x * cyy + z * syy, -x * syy + z * cyy
            y1, z2 = y * cxx - z1 * sxx, y * sxx + z1 * cxx
            f = 2.6 / (2.6 + z2)
            return cx + x1 * R * f, cy + y1 * R * f, z2, f

        g = QRadialGradient(QPointF(cx, cy), R * 0.75)
        g.setColorAt(0, T.qc(T.ACCENT, 0.22))
        g.setColorAt(1, T.qc(T.ACCENT, 0))
        p.fillRect(self.rect(), g)

        P = [proj(*q, breathe) for q in self.shell]
        pen = QPen()
        pen.setWidthF(max(0.6, size / 700))
        for a, b in self.edges:
            A, B = P[a], P[b]
            pen.setColor(T.qc(T.ACCENT2, 0.05 + 0.11 * (1 - (A[2] + B[2] + 2) / 4)))
            p.setPen(pen)
            p.drawLine(QPointF(A[0], A[1]), QPointF(B[0], B[1]))
        p.setPen(Qt.NoPen)
        for x, y, z, f in P:
            p.setBrush(T.qc("#dcf0ff", 0.15 + 0.45 * (1 - (z + 1) / 2)))
            s = 1.5 * f * size / 600
            p.drawRect(QRectF(x, y, s, s))
        jit = {"thinking": 0.06, "speaking": 0.035, "listening": 0.05}.get(self.mode, 0.012)
        for x0, y0, z0, col, ph in self.core:
            k = 1 + math.sin(t * 9 + ph) * jit
            x, y, z, f = proj(x0, y0, z0, breathe * k)
            c = QColor(col)
            c.setAlphaF(max(0.15, min(1.0, 0.35 + 0.6 * (1 - (z + 0.6) / 1.2))))
            p.setBrush(c)
            s = (1.4 + 0.9 * f) * size / 600
            p.drawRect(QRectF(x, y, s, s))
        g2 = QRadialGradient(QPointF(cx, cy), R * 0.12)
        g2.setColorAt(0, T.qc("#f0faff", 0.95))
        g2.setColorAt(1, T.qc(T.ACCENT, 0))
        p.setBrush(g2)
        p.drawEllipse(QPointF(cx, cy), R * 0.12, R * 0.12)
        p.end()


class OrbButton(QPushButton):
    """A round icon button on the ring."""

    def __init__(self, icon_name: str, tip: str, skill: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setToolTip(tip)
        self.setIcon(icon(icon_name, T.FG))
        self.setCursor(Qt.PointingHandCursor)
        self.skill = skill
        self.active = False
        self.setAccessibleName(tip)

    def set_size(self, s: int) -> None:
        self.setFixedSize(s, s)
        self.setIconSize(QSize(int(s * 0.44), int(s * 0.44)))
        border = T.ACCENT2 if self.skill else "rgba(220,238,255,0.55)"
        if self.active:
            border = T.ACCENT
        self.setStyleSheet(
            f"QPushButton {{ border-radius: {s // 2}px; border: 1.5px solid {border};"
            f" background: qradialgradient(cx:0.35, cy:0.3, radius:0.9, fx:0.35, fy:0.3, stop:0 #1a2c44, stop:1 #08121f); padding: 0; }}"
            f"QPushButton:hover {{ border-color: {T.ACCENT}; background: #12304f; }}")


class CenterView(QWidget):
    """Header + particle core + orbs placed evenly around it + state line."""

    talk = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.core = ParticleCore(self)
        self.core.clicked.connect(self.talk)
        self.orbs: list[OrbButton] = []
        self.state = QLabel(self)
        self.state.setAlignment(Qt.AlignCenter)
        self.state.setFont(T.font("mono", 8, 500, 3))
        self.set_state("standby")
        self.header = QWidget(self)
        lay = QVBoxLayout(self.header)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(2)
        self.title = QLabel()
        self.title.setTextFormat(Qt.RichText)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(T.font("display", 19, 700, 1))
        self.title.setText(f"<span style='color:{T.ACCENT}'>⬡</span> NOMI <span style='color:{T.ACCENT};font-weight:400'>Agentic OS</span>")
        self.sub = QLabel()
        self.sub.setAlignment(Qt.AlignCenter)
        self.sub.setFont(T.font("mono", 8.5, 500, 2.5))
        self.sub.setStyleSheet(f"color:{T.MUTED}")
        self.tools = QWidget()
        self.tools_lay = QVBoxLayout(self.tools)
        self.tools_lay.setContentsMargins(0, 4, 0, 0)
        lay.addWidget(self.title)
        lay.addWidget(self.sub)
        lay.addWidget(self.tools)

    def set_user(self, name: str, family: str = "") -> None:
        self.sub.setText(f"{family}  |  {name}" if family else name)

    def set_state(self, mode: str) -> None:
        label = {"standby": "Standby", "thinking": "Processing", "speaking": "Speaking", "listening": "Listening", "offline": "Offline"}.get(mode, mode)
        self.state.setText(f"<span style='color:{T.MUTED}'>CORE · </span><span style='color:{T.ACCENT}'>{label.upper()}</span>")
        self.core.set_mode(mode)

    def set_orbs(self, orbs: list[OrbButton]) -> None:
        for o in self.orbs:
            o.deleteLater()
        self.orbs = orbs
        for o in orbs:
            o.setParent(self)
            o.show()
        self._layout()

    def resizeEvent(self, e) -> None:
        self._layout()

    def _layout(self) -> None:
        w, h = self.width(), self.height()
        hh = self.header.sizeHint().height()
        self.header.setGeometry(0, 0, w, hh)
        top, bottom = hh + 6, h - 26
        area_h = bottom - top
        size = max(200, min(w - 20, area_h))
        cx, cy = w / 2, top + area_h / 2
        rad = size / 2 - 26
        n = max(1, len(self.orbs))
        s = int(max(28, min(46, 2 * math.pi * rad / n - 8)))
        a0 = math.pi / 2 + math.pi / n  # half-step offset so nothing sits dead centre at the bottom
        for i, o in enumerate(self.orbs):
            a = a0 + 2 * math.pi * i / n
            o.set_size(s)
            o.move(int(cx + math.cos(a) * rad - s / 2), int(cy + math.sin(a) * rad - s / 2))
        cs = int(max(140, rad * 2 - s - 26))
        self.core.setGeometry(int(cx - cs / 2), int(cy - cs / 2), cs, cs)
        self.state.setGeometry(0, h - 24, w, 20)
        self.core.lower()


# ══════════════════════════════════════════════════════════════════════════════
# PANELS — Side panels: Micro Apps, Calendar, Momentum (left) and Tasks, Skills Deck, Routines (right).
# ══════════════════════════════════════════════════════════════════════════════
# --------------------------------------------------------------------------- helpers
def label(text: str = "", kind: str = "", style: str = "") -> QLabel:
    l = QLabel(text)
    if kind:
        l.setObjectName(kind)
    if style:
        l.setStyleSheet(style)
    return l


def mini_button(text: str, accent: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"padding: 3px 8px; font-size: 7.5pt; {'color:' + T.ACCENT + '; border-color:' + T.ACCENT + ';' if accent else ''}")
    return b


def icon_button(name: str, tip: str, color: str = T.ACCENT, size: int = 22) -> QPushButton:
    b = QPushButton()
    b.setIcon(icon(name, color))
    b.setIconSize(QSize(size - 8, size - 8))
    b.setFixedSize(size + 4, size)
    b.setToolTip(tip)
    b.setAccessibleName(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet("padding: 0;")
    return b


class Panel(QFrame):
    """A titled section with an icon and optional header buttons."""

    def __init__(self, icon_name: str, title: str, *buttons: QPushButton) -> None:
        super().__init__()
        self.setObjectName("Panel")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(16, 14, 16, 16)
        self.lay.setSpacing(9)
        head = QHBoxLayout()
        head.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(pixmap(icon_name, T.ACCENT, 32).scaled(15, 15, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        t = QLabel(title.upper())
        t.setObjectName("PanelTitle")
        head.addWidget(ic)
        head.addWidget(t, 1)
        for b in buttons:
            head.addWidget(b)
        self.lay.addLayout(head)


class FormDialog(QDialog):
    """Small form: fields = [(key, label, placeholder, options | None, default)]."""

    def __init__(self, parent, title: str, fields: list) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("AppWindow")
        self.setStyleSheet(f"QDialog {{ background: {T.GLASS}; }}")
        self.setMinimumWidth(380)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        head = label(title.upper(), "PanelTitle", f"color:{T.ACCENT}")
        lay.addWidget(head)
        self.inputs = {}
        for key, lab, ph, opts, default in fields:
            lay.addWidget(label(lab.upper(), "Lbl"))
            if opts:
                w = QComboBox()
                for value, text in opts:
                    w.addItem(text, value)
                if default:
                    w.setCurrentIndex(max(0, w.findData(default)))
            elif key == "prompt":
                w = QPlainTextEdit()
                w.setPlaceholderText(ph)
                w.setFixedHeight(90)
                if default:
                    w.setPlainText(default)
            else:
                w = QLineEdit(default or "")
                w.setPlaceholderText(ph)
            self.inputs[key] = w
            lay.addWidget(w)
        self.err = label("", "", f"color:{T.WARN}")
        self.err.hide()
        lay.addWidget(self.err)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel, ok = QPushButton("Cancel"), QPushButton("Save")
        ok.setObjectName("Primary")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._ok)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)

    def values(self) -> dict:
        out = {}
        for k, w in self.inputs.items():
            out[k] = w.currentData() if isinstance(w, QComboBox) else (w.toPlainText() if isinstance(w, QPlainTextEdit) else w.text()).strip()
        return out

    def _ok(self) -> None:
        missing = [k for k, v in self.values().items() if v in ("", None)]
        if missing:
            self.err.setText("Please fill in every field.")
            self.err.show()
            return
        self.accept()


def ago(ts) -> str:
    try:
        ts = int(ts)
    except Exception:
        return ""
    if ts < 10**12:
        return ""
    m = (now_ms() - ts) // 60000
    return f"{max(1, m)}m" if m < 60 else f"{m // 60}h" if m < 1440 else f"{m // 1440}d"


# --------------------------------------------------------------------------- left: micro apps
class MicroAppsPanel(Panel):
    def __init__(self, store: Store, apps: dict, open_app, run_custom) -> None:
        self.add_btn = mini_button("+ Add app")
        super().__init__("grid", "Micro Apps", self.add_btn)
        self.store, self.apps, self.open_app, self.run_custom = store, apps, open_app, run_custom
        self.list = QVBoxLayout()
        self.list.setSpacing(0)
        self.lay.addLayout(self.list)
        self.add_btn.clicked.connect(self._add)
        store.changed.connect(lambda s: s == "apps" and self.render())
        self.render()

    def _row(self, icon_name: str, name: str, desc: str, cb) -> QPushButton:
        b = QPushButton()
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet("QPushButton { border: none; padding: 5px 4px; text-align: left; }"
                        "QPushButton:hover { background: rgba(79,179,255,0.13); }")
        b.setAccessibleName(name)
        lay = QHBoxLayout(b)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(pixmap(icon_name, T.ACCENT2, 36).scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        txt = QVBoxLayout()
        txt.setSpacing(0)
        n = QLabel(name)
        n.setFont(T.font("body", 9.5, 600))
        d = QLabel(desc)
        d.setStyleSheet(f"color:{T.MUTED}; font-size: 8pt;")
        txt.addWidget(n)
        txt.addWidget(d)
        arrow = QLabel("→")
        arrow.setStyleSheet(f"color:{T.DIM}")
        for w in (ic, n, d, arrow):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(ic)
        lay.addLayout(txt, 1)
        lay.addWidget(arrow)
        b.setMinimumHeight(44)
        b.clicked.connect(cb)
        return b

    def render(self) -> None:
        while self.list.count():
            w = self.list.takeAt(0).widget()
            if w:
                w.deleteLater()
        for key, a in self.apps.items():
            self.list.addWidget(self._row(a["icon"], a["name"], a["desc"], lambda _=False, k=key: self.open_app(k)))
        for c in self.store.custom_apps:
            self.list.addWidget(self._row("app", c["name"], "Micro app · runs with Jarvis", lambda _=False, c=c: self.run_custom(c)))

    def _add(self) -> None:
        d = FormDialog(self.window(), "Add micro app", [
            ("name", "Name", "e.g. Teleprompter", None, ""),
            ("prompt", "What should it do?", "e.g. Turn my latest note into a short script I can read on camera", None, "")])
        if d.exec():
            v = d.values()
            self.store.add_custom_app(v["name"], v["prompt"])


# --------------------------------------------------------------------------- left: calendar
def local_zone_label(now: datetime) -> str:
    """'GMT+8 · ULAANBAATAR' from the UTC offset and the system time zone name."""
    off = now.utcoffset()
    mins = int(off.total_seconds() // 60) if off else 0
    sign = "+" if mins >= 0 else "-"
    h, m = divmod(abs(mins), 60)
    gmt = f"GMT{sign}{h}" + (f":{m:02d}" if m else "")
    city = ""
    try:
        import os
        from pathlib import Path
        name = os.environ.get("TZ") or str(Path("/etc/localtime").resolve()).split("zoneinfo/")[-1]
        if "/" in name:
            city = name.rsplit("/", 1)[-1].replace("_", " ")
    except Exception:
        pass
    return f"{gmt} · {city}".upper() if city else gmt
class AnalogClock(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(64, 64)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(32, 32)
        r = 29
        p.setPen(QPen(T.qc(T.FG, 0.5), 1.5))
        p.drawEllipse(QPointF(0, 0), r, r)
        for i in range(12):
            a = i / 12 * 2 * math.pi
            inner = r - (6 if i % 3 == 0 else 4)
            p.setPen(QPen(T.qc(T.FG, 0.6), 1.5 if i % 3 == 0 else 0.8))
            p.drawLine(QPointF(math.sin(a) * (r - 2), -math.cos(a) * (r - 2)), QPointF(math.sin(a) * inner, -math.cos(a) * inner))
        now = datetime.now()
        s = now.second
        m = now.minute + s / 60
        h = now.hour % 12 + m / 60

        def hand(angle, length, width, color):
            pen = QPen(T.qc(color), width)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(0, 0), QPointF(math.sin(angle) * length, -math.cos(angle) * length))

        hand(h / 12 * 2 * math.pi, 15, 2.5, T.FG)
        hand(m / 60 * 2 * math.pi, 22, 1.8, T.FG)
        hand(s / 60 * 2 * math.pi, 24, 1, T.ACCENT)
        p.setPen(Qt.NoPen)
        p.setBrush(T.qc(T.ACCENT))
        p.drawEllipse(QPointF(0, 0), 2.5, 2.5)


class MonthGrid(QWidget):
    """This month as weeks × days: past days filled, today glowing."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(5 * 17 + 4)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        today = date.today()
        first = today.replace(day=1)
        days = ((first.replace(month=first.month % 12 + 1, year=first.year + (first.month == 12))) - first).days
        off = first.weekday()
        rows = math.ceil((off + days) / 7)
        self.setFixedHeight(rows * 17 + 4)
        p.setFont(T.font("mono", 7))
        for r in range(rows):
            y = r * 17 + 2
            p.setPen(T.qc(T.MUTED))
            p.drawText(QRectF(0, y, 22, 14), Qt.AlignVCenter, f"W{r + 1}")
            for c in range(7):
                n = r * 7 + c - off + 1
                rect = QRectF(26 + c * 17, y, 13, 13)
                if n < 1 or n > days:
                    continue
                if n < today.day:
                    p.setPen(Qt.NoPen)
                    p.setBrush(T.qc(T.FG, 0.85))
                elif n == today.day:
                    p.setPen(QPen(T.qc(T.ACCENT), 1))
                    p.setBrush(T.qc(T.ACCENT))
                else:
                    p.setPen(QPen(T.qc(T.DIM), 1))
                    p.setBrush(Qt.NoBrush)
                p.drawRect(rect)


class CalendarPanel(Panel):
    ZONES = [("Local", None), ("New York", "America/New_York"), ("London", "Europe/London")]

    def __init__(self) -> None:
        super().__init__("calendar", "Calendar")
        top = QHBoxLayout()
        top.setSpacing(14)
        self.clock = AnalogClock()
        txt = QVBoxLayout()
        txt.setSpacing(0)
        self.wk = label("", "", f"color:{T.ACCENT}; font-family:'{T.Fonts.mono}'; font-size:8.5pt; font-weight:600;")
        self.big = QLabel()
        self.big.setFont(T.font("display", 22, 600))
        self.big.setStyleSheet(f"color:{T.ACCENT}")
        self.tz = label("", "Lbl")
        txt.addWidget(self.wk)
        txt.addWidget(self.big)
        txt.addWidget(self.tz)
        top.addWidget(self.clock)
        top.addLayout(txt, 1)
        self.lay.addLayout(top)
        zrow = QHBoxLayout()
        self.zones = []
        for name, _ in self.ZONES:
            box = QVBoxLayout()
            box.setSpacing(0)
            box.addWidget(label(name.upper(), "Lbl"))
            v = QLabel()
            v.setFont(T.font("mono", 9, 600))
            box.addWidget(v)
            self.zones.append(v)
            zrow.addLayout(box)
        self.lay.addLayout(zrow)
        self.grid = MonthGrid()
        self.lay.addWidget(self.grid)
        self.tick()

    def tick(self) -> None:
        now = datetime.now().astimezone()
        h12 = now.hour % 12 or 12
        self.big.setText(f"{h12:02d}:{now.minute:02d}:{now.second:02d}<span style='font-size:12pt'> {'am' if now.hour < 12 else 'pm'}</span>")
        self.wk.setText(f"Wk{now.isocalendar()[1]} | {now.strftime('%b %d, %Y')} ({now.strftime('%a')})")
        self.tz.setText(local_zone_label(now))
        for (name, tz), lab in zip(self.ZONES, self.zones):
            try:
                t = now if tz is None else now.astimezone(ZoneInfo(tz))
                lab.setText(t.strftime("%I:%M %p"))
            except Exception:
                lab.setText("--:--")
        self.clock.update()
        if now.second == 0:
            self.grid.update()


# --------------------------------------------------------------------------- left: momentum
class Dots(QWidget):
    def __init__(self, store: Store) -> None:
        super().__init__()
        self.store = store
        self.setFixedSize(7 * 18, 4 * 18)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        act = self.store.data["activity"]
        for i in range(28):
            d = date.today() - timedelta(days=27 - i)
            n = act.get(d.isoformat(), 0)
            x, y = (i % 7) * 18 + 9, (i // 7) * 18 + 9
            col, a = (T.DIM, 0.6) if n == 0 else (T.ACCENT, 0.45 if n < 3 else 0.75 if n < 6 else 1)
            p.setPen(Qt.NoPen)
            p.setBrush(T.qc(col, a))
            p.drawEllipse(QPointF(x, y), 6, 6)
            if i == 27:
                p.setPen(QPen(T.qc(T.ACCENT2), 1.5))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(x, y), 8, 8)


class MomentumPanel(Panel):
    def __init__(self, store: Store) -> None:
        super().__init__("trend", "Momentum")
        self.store = store
        row = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(2)
        self.num = QLabel("0")
        self.num.setFont(T.font("display", 26, 700))
        self.num.setStyleSheet(f"color:{T.ACCENT}")
        left.addWidget(self.num)
        left.addWidget(label("ACTIONS · 28 DAYS", "Lbl"))
        self.sub = label("", "Muted")
        left.addWidget(self.sub)
        left.addStretch(1)
        self.dots = Dots(store)
        row.addLayout(left, 1)
        row.addWidget(self.dots, 0, Qt.AlignBottom)
        self.lay.addLayout(row)
        store.changed.connect(lambda s: s == "activity" and self.render())
        self.render()

    def render(self) -> None:
        act = self.store.data["activity"]
        vals = [act.get((date.today() - timedelta(days=i)).isoformat(), 0) for i in range(28)]
        self.num.setText(str(sum(vals)))
        self.sub.setText(f"{sum(1 for v in vals if v)} active days · best day {max(vals)}")
        self.dots.update()


# --------------------------------------------------------------------------- right: tasks
class MixBar(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[tuple[int, str]] = []
        self.setFixedHeight(6)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        total = sum(v for v, _ in self.parts) or 1
        x, w = 0.0, self.width()
        visible = [(v, c) for v, c in self.parts if v]
        gap = 3
        avail = w - gap * max(0, len(visible) - 1)
        if not visible:
            p.fillRect(self.rect(), T.qc(T.DIM))
        for v, c in visible:
            ww = avail * v / total
            p.fillRect(QRectF(x, 0, ww, 6), T.qc(c))
            x += ww + gap


class TasksPanel(Panel):
    def __init__(self, store: Store, open_tasks) -> None:
        self.open_btn = mini_button("Open")
        super().__init__("tasks", "Tasks", self.open_btn)
        self.store = store
        self.open_btn.clicked.connect(open_tasks)
        top = QHBoxLayout()
        self.count = QLabel("0")
        self.count.setFont(T.font("display", 30, 700))
        self.count.setStyleSheet(f"color:{T.ACCENT}")
        self.done = QLabel()
        self.done.setFont(T.font("mono", 8.5, 600, 1.5))
        top.addWidget(self.count)
        top.addWidget(self.done, 1, Qt.AlignVCenter)
        self.lay.addLayout(top)
        self.lay.addWidget(label("FLAGGED — NEEDS YOU", "Lbl"))
        self.flag = QVBoxLayout()
        self.flag.setSpacing(4)
        self.lay.addLayout(self.flag)
        self.lay.addWidget(label("TODAY'S MIX", "Lbl"))
        self.mix = MixBar()
        self.lay.addWidget(self.mix)
        self.legend = QLabel()
        self.legend.setTextFormat(Qt.RichText)
        self.legend.setFont(T.font("mono", 7.5))
        self.legend.setWordWrap(True)
        self.lay.addWidget(self.legend)
        self.saved = label("", "Muted")
        self.saved.setFont(T.font("mono", 7.5))
        self.lay.addWidget(self.saved)
        store.changed.connect(lambda s: s in ("todos", "notes", "routines") and self.render())
        self.render()

    def render(self) -> None:
        todos = self.store.todos
        open_ = [t for t in todos if not t["done"]]
        done = len(todos) - len(open_)
        self.count.setText(str(len(open_)))
        self.done.setText(f"OPEN<br><span style='color:{T.MUTED}'>{done} DONE</span>")
        while self.flag.count():
            item = self.flag.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    w = item.layout().takeAt(0).widget()
                    if w:
                        w.deleteLater()
        if not open_:
            self.flag.addWidget(label("All clear. Nice work.", "Muted"))
        for t in open_[:4]:
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            cb = QCheckBox(t["text"] if len(t["text"]) < 42 else t["text"][:40] + "…")
            cb.setToolTip(t["text"])
            cb.toggled.connect(lambda on, tid=t["id"]: on and self.store.set_task_done(tid, True))
            age = label(ago(t["id"]), "Muted")
            age.setFont(T.font("mono", 8))
            hl.addWidget(cb, 1)
            hl.addWidget(age)
            self.flag.addWidget(row)
        ran = sum(1 for v in self.store.data["routine_runs"].values() if v == day_key())
        parts = [("Done", done, T.ACCENT), ("Open", len(open_), T.FG), ("Notes", len(self.store.notes), T.ACCENT2), ("Routines", ran, T.DIM)]
        self.mix.parts = [(v, c) for _, v, c in parts]
        self.mix.update()
        self.legend.setText("&nbsp;&nbsp;".join(f"<span style='color:{c}'>■</span> <span style='color:{T.MUTED}'>{n.upper()}</span> <b>{v}</b>" for n, v, c in parts))
        self.saved.setText(f"● Saved locally {datetime.now().strftime('%H:%M')} · {len(self.store.notes)} notes")
        self.saved.setStyleSheet(f"color:{T.MUTED}")


# --------------------------------------------------------------------------- right: skills
class SkillPicker(QFrame):
    """Model × Effort grid. The chosen model's row fills up to the chosen effort, with a knob."""

    run = Signal(dict)

    def __init__(self, parent, store: Store, skill: dict) -> None:
        super().__init__(parent, Qt.Popup)
        self.store, self.skill = store, skill
        self.setObjectName("Glass")
        self.setFixedSize(330, 280)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        head = QHBoxLayout()
        t = QLabel(f"<b>/{skill['name']}</b> <span style='color:{T.MUTED}'>· MODEL × EFFORT</span>")
        t.setFont(T.font("mono", 9))
        x = icon_button("x", "Close", T.MUTED)
        x.clicked.connect(self.close)
        head.addWidget(t, 1)
        head.addWidget(x)
        lay.addLayout(head)
        self.grid = _PickerGrid(self)
        lay.addWidget(self.grid, 1)
        foot = QHBoxLayout()
        hint = label("Lighter models answer faster; higher effort thinks longer.", "Muted")
        hint.setWordWrap(True)
        hint.setFont(T.font("body", 8))
        go = QPushButton(" RUN")
        go.setIcon(icon("play", T.INK))
        go.setObjectName("Primary")
        go.clicked.connect(lambda: (self.close(), self.run.emit(self.skill)))
        foot.addWidget(hint, 1)
        foot.addWidget(go)
        lay.addLayout(foot)

    def choose(self, model: str, effort: str) -> None:
        self.skill["model"], self.skill["effort"] = model, effort
        self.store.touch("skills")
        self.grid.update()


class _PickerGrid(QWidget):
    COL0 = 60

    def __init__(self, picker: SkillPicker) -> None:
        super().__init__()
        self.picker = picker
        self.setMouseTracking(True)
        self.hover = None

    def _cell(self, pos):
        w = (self.width() - self.COL0) / len(EFFORTS)
        r = int((pos.y() - 22) // 34)
        c = int((pos.x() - self.COL0) // w)
        if 0 <= r < len(MODELS) and 0 <= c < len(EFFORTS) and pos.x() >= self.COL0 and pos.y() >= 22:
            return r, c
        return None

    def mouseMoveEvent(self, e) -> None:
        self.hover = self._cell(e.position())
        self.setCursor(Qt.PointingHandCursor if self.hover else Qt.ArrowCursor)
        self.update()

    def mousePressEvent(self, e) -> None:
        cell = self._cell(e.position())
        if cell:
            self.picker.choose(MODELS[cell[0]][0], EFFORTS[cell[1]])

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        m, eff = self.picker.store.skill_cfg(self.picker.skill)
        ei = EFFORTS.index(eff)
        w = (self.width() - self.COL0) / len(EFFORTS)
        p.setFont(T.font("mono", 7))
        for c, e in enumerate(EFFORTS):
            p.setPen(T.qc(T.ACCENT2 if c == ei else T.MUTED))
            p.drawText(QRectF(self.COL0 + c * w, 0, w, 18), Qt.AlignCenter, e.upper())
        for r, (key, name, _, _) in enumerate(MODELS):
            y = 22 + r * 34
            sel = key == m["key"]
            p.setFont(T.font("mono", 8, 600, 1.5))
            p.setPen(T.qc(T.ACCENT if sel else T.MUTED))
            p.drawText(QRectF(0, y, self.COL0, 28), Qt.AlignVCenter, name.upper())
            if sel:
                p.setPen(Qt.NoPen)
                p.setBrush(T.qc(T.ACCENT))
                p.drawRoundedRect(QRectF(self.COL0 + 2, y, w * (ei + 1) - 4, 28), 14, 14)
            for c in range(len(EFFORTS)):
                cx, cy = self.COL0 + c * w + w / 2, y + 14
                p.setPen(Qt.NoPen)
                if sel and c == ei:
                    p.setBrush(T.qc("#f4fbff"))
                    p.drawEllipse(QPointF(cx, cy), 10, 10)
                elif self.hover == (r, c):
                    p.setBrush(T.qc(T.ACCENT2))
                    p.drawEllipse(QPointF(cx, cy), 4.5, 4.5)
                else:
                    p.setBrush(T.qc(T.INK, 0.5) if sel and c < ei else T.qc(T.MUTED))
                    p.drawEllipse(QPointF(cx, cy), 2, 2)


class SkillCard(QFrame):
    def __init__(self, store: Store, skill: dict, on_open, on_remove) -> None:
        super().__init__()
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 9, 10, 9)
        lay.setSpacing(5)
        name = QLabel(f"<span style='color:{T.ACCENT2}'>⚡</span> /{skill['name']}")
        name.setFont(T.font("mono", 9, 600))
        name.setToolTip(skill["prompt"])
        m, e = store.skill_cfg(skill)
        meta = QLabel(f"<span style='color:{T.ACCENT2}'><b>{m['label'].upper()}</b></span> <span style='color:{T.ACCENT}'>· {e.upper()}</span>")
        meta.setFont(T.font("mono", 7.5, 500, 1))
        acts = QHBoxLayout()
        acts.setSpacing(6)
        play = icon_button("play", f"Level and run /{skill['name']}", T.ACCENT, 20)
        play.setStyleSheet(f"padding:0; border:1px solid {T.LINE2};")
        rm = icon_button("x", f"Remove /{skill['name']}", T.MUTED, 20)
        rm.setStyleSheet(f"padding:0; border:1px solid {T.LINE};")
        play.clicked.connect(lambda: on_open(skill, play))
        rm.clicked.connect(lambda: on_remove(skill))
        acts.addWidget(play)
        acts.addWidget(rm)
        acts.addStretch(1)
        lay.addWidget(name)
        lay.addWidget(meta)
        lay.addLayout(acts)


class SkillsPanel(Panel):
    def __init__(self, store: Store, run_skill) -> None:
        self.add_btn = mini_button("+ Add skill", accent=True)
        super().__init__("bolt", "Skills Deck", self.add_btn)
        self.store, self.run_skill = store, run_skill
        self.grid = QGridLayout()
        self.grid.setSpacing(8)
        self.lay.addLayout(self.grid)
        self.add_btn.clicked.connect(self._add)
        store.changed.connect(lambda s: s == "skills" and self.render())
        self.render()

    def render(self) -> None:
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        for i, s in enumerate(self.store.skills):
            self.grid.addWidget(SkillCard(self.store, s, self._open, lambda s: self.store.remove_skill(s["id"])), i // 2, i % 2)
        if not self.store.skills:
            self.grid.addWidget(label("No skills yet. Add one, or ask Jarvis to.", "Muted"), 0, 0)

    def _open(self, skill: dict, anchor: QWidget) -> None:
        pk = SkillPicker(self.window(), self.store, skill)
        pk.run.connect(self.run_skill)
        g = self.mapToGlobal(self.rect().topLeft())
        pk.move(g.x() + (self.width() - pk.width()) // 2, g.y() + 44)
        pk.show()

    def _add(self) -> None:
        d = FormDialog(self.window(), "Add skill", [
            ("name", "Name", "e.g. newsletter", None, ""),
            ("prompt", "Instructions for Jarvis", "e.g. Draft this week's newsletter from my notes and save it as a note", None, ""),
            ("model", "Model", "", [(m[0], m[1]) for m in MODELS], "sonnet"),
            ("effort", "Effort", "", [(e, e.title()) for e in EFFORTS], "medium")])
        if d.exec():
            v = d.values()
            self.store.add_skill(v["name"], v["prompt"], v["model"], v["effort"])


# --------------------------------------------------------------------------- right: routines
class RoutinesPanel(Panel):
    def __init__(self, store: Store, run_routine) -> None:
        self.add_btn = mini_button("+ Add")
        super().__init__("clock", "Routines", self.add_btn)
        self.store, self.run_routine = store, run_routine
        head = QHBoxLayout()
        for txt, stretch in (("TIME", 0), ("ROUTINE", 1), ("STATUS", 0)):
            l = label(txt, "Lbl")
            l.setMinimumWidth(56 if txt == "TIME" else 0)
            head.addWidget(l, stretch)
        self.lay.addLayout(head)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(2)
        self.lay.addLayout(self.rows)
        # add form
        self.form = QWidget()
        fl = QGridLayout(self.form)
        fl.setContentsMargins(0, 6, 0, 0)
        self.time_in = QTimeEdit(QTime.currentTime())
        self.time_in.setDisplayFormat("HH:mm")
        self.name_in = QLineEdit()
        self.name_in.setPlaceholderText("Routine name")
        self.prompt_in = QLineEdit()
        self.prompt_in.setPlaceholderText("What should Jarvis do? (optional)")
        ok = QPushButton("Add")
        ok.setObjectName("Primary")
        fl.addWidget(self.time_in, 0, 0)
        fl.addWidget(self.name_in, 0, 1)
        fl.addWidget(ok, 0, 2)
        fl.addWidget(self.prompt_in, 1, 0, 1, 3)
        self.form.hide()
        self.lay.addWidget(self.form)
        self.add_btn.clicked.connect(lambda: self.form.setVisible(not self.form.isVisible()))
        ok.clicked.connect(self._add)
        self.name_in.returnPressed.connect(self._add)
        store.changed.connect(lambda s: s == "routines" and self.render())
        self.render()

    def _add(self) -> None:
        name = self.name_in.text().strip()
        if not name:
            self.name_in.setFocus()
            return
        self.store.add_routine(self.time_in.time().toString("HH:mm"), name, self.prompt_in.text().strip())
        self.name_in.clear()
        self.prompt_in.clear()
        self.form.hide()

    def render(self) -> None:
        while self.rows.count():
            w = self.rows.takeAt(0).widget()
            if w:
                w.deleteLater()
        cur = datetime.now().strftime("%H:%M")
        today = day_key()
        rs = self.store.routines
        nxt = next((r for r in rs if r["time"] > cur), None)
        for r in rs:
            ran = self.store.data["routine_runs"].get(r["id"]) == today
            past = r["time"] <= cur
            status = "DONE" if ran else "NEXT" if r is nxt else "MISSED" if past else "QUEUED"
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 2, 0, 2)
            tm = QLabel(r["time"])
            tm.setFont(T.font("mono", 8.5, 600))
            tm.setFixedWidth(52)
            tm.setAlignment(Qt.AlignCenter)
            is_next = r is nxt
            tm.setStyleSheet(f"background:{T.ACCENT}; color:{T.INK}; padding:2px;" if is_next else f"border:1px solid {T.LINE}; padding:2px;")
            faded = (past or ran) and not is_next
            name = QPushButton(r["name"])
            name.setToolTip("Run now: " + r["prompt"])
            name.setCursor(Qt.PointingHandCursor)
            name.setStyleSheet(f"QPushButton {{ border:none; text-align:left; font-family:'{T.Fonts.body}'; font-size:9.5pt; font-weight:600; letter-spacing:0px; padding:2px 4px; color:{T.DIM if faded else T.FG}; }}"
                               f"QPushButton:hover {{ color:{T.ACCENT}; background:transparent; }}")
            name.setFont(T.font("body", 9.5, 600))
            name.clicked.connect(lambda _=False, r=r: self.run_routine(r))
            st = QLabel(status)
            st.setFont(T.font("mono", 7.5, 600, 1))
            st.setStyleSheet(f"color:{T.ACCENT if is_next else T.MUTED}")
            rm = QPushButton("×")
            rm.setObjectName("Flat")
            rm.setToolTip("Remove routine")
            rm.clicked.connect(lambda _=False, rid=r["id"]: self.store.remove_routine(rid))
            hl.addWidget(tm)
            hl.addWidget(name, 1)
            hl.addWidget(rm)
            hl.addWidget(st)
            if faded:
                tm.setStyleSheet(f"border:1px solid {T.LINE}; padding:2px; color:{T.DIM};")
                st.setStyleSheet(f"color:{T.DIM}")
            self.rows.addWidget(row)
        if not rs:
            self.rows.addWidget(label("No routines yet. Add one, or ask Jarvis to.", "Muted"))


# ══════════════════════════════════════════════════════════════════════════════
# APP WINDOWS — App windows: Jarvis, Second Brain (notes), Tasks, Calculator, Terminal, Settings.
# ══════════════════════════════════════════════════════════════════════════════
class AppWindow(QWidget):
    """A floating tool window in the NOMI style."""

    def __init__(self, parent, title: str, size: tuple[int, int]) -> None:
        super().__init__(parent, Qt.Window | Qt.Tool)
        self.setObjectName("AppWindow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"#AppWindow {{ background: {T.GLASS}; border: 1px solid {T.LINE2}; }}")
        self.setWindowTitle(f"{title} — NOMI")
        self.resize(*size)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(0)
        head = QLabel(title.upper())
        head.setFont(T.font("display", 9.5, 600, 3.5))
        head.setStyleSheet(f"color:{T.ACCENT2}; background:{T.PANEL2}; border-bottom:1px solid {T.LINE}; padding: 8px 14px;")
        self.lay.addWidget(head)
        QShortcut(QKeySequence("Esc"), self, activated=self.close)


# --------------------------------------------------------------------------- Jarvis
class JarvisWindow(AppWindow):
    def __init__(self, parent, store: Store, jarvis, voice) -> None:
        super().__init__(parent, "Jarvis", (520, 600))
        self.store, self.jarvis, self.voice = store, jarvis, voice
        bar = QHBoxLayout()
        bar.setContentsMargins(12, 8, 12, 8)
        self.status = QLabel()
        self.status.setFont(T.font("mono", 8))
        self.status.setStyleSheet(f"color:{T.MUTED}")
        self.vbtn = QPushButton()
        self.vbtn.setObjectName("Toggle")
        self.vbtn.setCheckable(True)
        self.vbtn.toggled.connect(lambda on: store.set_setting("voice_on", on) or (None if on else voice.stop()))
        clear = QPushButton("Clear memory")
        clear.clicked.connect(store.clear_turns)
        bar.addWidget(self.status, 1)
        bar.addWidget(self.vbtn)
        bar.addWidget(clear)
        self.lay.addLayout(bar)
        self.log = QTextBrowser()
        self.log.setOpenExternalLinks(True)
        self.log.setStyleSheet(f"QTextBrowser {{ border:none; border-top:1px solid {T.LINE}; border-bottom:1px solid {T.LINE}; padding:10px; font-size:10.5pt; }}")
        self.lay.addWidget(self.log, 1)
        row = QHBoxLayout()
        row.setContentsMargins(10, 10, 10, 10)
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Message Jarvis…")
        self.send = QPushButton("Send")
        self.send.setObjectName("Primary")
        row.addWidget(self.inp, 1)
        row.addWidget(self.send)
        self.lay.addLayout(row)
        self.live, self.live_err = "", ""
        self.inp.returnPressed.connect(self._send)
        self.send.clicked.connect(self._send)
        store.changed.connect(self._changed)
        jarvis.started.connect(lambda _: self._set_live("…", ""))
        jarvis.text.connect(lambda t: self._set_live(t, ""))
        jarvis.finished.connect(lambda *_: self._set_live("", ""))
        jarvis.failed.connect(lambda msg, partial: self._set_live("", msg))
        jarvis.busy_changed.connect(lambda _: self.render())
        self.render()
        self.inp.setFocus()

    def _changed(self, section: str) -> None:
        if section in ("turns", "settings"):
            self.render()

    def _send(self) -> None:
        if self.jarvis.busy:
            self.jarvis.stop()
            return
        t = self.inp.text().strip()
        self.inp.clear()
        self.jarvis.send(t)

    def _set_live(self, text: str, err: str) -> None:
        self.live, self.live_err = text, err
        self.render()

    def render(self) -> None:
        def bubble(role: str, text: str, extra: str = "") -> str:
            who = "YOU" if role == "user" else "JARVIS"
            color = T.MUTED if role == "user" else T.ACCENT
            align = "right" if role == "user" else "left"
            body = html.escape(text).replace("\n", "<br>")
            return (f"<div align='{align}' style='margin:0 0 14px 0;'><span style='font-size:8pt;letter-spacing:2px;color:{color};font-weight:600'>{who}</span><br>"
                    f"<span style='{extra}'>{body}</span></div>")
        parts = []
        if not self.store.turns and not self.live:
            parts.append(bubble("assistant", "Jarvis 4.0 online. Tell me what you need, or run a skill from the deck."))
        for t in self.store.turns:
            parts.append(bubble(t["role"], t["content"]))
        if self.jarvis.busy and self.live:
            parts.append(bubble("assistant", "Processing…" if self.live == "…" else self.live, f"color:{T.MUTED}" if self.live == "…" else ""))
        if self.live_err:
            parts.append(f"<div style='color:{T.WARN};font-size:9pt'>{html.escape(self.live_err)}</div>")
        self.log.setHtml("".join(parts))
        self.log.moveCursor(QTextCursor.End)
        on = self.store.settings.get("voice_on", True)
        self.vbtn.blockSignals(True)
        self.vbtn.setChecked(on)
        self.vbtn.blockSignals(False)
        self.vbtn.setText("Voice on" if on else "Voice off")
        self.status.setText("Processing…" if self.jarvis.busy else ("Neural link online" if not self.jarvis.problem() else "Not connected — see Settings"))
        self.send.setText("Stop" if self.jarvis.busy else "Send")


# --------------------------------------------------------------------------- Notes
class NotesWindow(AppWindow):
    def __init__(self, parent, store: Store) -> None:
        super().__init__(parent, "Second Brain", (700, 460))
        self.store = store
        self.cur = store.notes[0]["id"] if store.notes else None
        split = QSplitter()
        split.setStyleSheet(f"QSplitter::handle {{ background:{T.LINE}; width:1px; }}")
        self.list = QListWidget()
        self.list.setMinimumWidth(180)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 8, 8, 8)
        row = QHBoxLayout()
        new, dele = QPushButton("New note"), QPushButton("Delete")
        row.addWidget(new)
        row.addWidget(dele)
        row.addStretch(1)
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("Start writing…")
        self.edit.setStyleSheet("QPlainTextEdit { border:none; font-size: 11pt; }")
        rl.addLayout(row)
        rl.addWidget(self.edit, 1)
        split.addWidget(self.list)
        split.addWidget(right)
        split.setSizes([200, 500])
        self.lay.addWidget(split, 1)
        self._typing = False
        self._bumped = False
        self.list.currentItemChanged.connect(self._pick)
        self.edit.textChanged.connect(self._typed)
        new.clicked.connect(self.new_note)
        dele.clicked.connect(self._delete)
        store.changed.connect(lambda s: s == "notes" and not self._typing and self.render())
        self.render()

    def focus_note(self, nid) -> None:
        self.cur = nid
        self.render()

    def new_note(self) -> None:
        n = self.store.add_note("Untitled", "")
        self.cur = n["id"]
        self.render()
        self.edit.setFocus()

    def _delete(self) -> None:
        if self.cur is not None:
            self.store.delete_note(self.cur)
            self.cur = self.store.notes[0]["id"] if self.store.notes else None
            self.render()

    def _pick(self, item, _prev) -> None:
        if item is not None and not self._typing:
            self.cur = item.data(Qt.UserRole)
            self._load()

    def _load(self) -> None:
        n = next((x for x in self.store.notes if x["id"] == self.cur), None)
        self.edit.blockSignals(True)
        self.edit.setPlainText(n["body"] if n else "")
        self.edit.setEnabled(n is not None)
        self.edit.blockSignals(False)

    def _typed(self) -> None:
        if self.cur is None:
            return
        self._typing = True
        self.store.update_note(self.cur, self.edit.toPlainText())
        if not self._bumped:
            self._bumped = True
            self.store.bump()
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(Qt.UserRole) == self.cur:
                n = next(x for x in self.store.notes if x["id"] == self.cur)
                it.setText(f"{n['title']}\n{datetime.fromtimestamp(n['t'] / 1000).strftime('%b %d')}")
        self._typing = False

    def render(self) -> None:
        if self.cur is None or not any(n["id"] == self.cur for n in self.store.notes):
            self.cur = self.store.notes[0]["id"] if self.store.notes else None
        self.list.blockSignals(True)
        self.list.clear()
        for n in self.store.notes:
            it = QListWidgetItem(f"{n['title'] or 'Untitled'}\n{datetime.fromtimestamp(n['t'] / 1000).strftime('%b %d')}")
            it.setData(Qt.UserRole, n["id"])
            self.list.addItem(it)
            if n["id"] == self.cur:
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        self._load()


# --------------------------------------------------------------------------- Tasks
class TasksWindow(AppWindow):
    def __init__(self, parent, store: Store) -> None:
        super().__init__(parent, "Tasks", (420, 480))
        self.store = store
        body = QVBoxLayout()
        body.setContentsMargins(14, 14, 14, 14)
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Add a task and press Enter")
        self.count = QLabel()
        self.count.setObjectName("Lbl")
        self.items = QVBoxLayout()
        self.items.setSpacing(0)
        body.addWidget(self.inp)
        body.addWidget(self.count)
        body.addLayout(self.items)
        body.addStretch(1)
        self.lay.addLayout(body, 1)
        self.inp.returnPressed.connect(self._add)
        store.changed.connect(lambda s: s == "todos" and self.render())
        self.render()

    def _add(self) -> None:
        t = self.inp.text().strip()
        if t:
            self.store.add_task(t)
            self.inp.clear()

    def render(self) -> None:
        while self.items.count():
            w = self.items.takeAt(0).widget()
            if w:
                w.deleteLater()
        for t in self.store.todos:
            row = QWidget()
            row.setStyleSheet(f"border-bottom:1px solid {T.LINE};")
            hl = QHBoxLayout(row)
            hl.setContentsMargins(2, 6, 2, 6)
            cb = QCheckBox(t["text"])
            cb.setChecked(t["done"])
            cb.setStyleSheet(f"border:none; font-size:10.5pt; {'color:' + T.MUTED + '; text-decoration: line-through;' if t['done'] else ''}")
            cb.toggled.connect(lambda on, tid=t["id"]: self.store.set_task_done(tid, on))
            rm = QPushButton("×")
            rm.setObjectName("Flat")
            rm.setStyleSheet("border:none; font-size:13pt;")
            rm.setToolTip("Delete task")
            rm.clicked.connect(lambda _=False, tid=t["id"]: self.store.delete_task(tid))
            hl.addWidget(cb, 1)
            hl.addWidget(rm)
            self.items.addWidget(row)
        open_ = sum(not t["done"] for t in self.store.todos)
        self.count.setText(f"{open_} OPEN · {len(self.store.todos) - open_} DONE")


# --------------------------------------------------------------------------- Calculator
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod, ast.USub: operator.neg, ast.UAdd: operator.pos}


def safe_eval(expr: str) -> float:
    """Arithmetic only: numbers, + - * / % ** and brackets."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        raise ValueError("not arithmetic")
    return ev(ast.parse(expr, mode="eval"))


class CalcWindow(AppWindow):
    KEYS = ["C", "±", "⌫", "÷", "7", "8", "9", "×", "4", "5", "6", "−", "1", "2", "3", "+", "0", ".", "%", "="]

    def __init__(self, parent) -> None:
        super().__init__(parent, "Calculator", (320, 440))
        self.expr, self.last = "", ""
        body = QVBoxLayout()
        body.setContentsMargins(12, 12, 12, 12)
        self.top = QLabel()
        self.top.setAlignment(Qt.AlignRight)
        self.top.setStyleSheet(f"color:{T.MUTED}")
        self.main = QLabel("0")
        self.main.setAlignment(Qt.AlignRight)
        self.main.setFont(T.font("mono", 24, 500))
        scr = QWidget()
        scr.setStyleSheet(f"background: rgba(3,8,15,0.85); border:1px solid {T.LINE};")
        sl = QVBoxLayout(scr)
        sl.addWidget(self.top)
        sl.addWidget(self.main)
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, k in enumerate(self.KEYS):
            b = QPushButton(k)
            b.setMinimumHeight(46)
            style = f"font-size:14pt; font-family:'{T.Fonts.mono}'; background:{T.PANEL2}; border:1px solid {T.LINE};"
            if k in "÷×−+%":
                style += f"color:{T.ACCENT};"
            if k == "=":
                style = f"font-size:14pt; background:{T.ACCENT}; color:{T.INK}; border:none;"
            b.setStyleSheet(style)
            b.clicked.connect(lambda _=False, k=k: self.press(k))
            grid.addWidget(b, i // 4, i % 4)
        body.addWidget(scr)
        body.addLayout(grid, 1)
        self.lay.addLayout(body, 1)

    def press(self, k: str) -> None:
        if k == "C":
            self.expr, self.last = "", ""
        elif k == "⌫":
            self.expr = self.expr[:-1]
        elif k == "±":
            self.expr = self.expr[1:] if self.expr.startswith("-") else "-" + self.expr
        elif k == "=":
            try:
                v = safe_eval(self.expr.replace("×", "*").replace("÷", "/").replace("−", "-").replace("%", "/100"))
                self.last = self.expr + " ="
                self.expr = f"{v:.10g}"
            except Exception:
                self.last = "Error"
        else:
            self.expr += k
        self.main.setText(self.expr or "0")
        self.top.setText(self.last)

    def keyPressEvent(self, e) -> None:
        m = {Qt.Key_Return: "=", Qt.Key_Enter: "=", Qt.Key_Backspace: "⌫", Qt.Key_Delete: "C"}
        ch = {"*": "×", "/": "÷", "-": "−"}.get(e.text(), e.text())
        if e.key() in m:
            self.press(m[e.key()])
        elif ch and ch in "0123456789.+×÷−%=":
            self.press(ch)
        else:
            super().keyPressEvent(e)


# --------------------------------------------------------------------------- Terminal
class TerminalWindow(AppWindow):
    def __init__(self, parent, store: Store, host) -> None:
        super().__init__(parent, "Terminal", (620, 380))
        self.store, self.host = store, host
        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setStyleSheet(f"QPlainTextEdit {{ background:#01040a; border:none; color:#b8dcff; font-family:'{T.Fonts.mono}'; font-size:10pt; }}")
        row = QHBoxLayout()
        row.setContentsMargins(10, 4, 10, 8)
        prompt = QLabel("you@myos:~$")
        prompt.setFont(T.font("mono", 10))
        prompt.setStyleSheet(f"color:{T.ACCENT}")
        self.inp = QLineEdit()
        self.inp.setStyleSheet(f"border:none; background:transparent; font-family:'{T.Fonts.mono}'; font-size:10pt;")
        row.addWidget(prompt)
        row.addWidget(self.inp, 1)
        wrap = QWidget()
        wrap.setStyleSheet("background:#01040a;")
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(self.out, 1)
        wl.addLayout(row)
        self.lay.addWidget(wrap, 1)
        self.hist: list[str] = []
        self.hi = 0
        self.inp.returnPressed.connect(self._run)
        self.write("NOMI shell. Type 'help' to see what I can do.")
        self.inp.setFocus()

    def write(self, text: str) -> None:
        self.out.appendPlainText(text)

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key_Up and self.hi > 0:
            self.hi -= 1
            self.inp.setText(self.hist[self.hi])
        elif e.key() == Qt.Key_Down:
            self.hi = min(len(self.hist), self.hi + 1)
            self.inp.setText(self.hist[self.hi] if self.hi < len(self.hist) else "")
        else:
            super().keyPressEvent(e)

    def _run(self) -> None:
        line = self.inp.text()
        self.inp.clear()
        self.hist.append(line)
        self.hi = len(self.hist)
        self.write(f"you@myos:~$ {line}")
        cmd, _, arg = line.strip().partition(" ")
        if not cmd:
            return
        s, h = self.store, self.host
        cmd = cmd.lower()
        if cmd == "help":
            out = "Commands: help, actions, undo, reminders, apps, open <app>, close <app>, map, ls, cat <n>, todo, todo add <text>, skills, run <skill>, routines, jarvis <message>, say <text>, date, whoami, neofetch, clear"
        elif cmd == "actions":
            out = "\n".join(f"{r.name:<18}{'[plugin] ' if r.source == 'plugin' else ''}{r.description[:70]}" for r in h.registry.records.values())
        elif cmd == "apps":
            out = "\n".join(f"{k:<10}{v}" for k, v in h.app_list())
        elif cmd == "open":
            out = f"Opening {arg}…" if h.open_app(arg) else f"open: unknown app '{arg}'. Try 'apps'."
        elif cmd == "close":
            h.close_app(arg)
            out = f"Closed {arg}."
        elif cmd == "map":
            h.open_app("map")
            out = "Opening system map…"
        elif cmd == "ls":
            out = "\n".join(f"{i + 1}.  {n['title']}" for i, n in enumerate(s.notes)) or "(no notes)"
        elif cmd == "cat":
            try:
                out = s.notes[int(arg) - 1]["body"]
            except Exception:
                out = f"cat: no note {arg}. Try 'ls'."
        elif cmd == "todo":
            if arg.startswith("add "):
                s.add_task(arg[4:])
                out = "Added."
            else:
                out = "\n".join(("[x] " if t["done"] else "[ ] ") + t["text"] for t in s.todos) or "(empty)"
        elif cmd == "skills":
            out = "  ".join("/" + x["name"] for x in s.skills) or "(none)"
        elif cmd == "run":
            sk = next((x for x in s.skills if x["name"] == arg.lstrip("/")), None)
            if sk:
                h.run_skill(sk)
                out = f"Running /{sk['name']}…"
            else:
                out = f"run: no skill '{arg}'. Try 'skills'."
        elif cmd == "routines":
            out = "\n".join(f"{r['time']}  {r['name']}" for r in s.routines) or "(none)"
        elif cmd == "jarvis":
            h.ask(arg) if arg else None
            out = "Transmitted to Jarvis." if arg else "usage: jarvis <message>"
        elif cmd == "say":
            h.say(arg)
            out = "Speaking…" if arg else "usage: say <text>"
        elif cmd == "undo":
            out = undo_stack.undo()
        elif cmd == "reminders":
            out = "\n".join(f"{datetime.fromtimestamp(r['due'] / 1000):%a %H:%M}  {r['text']}" for r in sorted(s.reminders, key=lambda r: r["due"])) or "(none)"
        elif cmd == "date":
            out = datetime.now().astimezone().strftime("%A %d %B %Y, %H:%M:%S %Z")
        elif cmd == "whoami":
            out = f"{s.settings.get('name', 'Nominjin')} — commander of this system"
        elif cmd == "neofetch":
            out = (f"    /\\       NOMI · Agentic OS (Python)\n   /  \\      --------------------------\n"
                   f"  / /\\ \\     Core: J.A.R.V.I.S 4.0\n /_/  \\_\\    Python {platform.python_version()} · {platform.system()}\n"
                   f"             Notes: {len(s.notes)}  Tasks: {len(s.todos)}  Skills: {len(s.skills)}")
        elif cmd == "clear":
            self.out.clear()
            return
        else:
            out = f"{cmd}: command not found"
        self.write(out)


# --------------------------------------------------------------------------- Settings
class SettingsWindow(AppWindow):
    def __init__(self, parent, store: Store, voice, wake, jarvis, dashboard=None) -> None:
        super().__init__(parent, "Settings", (460, 720))
        self.store, self.voice, self.wake_word, self.dashboard = store, voice, wake, dashboard
        ears = wake.ears
        body = QVBoxLayout()
        body.setContentsMargins(16, 14, 16, 16)
        body.setSpacing(8)

        def lbl(t):
            l = QLabel(t.upper())
            l.setObjectName("Lbl")
            body.addWidget(l)

        lbl("Your name")
        self.name = QLineEdit(cfg.get_user_name())
        self.name.textChanged.connect(lambda t: store.set_setting("user_name", t.strip() or "Nominjin"))
        body.addWidget(self.name)

        lbl("Family name (shown before your name)")
        self.family = QLineEdit(cfg.get_family_name())
        self.family.textChanged.connect(lambda t: store.set_setting("family_name", t.strip()))
        body.addWidget(self.family)

        lbl("Jarvis")
        st = QLabel(jarvis.problem() or f"Connected to Claude ({jarvis.client and 'API key loaded'}).")
        st.setWordWrap(True)
        st.setStyleSheet(f"color:{T.WARN if jarvis.problem() else T.OK}")
        body.addWidget(st)

        lbl("Voice")
        row = QHBoxLayout()
        self.von = QPushButton()
        self.von.setObjectName("Toggle")
        self.von.setCheckable(True)
        self.von.setChecked(store.settings.get("voice_on", True))
        self.von.toggled.connect(self._voice_on)
        test = QPushButton("▶ Test voice")
        test.clicked.connect(self._test)
        row.addWidget(self.von)
        row.addWidget(test)
        row.addStretch(1)
        body.addLayout(row)
        if not voice.available:
            note = QLabel("No speech engine found. On Linux install espeak-ng (sudo apt install espeak-ng).")
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{T.WARN}")
            body.addWidget(note)
        lbl("Jarvis's voice")
        self.vsel = QComboBox()
        self.vsel.currentIndexChanged.connect(lambda i: i >= 0 and self.vsel.itemData(i) is not None and store.set_setting("voice", self.vsel.itemData(i)))
        body.addWidget(self.vsel)
        lbl("Speed")
        sr = QHBoxLayout()
        self.rate = QSlider(Qt.Horizontal)
        self.rate.setRange(70, 140)
        self.rate.setValue(int(store.settings.get("rate", 1.0) * 100))
        self.rate_v = QLabel()
        self.rate_v.setFixedWidth(46)
        self.rate.valueChanged.connect(self._rate)
        sr.addWidget(self.rate, 1)
        sr.addWidget(self.rate_v)
        body.addLayout(sr)
        self._rate(self.rate.value())

        lbl("Microphone")
        self.wake = QCheckBox("Listen for “Hey Jarvis” in the background")
        self.wake.setChecked(wake.on)
        self.wake.setEnabled(ears.available())
        self.wake.toggled.connect(lambda on: parent.set_wake(on))
        body.addWidget(self.wake)
        mic_note = QLabel("Speech is turned into text by Google's free recognizer, so your voice is sent to Google. Typing never is."
                          if ears.available() else "No microphone support. Install SpeechRecognition and PyAudio (see readme.md).")
        mic_note.setWordWrap(True)
        mic_note.setStyleSheet(f"color:{T.MUTED}")
        body.addWidget(mic_note)

        lbl("Phone dashboard")
        self.dash = QCheckBox("Control NOMI from your phone (same Wi-Fi)")
        self.dash.setChecked(bool(dashboard and dashboard.running))
        self.dash.setEnabled(dashboard is not None)
        self.dash_info = QLabel()
        self.dash_info.setWordWrap(True)
        self.dash_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.dash.toggled.connect(self._dashboard)
        body.addWidget(self.dash)
        body.addWidget(self.dash_info)
        self._dash_text()

        lbl("Storage")
        self.reset = QPushButton("Reset NOMI")
        self.confirm = QWidget()
        cl = QHBoxLayout(self.confirm)
        cl.setContentsMargins(0, 0, 0, 0)
        cancel, erase = QPushButton("Cancel"), QPushButton("Erase everything")
        erase.setObjectName("Danger")
        cl.addWidget(QLabel("Erase notes, tasks, skills, routines and memory?"), 1)
        cl.addWidget(cancel)
        cl.addWidget(erase)
        self.confirm.hide()
        self.reset.clicked.connect(lambda: self.confirm.setVisible(True))
        cancel.clicked.connect(lambda: self.confirm.setVisible(False))
        erase.clicked.connect(lambda: (store.reset(), self.confirm.hide(), parent.center.set_user(cfg.get_user_name(), cfg.get_family_name())))
        body.addWidget(self.reset, 0, Qt.AlignLeft)
        body.addWidget(self.confirm)
        body.addStretch(1)
        about = QLabel(f"{APP_NAME} {VERSION} · Agentic OS · Jarvis · Data: ~/.nomi")
        about.setStyleSheet(f"color:{T.MUTED}")
        body.addWidget(about)
        self.lay.addLayout(body, 1)
        self._voice_label()
        QTimer.singleShot(300, self.fill_voices)
        QTimer.singleShot(2500, self.fill_voices)  # voices load in the background

    def _dashboard(self, on: bool) -> None:
        if self.dashboard is None:
            return
        cfg.save_dashboard_enabled(on)
        self.dashboard.start() if on else self.dashboard.stop()
        self._dash_text()

    def _dash_text(self) -> None:
        d = self.dashboard
        if d is None:
            self.dash_info.setText("Not available.")
        elif d.running:
            self.dash_info.setText(f"Open <b>{d.url}</b> on your phone and enter the code <b style='color:{T.ACCENT}'>{d.code}</b>. "
                                   "Anyone on your network with the code can use NOMI, so turn this off when you're done.")
        else:
            self.dash_info.setText(f"<span style='color:{T.MUTED}'>Off. Turn it on to see the address and access code.</span>")

    def fill_voices(self) -> None:
        cur = self.store.settings.get("voice", "")
        self.vsel.blockSignals(True)
        self.vsel.clear()
        vs = sorted(self.voice.voices, key=lambda v: (not v["lang"].lower().startswith("en"), v["name"]))
        if not vs:
            self.vsel.addItem("Default voice", "")
        for v in vs:
            self.vsel.addItem(f"{v['name']} · {v['lang']}", v["name"])
        i = self.vsel.findData(cur)
        self.vsel.setCurrentIndex(max(0, i))
        self.vsel.blockSignals(False)

    def _rate(self, v: int) -> None:
        self.rate_v.setText(f"{v / 100:.2f}×")
        self.store.set_setting("rate", v / 100)

    def _voice_label(self) -> None:
        self.von.setText("Spoken replies: on" if self.von.isChecked() else "Spoken replies: off")

    def _voice_on(self, on: bool) -> None:
        self.store.set_setting("voice_on", on)
        if not on:
            self.voice.stop()
        self._voice_label()

    def _test(self) -> None:
        if not self.von.isChecked():
            self.von.setChecked(True)
        self.voice.say(f"Good {greeting_word()}, {self.store.settings.get('name', 'Nominjin')}. Jarvis voice systems are online.", interrupt=True)


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM MAP — System Map: every app, routine, skill and memory in NOMI drawn as rings around Jarvis.
# ══════════════════════════════════════════════════════════════════════════════
CATS = {"note": "Notes", "task": "Tasks", "chat": "Conversations", "day": "Activity"}


class SystemMap(QWidget):
    closed = Signal()

    def __init__(self, parent, store, host) -> None:
        super().__init__(parent)
        self.store, self.host = store, host
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"background:{T.BG};")
        self.dot, self.spread, self.labels = 1.6, 1.0, True
        self.focus_key = None
        self.hover_key = None
        self.t = 0.0
        rnd = random.Random(3)
        self.stars = [(rnd.random(), rnd.random() * 6.283) for _ in range(140)]
        self._build_panel()
        self.timer = QTimer(self, interval=40)
        self.timer.timeout.connect(self._tick)
        self.refresh()

    # ------------------------------------------------------------------ data
    def refresh(self) -> None:
        s, h = self.store, self.host
        self.ents = []
        for key, name, icon_name in h.app_entries():
            self.ents.append({"key": f"app:{key}", "ring": "app", "name": name, "type": "Application", "icon": icon_name, "act": lambda k=key: h.open_app(k)})
        for c in s.custom_apps:
            self.ents.append({"key": f"capp:{c['id']}", "ring": "app", "name": c["name"], "type": "Micro app", "icon": "app", "act": lambda c=c: h.ask(c["prompt"], c["name"])})
        for r in s.routines:
            self.ents.append({"key": f"rt:{r['id']}", "ring": "routine", "name": f"{r['time']} {r['name']}", "type": "Routine", "act": lambda r=r: h.run_routine(r)})
        for sk in s.skills:
            self.ents.append({"key": f"sk:{sk['id']}", "ring": "skill", "name": "/" + sk["name"], "type": "Skill", "act": lambda sk=sk: h.run_skill(sk)})
        self.mem = []
        for n in s.notes:
            self.mem.append({"key": f"note:{n['id']}", "cat": "note", "name": n["title"] or "Untitled", "type": "Note",
                             "w": min(1, 0.25 + len(n["body"]) / 1200), "act": lambda n=n: h.open_note(n["id"])})
        for t in s.todos:
            self.mem.append({"key": f"task:{t['id']}", "cat": "task", "name": t["text"], "type": "Task · " + ("done" if t["done"] else "open"),
                             "w": 0.3 if t["done"] else 0.55, "act": lambda: h.open_app("tasks")})
        turns = s.turns
        for i in range(0, len(turns), 2):
            if turns[i]["role"] == "user":
                ans = turns[i + 1]["content"] if i + 1 < len(turns) else ""
                self.mem.append({"key": f"chat:{i}", "cat": "chat", "name": turns[i]["content"][:80], "type": "Conversation",
                                 "w": min(1, 0.3 + len(ans) / 900), "act": lambda: h.open_app("jarvis")})
        for k in sorted(s.data["activity"])[-28:]:
            v = s.data["activity"][k]
            self.mem.append({"key": f"day:{k}", "cat": "day", "name": f"{k} · {v} actions", "type": "Activity", "w": min(1, 0.2 + v / 10), "act": None})
        self._results()
        self._layout()

    # ------------------------------------------------------------------ side panel
    def _build_panel(self) -> None:
        self.panel = QFrame(self)
        self.panel.setFixedWidth(290)
        pl = QVBoxLayout(self.panel)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(10)
        top = QHBoxLayout()
        back = QPushButton("← BACK TO THE OS")
        jv = QPushButton("≡ JARVIS")
        for b in (back, jv):
            b.setStyleSheet(f"border:1.5px solid {T.ACCENT}; padding:8px 12px; background:#030a14; font-weight:700;")
        back.clicked.connect(self.close_map)
        jv.clicked.connect(lambda: (self.close_map(), self.host.open_app("jarvis")))
        top.addStretch(1)
        top.addWidget(back)
        top.addWidget(jv)
        pl.addLayout(top)
        box = QFrame()
        box.setStyleSheet(f"QFrame {{ background: rgba(6,14,26,0.94); border:1px solid {T.LINE}; }}")
        bl = QVBoxLayout(box)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search the system…")
        self.search.setStyleSheet(f"border:1.5px solid {T.ACCENT};")
        self.search.textChanged.connect(self._search)
        self.search.returnPressed.connect(self._open_focused)
        self.results = QListWidget()
        self.results.setFixedHeight(220)
        self.results.setStyleSheet("QListWidget { border:none; } QListWidget::item { padding:5px 4px; border:none; }")
        self.results.itemClicked.connect(self._pick)
        self.results.itemDoubleClicked.connect(self._open_item)
        bl.addWidget(self.search)
        bl.addWidget(self.results)
        pl.addWidget(box)
        ctl = QFrame()
        ctl.setStyleSheet(f"QFrame {{ background: rgba(6,14,26,0.94); border:1px solid {T.LINE}; }} QLabel {{ border:none; }}")
        cl = QVBoxLayout(ctl)

        def slider(name, lo, hi, val, cb):
            head = QHBoxLayout()
            l = QLabel(name.upper())
            l.setObjectName("Lbl")
            v = QLabel()
            v.setFont(T.font("mono", 8))
            head.addWidget(l, 1)
            head.addWidget(v)
            s = QSlider(Qt.Horizontal)
            s.setRange(lo, hi)
            s.setValue(val)
            s.valueChanged.connect(lambda x: (cb(x), v.setText(f"{x / 100:.2f}")))
            v.setText(f"{val / 100:.2f}")
            cl.addLayout(head)
            cl.addWidget(s)
            return s

        self.s_dot = slider("Dot size", 80, 300, 160, lambda x: self._set("dot", x / 100))
        self.s_spread = slider("Ring spread", 60, 160, 100, lambda x: self._set("spread", x / 100))
        two = QHBoxLayout()
        ex, co = QPushButton("Expand all"), QPushButton("Collapse all")
        ex.clicked.connect(lambda: self._set("labels", True))
        co.clicked.connect(lambda: self._set("labels", False))
        two.addWidget(ex)
        two.addWidget(co)
        cl.addLayout(two)
        rs = QPushButton("Reset settings")
        rs.setStyleSheet(f"color:{T.ACCENT}; border-color:{T.ACCENT};")
        rs.clicked.connect(lambda: (self.s_dot.setValue(160), self.s_spread.setValue(100), self._set("labels", True)))
        cl.addWidget(rs, 0, Qt.AlignLeft)
        leg = QLabel("&nbsp;&nbsp;".join(f"<span style='color:{T.CAT_COLORS[k]}'>●</span> {v}" for k, v in CATS.items()))
        leg.setTextFormat(Qt.RichText)
        leg.setStyleSheet(f"color:{T.MUTED}; font-size:8pt;")
        cl.addWidget(leg)
        pl.addWidget(ctl)
        pl.addStretch(1)

    def _set(self, k: str, v) -> None:
        setattr(self, k, v)
        self._layout()

    def _all(self) -> list:
        return self.ents + self.mem

    def _results(self) -> None:
        q = self.search.text().strip().lower()
        items = [e for e in self._all() if q in e["name"].lower() or q in e["type"].lower()] if q else self.ents
        self.results.clear()
        for e in items[:40]:
            color = T.CAT_COLORS.get(e.get("cat"), "#ffffff" if e.get("ring") == "skill" else T.ACCENT2 if e.get("ring") == "routine" else T.ACCENT)
            it = QListWidgetItem(f"■  {e['name']}    ·  {e['type'].split(' ·')[0]}")
            it.setForeground(T.qc(T.FG))
            it.setData(Qt.UserRole, e["key"])
            it.setToolTip("Click to find · double-click to open")
            self.results.addItem(it)
            if e["key"] == self.focus_key:
                self.results.setCurrentItem(it)
        if not items:
            self.results.addItem(QListWidgetItem("Nothing matches."))

    def _search(self) -> None:
        q = self.search.text().strip().lower()
        m = [e for e in self._all() if q and q in e["name"].lower()]
        self.focus_key = m[0]["key"] if len(m) == 1 else None
        self._results()
        self.update()

    def _find(self, key):
        return next((e for e in self._all() if e["key"] == key), None)

    def _pick(self, item) -> None:
        k = item.data(Qt.UserRole)
        self.focus_key = None if self.focus_key == k else k
        self.update()

    def _open_item(self, item) -> None:
        e = self._find(item.data(Qt.UserRole))
        if e and e["act"]:
            self.close_map()
            e["act"]()

    def _open_focused(self) -> None:
        q = self.search.text().strip().lower()
        e = self._find(self.focus_key) or next((x for x in self._all() if q and q in x["name"].lower()), None)
        if e and e["act"]:
            self.close_map()
            e["act"]()

    # ------------------------------------------------------------------ show / hide
    def open_map(self) -> None:
        self.refresh()
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self.timer.start()
        self.search.setFocus()

    def close_map(self) -> None:
        self.timer.stop()
        self.hide()
        self.closed.emit()

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key_Escape:
            self.close_map()
        else:
            super().keyPressEvent(e)

    def resizeEvent(self, _e) -> None:
        self._layout()

    def _tick(self) -> None:
        self.t += 0.004
        self.update()

    # ------------------------------------------------------------------ geometry
    def _layout(self) -> None:
        W, H = self.width(), self.height()
        side = 310
        self.panel.setGeometry(W - side, 16, 290, H - 32)
        self.cx, self.cy = (W - side) / 2, H / 2
        R = max(140, min((W - side) / 2, H / 2) - 40)
        sp = self.spread
        self.r = {"app": R, "routine": R * 0.88, "mem_out": R * 0.78, "mem_in": R * max(0.26, 0.32 / sp),
                  "skill": R * min(0.24, 0.2 * sp)}

        def place(items, rad, offset):
            n = max(1, len(items))
            for i, e in enumerate(items):
                a = -math.pi / 2 + offset + 2 * math.pi * i / n
                e["pos"] = QPointF(self.cx + math.cos(a) * rad, self.cy + math.sin(a) * rad)

        place([e for e in self.ents if e["ring"] == "app"], self.r["app"], math.pi / max(8, len(self.ents)))
        place([e for e in self.ents if e["ring"] == "routine"], self.r["routine"], 0.35)
        place([e for e in self.ents if e["ring"] == "skill"], self.r["skill"], 0.5)
        # memory sectors
        cats = [c for c in CATS if any(m["cat"] == c for m in self.mem)]
        tot = sum(max(3, sum(m["cat"] == c for m in self.mem)) for c in cats) or 1
        gap = 0.06
        a = -math.pi / 2 + gap
        span_all = 2 * math.pi - gap * len(cats)
        self.sectors, self.arcs = [], []
        d = self.dot
        for c in cats:
            items = [m for m in self.mem if m["cat"] == c]
            a1 = a + span_all * max(3, len(items)) / tot
            self.sectors.append({"cat": c, "a0": a, "a1": a1, "mid": (a + a1) / 2})
            avail = self.r["mem_out"] - self.r["mem_in"]
            step = max(d * 2.4, avail / max(1, len(items)))
            row_gap = d * 3.6 / self.spread
            for i, m in enumerate(items):
                rr = self.r["mem_in"] + step * (i + 0.5)
                if rr > self.r["mem_out"]:
                    break
                rows = max(1, min(14, int(step // row_gap)))
                span = (a1 - a) * max(0.3, min(1, 0.35 + m["w"] * 0.65))
                rowdef = []
                for j in range(rows):
                    rj = rr - step / 2 + (j + 0.5) * step / rows
                    spj = span * (1 - 0.45 * (j / max(1, rows)) * (1 if i % 2 else 0.6))
                    rowdef.append((rj, a + spj, max(3, int(spj * rj / (d * 3.2)))))
                self.arcs.append({"m": m, "r": rr, "a0": a, "a1": a + span, "band": step / 2, "rows": rowdef})
            a = a1 + gap
        self.update()

    def _hit(self, pos: QPointF):
        for e in self.ents:
            if "pos" in e and (pos - e["pos"]).manhattanLength() < (24 if e["ring"] == "app" else 12):
                return e
        dx, dy = pos.x() - self.cx, pos.y() - self.cy
        r, ang = math.hypot(dx, dy), math.atan2(dy, dx)
        for A in self.arcs:
            if abs(r - A["r"]) > A["band"]:
                continue
            t = ang
            while t < A["a0"]:
                t += 2 * math.pi
            while t > A["a0"] + 2 * math.pi:
                t -= 2 * math.pi
            if t <= A["a1"]:
                return A["m"]
        return None

    def mouseMoveEvent(self, e) -> None:
        hit = self._hit(e.position())
        self.hover_key = hit["key"] if hit else None
        self.setCursor(Qt.PointingHandCursor if hit and hit["act"] else Qt.ArrowCursor)
        if hit:
            QToolTip.showText(e.globalPosition().toPoint(), f"{hit['type'].upper()}\n{hit['name']}" + ("\nClick to open" if hit["act"] else ""), self)
        else:
            QToolTip.hideText()
        self.update()

    def mousePressEvent(self, e) -> None:
        hit = self._hit(e.position())
        if hit and hit["act"]:
            self.close_map()
            hit["act"]()
        elif math.hypot(e.position().x() - self.cx, e.position().y() - self.cy) < self.r["skill"] * 0.8:
            self.close_map()
            self.host.focus_command()

    # ------------------------------------------------------------------ drawing
    def _label(self, p: QPainter, text: str, x: float, y: float, color: str, size: float) -> None:
        p.setFont(T.font("display", size, 600, 1.5))
        p.setPen(T.qc(color))
        p.drawText(QRectF(x - 200, y - 12, 400, 24), Qt.AlignCenter, text)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QRadialGradient(QPointF(self.cx, self.cy), max(self.width(), self.height()) * 0.7)
        bg.setColorAt(0, T.qc("#06142a"))
        bg.setColorAt(1, T.qc("#010307"))
        p.fillRect(self.rect(), bg)
        cx, cy, r, t, d = self.cx, self.cy, self.r, self.t, self.dot
        # constellation
        p.setPen(QPen(T.qc(T.ACCENT2, 0.035), 1))
        pts = [QPointF(cx + math.cos(a + t * 0.2) * k * r["mem_out"], cy + math.sin(a + t * 0.2) * k * r["mem_out"]) for k, a in self.stars]
        for i, pt in enumerate(pts):
            p.drawLine(pt, pts[(i * 7 + 3) % len(pts)])
        g = QRadialGradient(QPointF(cx, cy), r["mem_out"] * 1.05)
        g.setColorAt(0, T.qc(T.ACCENT, 0.10))
        g.setColorAt(1, T.qc(T.ACCENT, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(cx, cy), r["mem_out"] * 1.05, r["mem_out"] * 1.05)
        # rings
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(T.qc(T.ACCENT, 0.55), 1.5))
        p.drawEllipse(QPointF(cx, cy), r["app"], r["app"])
        p.setPen(QPen(T.qc(T.ACCENT2, 0.55), 1.5))
        p.drawEllipse(QPointF(cx, cy), r["routine"], r["routine"])
        beads = int(r["routine"] * 2 * math.pi / 34)
        for i in range(beads):
            a = i / beads * 2 * math.pi + t * 0.3
            p.drawEllipse(QPointF(cx + math.cos(a) * r["routine"], cy + math.sin(a) * r["routine"]), 4.5, 4.5)
        # memory arcs
        for A in self.arcs:
            m = A["m"]
            on = self.focus_key is None or m["key"] == self.focus_key
            hot = m["key"] in (self.hover_key, self.focus_key)
            col = T.CAT_COLORS[m["cat"]]
            p.setPen(Qt.NoPen)
            for rj, a1, n in A["rows"]:
                for i in range(n):
                    a = A["a0"] + (a1 - A["a0"]) * (i / max(1, n - 1))
                    tw = 0.75 + 0.25 * math.sin(t * 6 + i * 0.7 + rj)
                    p.setBrush(T.qc(col, (1 if on else 0.12) * tw * (1 - 0.55 * i / n)))
                    rad = d * (1.4 if hot else 1) * (1 - 0.45 * i / n)
                    p.drawEllipse(QPointF(cx + math.cos(a) * rj, cy + math.sin(a) * rj), rad, rad)
        for s in self.sectors:
            x, y = cx + math.cos(s["mid"]) * r["mem_in"] * 0.78, cy + math.sin(s["mid"]) * r["mem_in"] * 0.78
            p.setBrush(T.qc(T.CAT_COLORS[s["cat"]]))
            p.drawEllipse(QPointF(x, y), 5, 5)
            if self.labels:
                self._label(p, CATS[s["cat"]].upper(), x, y + 15, "#e6f4ff", 8)
        # skills ring + core
        g2 = QRadialGradient(QPointF(cx, cy), r["skill"])
        g2.setColorAt(0, T.qc(T.ACCENT, 0.35))
        g2.setColorAt(1, T.qc(T.ACCENT, 0))
        p.setBrush(g2)
        p.drawEllipse(QPointF(cx, cy), r["skill"], r["skill"])
        p.setBrush(Qt.NoBrush)
        for k in range(4):
            pen = QPen(T.qc("#ffffff", 0.18), 1)
            pen.setDashPattern([2, 5 + k])
            p.setPen(pen)
            rr = r["skill"] * (0.55 + k * 0.15)
            p.drawEllipse(QPointF(cx, cy), rr, rr)
        p.setPen(QPen(T.qc(T.ACCENT2), 1.5))
        p.setBrush(T.qc("#03101e"))
        p.drawEllipse(QPointF(cx, cy), 9, 9)
        p.setPen(Qt.NoPen)
        p.setBrush(T.qc(T.ACCENT))
        p.drawEllipse(QPointF(cx, cy), 3.5, 3.5)
        self._label(p, "JARVIS", cx, cy + 22, "#e6f4ff", 8.5)
        # ring entities
        for e in self.ents:
            if "pos" not in e:
                continue
            pos, hot = e["pos"], e["key"] in (self.hover_key, self.focus_key)
            if e["ring"] == "app":
                s = 21 if hot else 19
                hexagon = QPolygonF([QPointF(pos.x() + s * math.cos(math.pi / 6 + k * math.pi / 3), pos.y() + s * math.sin(math.pi / 6 + k * math.pi / 3)) for k in range(6)])
                p.setPen(QPen(T.qc(T.ACCENT), 2))
                p.setBrush(T.qc("#081a30"))
                p.drawPolygon(hexagon)
                p.drawPixmap(QRectF(pos.x() - 9, pos.y() - 9, 18, 18), pixmap(e["icon"], "#ffffff" if hot else "#cfe9ff", 36), QRectF(0, 0, 36, 36))
            else:
                skill = e["ring"] == "skill"
                rad = (6.5 if skill else 8) * (1.25 if hot else 1)
                p.setPen(QPen(T.qc("#ffffff" if skill else T.ACCENT2), 2))
                p.setBrush(T.qc(T.ACCENT2 if hot else "#05121f"))
                p.drawEllipse(pos, rad, rad)
        if self.labels:
            self._label(p, "APPLICATIONS", cx, cy - r["app"] - 30, T.ACCENT, 12)
            self._label(p, "ROUTINES", cx, cy - r["routine"] + 22, T.ACCENT2, 11)
            self._label(p, "MEMORY", cx, cy - r["mem_out"] + 16, "#8a96ff", 11)
            self._label(p, "SKILLS", cx, cy - r["skill"] - 14, "#e6f4ff", 9)
        p.end()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW — Dashboard: the NOMI main window — panels, particle core, command bar, reply panel, boot screen.
# ══════════════════════════════════════════════════════════════════════════════
APPS = {
    "jarvis": {"name": "Jarvis", "desc": "Full conversation with your assistant", "icon": "jarvis"},
    "notes": {"name": "Second Brain", "desc": "Notes that Jarvis can read and write", "icon": "notes"},
    "tasks": {"name": "Tasks", "desc": "Your to-do list", "icon": "tasks"},
    "calc": {"name": "Calculator", "desc": "Quick sums, keyboard friendly", "icon": "calc"},
    "term": {"name": "Terminal", "desc": "Command line for NOMI", "icon": "term"},
    "settings": {"name": "Settings", "desc": "Voice, microphone, storage", "icon": "settings"},
    "map": {"name": "System Map", "desc": "Everything in NOMI as rings", "icon": "map"},
}


class ReplyPanel(QFrame):
    """Jarvis's latest answer, floating above the command bar."""

    def __init__(self, parent, on_replay, on_open) -> None:
        super().__init__(parent)
        self.setObjectName("Glass")
        self.setFixedWidth(620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 12, 12)
        lay.setSpacing(4)
        head = QHBoxLayout()
        t = QLabel("JARVIS")
        t.setFont(T.font("display", 8, 600, 4))
        t.setStyleSheet(f"color:{T.ACCENT}")
        replay = icon_button("spk_on", "Read aloud again", T.ACCENT2)
        replay.setStyleSheet("border:none; padding:0;")
        close = icon_button("x", "Close", T.MUTED)
        close.setStyleSheet("border:none; padding:0;")
        replay.clicked.connect(on_replay)
        close.clicked.connect(self.hide)
        head.addWidget(t, 1)
        head.addWidget(replay)
        head.addWidget(close)
        lay.addLayout(head)
        self.q = QLabel()
        self.q.setFont(T.font("mono", 8.5))
        self.q.setStyleSheet(f"color:{T.MUTED}")
        self.q.setWordWrap(True)
        self.a = QLabel()
        self.a.setWordWrap(True)
        self.a.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.a.setFont(T.font("body", 11))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.a)
        self.scroll.setMaximumHeight(260)
        self.err = QLabel()
        self.err.setStyleSheet(f"color:{T.WARN}")
        self.err.setWordWrap(True)
        self.note = QLabel()
        self.note.setStyleSheet(f"color:{T.MUTED}; font-size:8pt;")
        self.note.setWordWrap(True)
        more = QPushButton("Open full conversation →")
        more.setObjectName("Flat")
        more.setStyleSheet(f"color:{T.ACCENT}; border:none; text-align:left; padding:2px 0;")
        more.clicked.connect(on_open)
        for w in (self.q, self.scroll, self.err, self.note):
            lay.addWidget(w)
        lay.addWidget(more, 0, Qt.AlignLeft)
        self.hide_timer = QTimer(self, singleShot=True, interval=25000)
        self.hide_timer.timeout.connect(lambda: not self.underMouse() and self.hide())
        self.answer = ""

    def show_msg(self, q: str, a: str, wait: bool = False, err: str = "", note: str = "") -> None:
        self.q.setText("› " + q)
        self.answer = "" if wait else a
        self.a.setText("Processing…" if wait else a)
        self.a.setStyleSheet(f"color:{T.MUTED}" if wait else "")
        self.err.setText(err)
        self.err.setVisible(bool(err))
        self.note.setText(note)
        self.note.setVisible(bool(note))
        self.a.setFixedWidth(self.width() - 40)
        self.scroll.setFixedHeight(min(260, self.a.heightForWidth(self.width() - 40) + 6))
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())
        self.hide_timer.stop()

    def settle(self) -> None:
        self.hide_timer.start()

    def reposition(self) -> None:
        par = self.parent()
        w = min(620, par.width() - 32)
        self.setFixedWidth(w)
        self.adjustSize()
        self.move((par.width() - w) // 2, par.height() - 62 - self.height() - 12)


class BootScreen(QWidget):
    """Short start-up sequence; click or press a key to skip."""

    LINES = ["Initializing particle core", "Mounting micro apps", "Loading skills deck", "Scheduling routines",
             "Establishing neural link", "All systems online"]

    def __init__(self, parent, on_done) -> None:
        super().__init__(parent)
        self.on_done = on_done
        self.n = 0
        self.setGeometry(parent.rect())
        self.timer = QTimer(self, interval=260)
        self.timer.timeout.connect(self._step)
        self.timer.start()
        self.setFocusPolicy(Qt.StrongFocus)

    def _step(self) -> None:
        self.n += 1
        self.update()
        if self.n > len(self.LINES) + 1:
            self.finish()

    def finish(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self.hide()
            self.deleteLater()
            self.on_done()

    def mousePressEvent(self, _e) -> None:
        self.finish()

    def keyPressEvent(self, _e) -> None:
        self.finish()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), T.qc("#02050a"))
        w = min(520, self.width() - 40)
        x, y = (self.width() - w) / 2, self.height() / 2 - 130
        p.setFont(T.font("display", 24, 700, 8))
        p.setPen(T.qc(T.FG))
        p.drawText(QRectF(x, y, w, 40), Qt.AlignLeft, "NOMI")
        p.setFont(T.font("mono", 8.5, 500, 4))
        p.setPen(T.qc(T.ACCENT))
        p.drawText(QRectF(x, y + 42, w, 20), Qt.AlignLeft, "AGENTIC OS · J.A.R.V.I.S 4.0 · PYTHON")
        p.setFont(T.font("mono", 10))
        for i, line in enumerate(self.LINES[: self.n]):
            yy = y + 80 + i * 24
            p.setPen(T.qc(T.ACCENT2))
            p.drawText(QRectF(x, yy, w, 22), Qt.AlignLeft, "› " + line + (" … " if i < len(self.LINES) - 1 else ""))
            if i < len(self.LINES) - 1:
                p.setPen(T.qc(T.OK))
                p.drawText(QRectF(x + p.fontMetrics().horizontalAdvance("› " + line + " … "), yy, 40, 22), Qt.AlignLeft, "OK")
        by = y + 80 + len(self.LINES) * 24 + 12
        p.fillRect(QRectF(x, by, w, 2), T.qc(T.ACCENT, 0.15))
        p.fillRect(QRectF(x, by, w * min(1, self.n / len(self.LINES)), 2), T.qc(T.ACCENT))
        p.setFont(T.font("mono", 8.5))
        p.setPen(T.qc(T.MUTED))
        p.drawText(QRectF(x, by + 12, w, 20), Qt.AlignLeft, "Click or press any key to skip")


class NomiUI(QMainWindow):
    def __init__(self, registry, dashboard=None) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.registry, self.dashboard = registry, dashboard
        try:
            from config import ICON_PATH
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        except Exception:
            pass
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self.store = Store()
        self.voice = Voice(self.store)
        self.ears = Ears(self.voice)
        self.wake = WakeWord(self.ears, self.voice)
        self.hotkey = Hotkey()
        self.jarvis = Jarvis(self.store, self.voice, self, registry)
        confirm_gate.set_parent(self)
        registry.bind(store=self.store, host=self, voice=self.voice, confirm=confirm_gate.ask, undo=undo_stack,
                      speak=lambda text: self.voice.say(text))
        self.windows: dict[str, QWidget] = {}
        self.mode = "standby"

        self.desk = QWidget()
        self.desk.setObjectName("Desk")
        self.setCentralWidget(self.desk)
        root = QVBoxLayout(self.desk)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        cols = QHBoxLayout()
        cols.setSpacing(0)
        root.addLayout(cols, 1)

        # left column
        self.micro = MicroAppsPanel(self.store, {k: v for k, v in APPS.items()}, self.open_app, lambda c: self.ask(c["prompt"], c["name"]))
        self.cal = CalendarPanel()
        self.momentum = MomentumPanel(self.store)
        cols.addWidget(self._column([self.micro, self.cal, self.momentum], "ColL"))
        # center
        self.center = CenterView()
        self.center.talk.connect(self.focus_command)
        tools = QHBoxLayout()
        tools.addStretch(1)
        for name, tip, cb in (("pencil", "New note", self.new_note), ("search", "Ask Jarvis (/)", self.focus_command),
                              ("grid", "Conversation", lambda: self.open_app("jarvis")), ("map", "System map", lambda: self.open_app("map")),
                              ("info", "Settings", lambda: self.open_app("settings"))):
            b = icon_button(name, tip, T.MUTED, 22)
            b.setStyleSheet("border:none; padding:0;")
            b.clicked.connect(cb)
            tools.addWidget(b)
        tools.addStretch(1)
        self.center.tools_lay.addLayout(tools)
        cols.addWidget(self.center, 1)
        # right column
        self.tasks_panel = TasksPanel(self.store, lambda: self.open_app("tasks"))
        self.skills_panel = SkillsPanel(self.store, self.run_skill)
        self.routines_panel = RoutinesPanel(self.store, self.run_routine)
        cols.addWidget(self._column([self.tasks_panel, self.skills_panel, self.routines_panel], "ColR"))

        root.addWidget(self._command_bar())
        self.reply = ReplyPanel(self.desk, self.replay, lambda: (self.reply.hide(), self.open_app("jarvis")))
        self.reply.hide()
        self.map = SystemMap(self.desk, self.store, self)
        self.map.hide()

        self._wire()
        self._build_orbs()
        self.center.set_user(cfg.get_user_name(), cfg.get_family_name())
        self.clock = QTimer(self, interval=1000)
        self.clock.timeout.connect(self._tick)
        self.clock.start()
        self._tick()
        QApplication.instance().installEventFilter(self)
        QShortcut(QKeySequence("Ctrl+Space"), self, activated=self.listen)
        QShortcut(QKeySequence("Meta+Space"), self, activated=self.listen)
        if self.ears.available():
            if cfg.get_wake_word_enabled():
                self.set_wake(True, announce=False)
            if cfg.get_push_to_talk_global():
                self.hotkey.pressed.connect(self.listen)
                self.hotkey.start_global()
        self.reminder_timer = QTimer(self, interval=5000)
        self.reminder_timer.timeout.connect(self._check_reminders)
        self.reminder_timer.start()
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._undo)
        log(f"🖥 Dashboard ready ({len(APPS)} apps, {len(self.store.skills)} skills, {len(self.store.routines)} routines)", "UI")
        if self.ears.available():
            log("🎤 Mic ready (Ctrl+Space to talk)")
        self.boot = BootScreen(self.desk, self._booted)
        self.boot.show()
        self.boot.setFocus()

    # ------------------------------------------------------------------ layout pieces
    def _column(self, panels, name: str) -> QScrollArea:
        inner = QWidget()
        inner.setObjectName("Col")
        inner.setFixedWidth(322)
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        for p in panels:
            v.addWidget(p)
        v.addStretch(1)
        sa = QScrollArea()
        sa.setObjectName(name)
        sa.setWidget(inner)
        sa.setWidgetResizable(True)
        sa.setFixedWidth(330)
        sa.setStyleSheet(f"QScrollArea#{name} {{ background:{T.PANEL}; border:none; {'border-right' if name == 'ColL' else 'border-left'}:1px solid {T.LINE}; }}")
        return sa

    def _command_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("CmdBar")
        bar.setFixedHeight(62)
        h = QHBoxLayout(bar)
        h.setContentsMargins(14, 0, 14, 0)
        self.task_strip = QHBoxLayout()
        self.task_strip.setSpacing(4)
        strip = QWidget()
        strip.setLayout(self.task_strip)
        strip.setFixedWidth(300)
        h.addWidget(strip)
        box = QFrame()
        box.setObjectName("CmdBox")
        box.setMaximumWidth(680)
        box.setFixedHeight(44)
        bl = QHBoxLayout(box)
        bl.setContentsMargins(12, 0, 6, 0)
        bl.setSpacing(8)
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color:{T.ACCENT}; font-size:9pt;")
        self.cmd = QLineEdit()
        self.cmd.setPlaceholderText("Ask Jarvis anything…" + ("  (Ctrl+Space to talk)" if self.ears.available() else ""))
        self.cmd.returnPressed.connect(self._submit)
        kbd = QLabel("/")
        kbd.setStyleSheet(f"color:{T.MUTED}; border:1px solid {T.LINE}; padding:0 6px; font-family:'{T.Fonts.mono}';")
        kbd.setFixedHeight(20)
        self.mic_btn = icon_button("mic", "Talk to Jarvis (Ctrl+Space)", T.ACCENT2, 26)
        self.mic_btn.setStyleSheet("border:none; padding:0;")
        self.mic_btn.clicked.connect(self.listen)
        self.mic_btn.setVisible(self.ears.available())
        self.wake_btn = QPushButton("HEY J")
        self.wake_btn.setObjectName("Wake")
        self.wake_btn.setCheckable(True)
        self.wake_btn.setToolTip("Listen for “Hey Jarvis” in the background")
        self.wake_btn.toggled.connect(self._toggle_wake)
        self.wake_btn.setVisible(self.ears.available())
        self.spk_btn = icon_button("spk_on", "Mute Jarvis", T.ACCENT2, 26)
        self.spk_btn.setStyleSheet("border:none; padding:0;")
        self.spk_btn.clicked.connect(lambda: self.store.set_setting("voice_on", not self.store.settings.get("voice_on", True)))
        self.send_btn = QPushButton("SEND")
        self.send_btn.setObjectName("Primary")
        self.send_btn.clicked.connect(self._submit)
        for w in (self.dot, self.cmd, kbd, self.mic_btn, self.wake_btn, self.spk_btn, self.send_btn):
            bl.addWidget(w, 1 if w is self.cmd else 0)
        h.addWidget(box, 1)
        self.tray = QLabel()
        self.tray.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.tray.setFont(T.font("mono", 8.5))
        self.tray.setStyleSheet(f"color:{T.MUTED}")
        self.tray.setFixedWidth(300)
        h.addWidget(self.tray)
        return bar

    def _build_orbs(self) -> None:
        orbs = []

        def add(icon_name, tip, cb, skill=False):
            o = OrbButton(icon_name, tip, skill)
            o.clicked.connect(cb)
            orbs.append(o)
            return o

        for k, a in APPS.items():
            o = add(a["icon"], a["name"], lambda _=False, k=k: self.open_app(k))
            o.active = k in self.windows and self.windows[k].isVisible()
        for s in self.store.skills:
            add("bolt", f"/{s['name']}", lambda _=False, s=s: self.run_skill(s), True)
        for c in self.store.custom_apps:
            add("app", c["name"], lambda _=False, c=c: self.ask(c["prompt"], c["name"]))
        for r in self.store.routines[:4]:
            add("clock", f"{r['time']} {r['name']}", lambda _=False, r=r: self.run_routine(r))
        add("spark", "New idea", lambda: self.ask("Give me one surprising idea I could act on today, based on my notes and tasks.", "New idea"))
        add("globe", "World clocks", lambda: self.ask("What time is it in Ulaanbaatar, New York, London and Tokyo right now?", "World clocks"))
        self.center.set_orbs(orbs)

    # ------------------------------------------------------------------ wiring
    def _wire(self) -> None:
        s, j = self.store, self.jarvis
        s.changed.connect(self._store_changed)
        j.started.connect(lambda label: (self.reply.show_msg(label, "", wait=True), self._set_mode()))
        j.text.connect(lambda t: self.reply.show_msg(self.reply.q.text()[2:], t))
        j.finished.connect(lambda text, note: (self.reply.show_msg(self.reply.q.text()[2:], text, note=note), self.reply.settle()))
        j.failed.connect(lambda msg, partial: (self.reply.show_msg(self.reply.q.text()[2:], partial, err=msg if msg != "Stopped." else "",
                                                                   note="Stopped." if msg == "Stopped." else ""), self.reply.settle()))
        j.busy_changed.connect(lambda busy: (self.send_btn.setText("STOP" if busy else "SEND"),
                                            self.send_btn.setObjectName("Danger" if busy else "Primary"),
                                            self.send_btn.setStyle(self.send_btn.style()), self._set_mode()))
        self.voice.speaking.connect(lambda _: self._set_mode())
        self.ears.listening.connect(lambda on: (self.mic_btn.setIcon(icon("mic", T.WARN if on else T.ACCENT2)),
                                               self.cmd.setPlaceholderText("Listening… speak now" if on else "Ask Jarvis anything…  (Ctrl+Space to talk)"),
                                               self._set_mode(listening=on)))
        self.ears.heard.connect(self._heard)
        self.wake.wake.connect(lambda: (self.voice.say("Yes?", interrupt=True), QTimer.singleShot(800, self.listen)))
        self.wake.command.connect(lambda t: not self.jarvis.busy and self.jarvis.send(t))
        self.wake.stopped.connect(lambda _: self.set_wake(False, announce=False))
        self._render_speaker()

    def _store_changed(self, section: str) -> None:
        if section in ("skills", "routines", "apps"):
            self._build_orbs()
        if section == "settings":
            self.center.set_user(cfg.get_user_name(), cfg.get_family_name())
            self._render_speaker()

    def _render_speaker(self) -> None:
        on = self.store.settings.get("voice_on", True)
        self.spk_btn.setIcon(icon("spk_on" if on else "spk_off", T.ACCENT2 if on else T.MUTED))
        self.spk_btn.setToolTip("Jarvis speaks — click to mute" if on else "Jarvis is muted — click to unmute")
        if not on:
            self.voice.stop()

    def _set_mode(self, listening: bool | None = None) -> None:
        if listening is not None:
            self._listening = listening
        if getattr(self, "_listening", False):
            mode = "listening"
        elif self.jarvis.busy:
            mode = "thinking"
        elif self.voice.busy:
            mode = "speaking"
        else:
            mode = "standby"
        self.mode = mode
        self.center.set_state(mode)

    def _tick(self) -> None:
        now = datetime.now()
        self.cal.tick()
        self.tray.setText(f"{now.strftime('%H:%M')}\nNOMI 4.0")
        if now.second == 0:
            self.routines_panel.render()

    # ------------------------------------------------------------------ actions (the "host" Jarvis and the map call)
    def app_names(self) -> list[str]:
        return list(APPS)

    def app_list(self) -> list[tuple[str, str]]:
        return [(k, a["name"]) for k, a in APPS.items()]

    def app_entries(self) -> list[tuple[str, str, str]]:
        return [(k, a["name"], a["icon"]) for k, a in APPS.items() if k != "map"]

    def open_app(self, key: str) -> bool:
        key = (key or "").strip().lower()
        aliases = {"conversation": "jarvis", "chat": "jarvis", "second brain": "notes", "note": "notes", "todo": "tasks",
                   "calculator": "calc", "terminal": "term", "system map": "map", "settings": "settings"}
        key = aliases.get(key, key)
        if key == "map":
            self.reply.hide()
            self.map.open_map()
            return True
        if key not in APPS:
            return False
        w = self.windows.get(key)
        if w is None:
            if key == "jarvis":
                w = JarvisWindow(self, self.store, self.jarvis, self.voice)
            elif key == "notes":
                w = NotesWindow(self, self.store)
            elif key == "tasks":
                w = TasksWindow(self, self.store)
            elif key == "calc":
                w = CalcWindow(self)
            elif key == "term":
                w = TerminalWindow(self, self.store, self)
            else:
                w = SettingsWindow(self, self.store, self.voice, self.wake, self.jarvis, self.dashboard)
            w.setAttribute(Qt.WA_DeleteOnClose)
            w.destroyed.connect(lambda _=None, k=key: (self.windows.pop(k, None), self._render_strip(), self._build_orbs()))
            n = len(self.windows)
            g = self.geometry()
            w.move(g.x() + (g.width() - w.width()) // 2 + n * 30, g.y() + (g.height() - w.height()) // 2 + n * 24 - 30)
            self.windows[key] = w
        if key == "jarvis":
            self.reply.hide()
        w.show()
        w.raise_()
        w.activateWindow()
        self._render_strip()
        self._build_orbs()
        return True

    def close_app(self, key: str) -> None:
        keys = list(self.windows) if key == "all" else [key]
        for k in keys:
            w = self.windows.get(k)
            if w:
                w.close()
        if key in ("map", "all"):
            self.map.close_map()

    def _render_strip(self) -> None:
        while self.task_strip.count():
            w = self.task_strip.takeAt(0).widget()
            if w:
                w.deleteLater()
        for k in list(self.windows):
            b = icon_button(APPS[k]["icon"], APPS[k]["name"], T.ACCENT, 34)
            b.setStyleSheet(f"border:1px solid {T.LINE}; padding:0;")
            b.clicked.connect(lambda _=False, k=k: self.open_app(k))
            self.task_strip.addWidget(b)
        self.task_strip.addStretch(1)

    def open_note(self, nid) -> None:
        self.open_app("notes")
        self.windows["notes"].focus_note(nid)

    def new_note(self) -> None:
        self.open_app("notes")
        self.windows["notes"].new_note()

    def ask(self, text: str, label: str | None = None) -> None:
        self.jarvis.send(text, label)

    def run_skill(self, skill: dict) -> None:
        self.jarvis.send(skill["prompt"], "/" + skill["name"], skill)

    def run_routine(self, r: dict) -> None:
        if self.jarvis.busy:
            return
        self.store.mark_routine_run(r["id"])
        self.jarvis.send(r["prompt"] or r["name"], "Routine · " + r["name"])

    def say(self, text: str) -> None:
        self.voice.say(text, interrupt=True)

    def focus_command(self) -> None:
        self.activateWindow()
        self.cmd.setFocus()

    def replay(self) -> None:
        if not self.store.settings.get("voice_on", True):
            self.store.set_setting("voice_on", True)
        self.voice.say(self.reply.answer, interrupt=True)

    def listen(self) -> None:
        if self.ears.available():
            self.ears.listen_once()

    def _heard(self, r: dict) -> None:
        if r.get("text"):
            self.jarvis.send(r["text"])
            return
        msg = {"timeout": "I didn't hear anything.", "not_understood": "Sorry, I didn't catch that.",
               "offline": "Speech recognition needs an internet connection.", "no_mic": "I can't find a microphone."}.get(r.get("error"), "Microphone error.")
        self.reply.show_msg("Voice", msg)
        self.reply.settle()
        self.voice.say(msg)

    def _toggle_wake(self, on: bool) -> None:
        self.set_wake(on)

    def set_wake(self, on: bool, announce: bool = True) -> bool:
        """Turn the "Hey Jarvis" wake word on or off; keeps the button, Settings and config in step."""
        ok = self.wake.set(on)
        self.wake_btn.blockSignals(True)
        self.wake_btn.setChecked(ok)
        self.wake_btn.blockSignals(False)
        cfg.save_wake_word_enabled(ok)
        s = self.windows.get("settings")
        if s is not None:
            s.wake.blockSignals(True)
            s.wake.setChecked(ok)
            s.wake.blockSignals(False)
        if ok and announce:
            self.voice.say("Say Hey Jarvis whenever you need me.", interrupt=True)
        return ok

    def _check_reminders(self) -> None:
        now = now_ms()
        for r in [r for r in self.store.reminders if r["due"] <= now]:
            self.store.remove_reminder(r["id"])
            log(f"⏰ Reminder: {r['text']}")
            msg = f"{cfg.get_user_name()}, a reminder: {r['text']}."
            self.reply.show_msg("⏰ Reminder", msg)
            self.reply.settle()
            self.voice.say(msg, interrupt=not self.jarvis.busy)

    def _undo(self) -> None:
        fw = QApplication.focusWidget()
        if isinstance(fw, (QLineEdit, QPlainTextEdit, QTextEdit)) and not (fw is self.cmd and not self.cmd.text()):
            if isinstance(fw, QLineEdit):
                fw.undo()
            elif hasattr(fw, "undo"):
                fw.undo()
            return  # Ctrl+Z inside a text box undoes typing; on the empty command bar it undoes NOMI
        msg = undo_stack.undo()
        self.reply.show_msg("Undo", msg)
        self.reply.settle()

    def _submit(self) -> None:
        if self.jarvis.busy:
            self.jarvis.stop()
            return
        t = self.cmd.text().strip()
        self.cmd.clear()
        self.jarvis.send(t)

    def _booted(self) -> None:
        s = self.store
        open_n = sum(not t["done"] for t in s.todos)
        cur = datetime.now().strftime("%H:%M")
        nxt = next((r for r in s.routines if r["time"] > cur), None)
        msg = (f"Good {greeting_word()}, {s.settings.get('name', 'Nominjin')}. All systems are online. "
               f"You have {open_n} open task{'s' if open_n != 1 else ''}" + (f", and {nxt['name']} is next at {nxt['time']}" if nxt else "") + ". "
               + ("Press slash to talk to me." if not self.jarvis.problem() else self.jarvis.problem()))
        log("Briefing (greeting) sent.")
        self.reply.show_msg("System boot", msg)
        self.reply.settle()
        self.voice.say(msg)
        self.cmd.setFocus()

    # ------------------------------------------------------------------ events
    def eventFilter(self, obj: QObject, e: QEvent) -> bool:
        if e.type() == QEvent.KeyPress and e.text() == "/" and not e.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
            fw = QApplication.focusWidget()
            if not isinstance(fw, (QLineEdit, QPlainTextEdit, QTextEdit)):
                self.focus_command()
                return True
        return False

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if self.reply.isVisible():
            self.reply.reposition()
        if self.map.isVisible():
            self.map.setGeometry(self.desk.rect())
        if getattr(self, "boot", None) is not None:
            try:
                self.boot.setGeometry(self.desk.rect())
            except RuntimeError:
                pass

    def closeEvent(self, e) -> None:
        log("👋 Shutting down. Memory saved.")
        self.store.save_now()
        self.voice.stop()
        self.wake.set(False)
        self.hotkey.stop()
        if self.dashboard is not None:
            self.dashboard.stop()
        super().closeEvent(e)


MainWindow = NomiUI  # older name
