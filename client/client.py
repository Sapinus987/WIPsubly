"""
Subly Client — Interface PyQt5 légère

Ne charge aucun modèle IA. Se connecte au serveur Subly via WebSocket et
affiche les sous-titres traduits dans des fenêtres overlay.
"""
import os
import sys
import re
import json
import asyncio
import threading

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QSlider, QVBoxLayout, QHBoxLayout, QFrame, QSizeGrip, QComboBox,
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QRectF
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QPainterPath,
    QFontDatabase, QLinearGradient,
)

# ── Constantes ─────────────────────────────────────────────────────────────────
_BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
_TWITCH_RE  = re.compile(r"^[a-zA-Z0-9_]{1,25}$")
DEFAULT_URL = "ws://localhost:8765"

# ── Localisation UI ────────────────────────────────────────────────────────────
def _detect_ui_lang() -> str:
    """Retourne 'fr' si la langue système est française, 'en' sinon."""
    from PyQt5.QtCore import QLocale
    code = QLocale.system().name()          # ex: 'fr_FR', 'en_US', 'de_DE'
    return "fr" if code.startswith("fr") else "en"

_UI_STRINGS = {
    "fr": {
        "server":        "Serveur",
        "source_lang":   "Langue du stream",
        "trans_lang":    "Langue de traduction",
        "add_channel":   "Ajouter une chaîne",
        "placeholder":   "ex: b_a_s_y_a",
        "active":        "Sessions actives",
        "none":          "Aucune session",
        "text_size":     "Taille du texte",
        "stop_all":      "■  Tout arrêter",
        "status_idle":   "● Connecté · aucune session",
        "status_n":      "● Connecté · {n} session{s} active{s}",
        "connecting":    "Connexion...",
        "err_connect":   "Connexion impossible",
        "err_generic":   "Erreur",
    },
    "en": {
        "server":        "Server",
        "source_lang":   "Stream language",
        "trans_lang":    "Translation language",
        "add_channel":   "Add a channel",
        "placeholder":   "e.g. b_a_s_y_a",
        "active":        "Active sessions",
        "none":          "No session",
        "text_size":     "Text size",
        "stop_all":      "■  Stop all",
        "status_idle":   "● Connected · no session",
        "status_n":      "● Connected · {n} active session{s}",
        "connecting":    "Connecting...",
        "err_connect":   "Connection failed",
        "err_generic":   "Error",
    },
}

UI_LANG = _detect_ui_lang()

def tr(key: str, **kwargs) -> str:
    """Retourne la chaîne traduite pour la langue UI détectée."""
    s = _UI_STRINGS[UI_LANG].get(key, key)
    return s.format(**kwargs) if kwargs else s

# ── Palette ────────────────────────────────────────────────────────────────────
BG       = "#0e0e10"
CARD     = "#18181b"
PURPLE   = "#9147ff"
LILAC    = "#bf94ff"
PINK     = "#fc5db4"
FG       = "#efeff1"
FG_DIM   = "#7a6a9a"
CARD_BDR = "#4a2a6a"

SESSION_COLORS = [PURPLE, PINK, LILAC, "#e040fb"]
FONT = "Segoe UI"


def _load_fonts():
    global FONT
    for name in ("Nunito-Regular.ttf", "Nunito-SemiBold.ttf", "Nunito-Bold.ttf"):
        path = os.path.join(_BASE_DIR, "fonts", name)
        if os.path.exists(path):
            QFontDatabase.addApplicationFont(path)
            FONT = "Nunito"


# ══════════════════════════════════════════════════════════════════════════════
#  GradientButton
# ══════════════════════════════════════════════════════════════════════════════
class GradientButton(QPushButton):
    RADIUS = 10

    def __init__(self, text, c1, c2, text_color="#fff", border_color=None, parent=None):
        super().__init__(text, parent)
        self._c1     = QColor(c1)
        self._c2     = QColor(c2)
        self._tc     = QColor(text_color)
        self._border = QColor(border_color) if border_color else None
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        factor = 0.85 if self.isDown() else (1.1 if self.underMouse() else 1.0)
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0, self._c1.lighter(int(factor * 100)))
        g.setColorAt(1, self._c2.lighter(int(factor * 100)))
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.RADIUS, self.RADIUS)
        p.fillPath(path, QBrush(g))
        if self._border:
            p.setPen(QPen(self._border, 1))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        p.setPen(self._tc)
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignCenter, self.text())


# ══════════════════════════════════════════════════════════════════════════════
#  TrafficLight
# ══════════════════════════════════════════════════════════════════════════════
class TrafficLight(QWidget):
    SIZE = 11

    def __init__(self, color, action=None, parent=None):
        super().__init__(parent)
        self._color   = QColor(color)
        self._action  = action
        self._hovered = False
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.PointingHandCursor if action else Qt.ArrowCursor)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def enterEvent(self, _): self._hovered = True;  self.update()
    def leaveEvent(self, _): self._hovered = False; self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._action:
            self._action()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = self._color.lighter(130) if self._hovered and self._action else self._color
        p.setBrush(QBrush(c))
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, self.SIZE, self.SIZE)


# ══════════════════════════════════════════════════════════════════════════════
#  OverlayWindow
# ══════════════════════════════════════════════════════════════════════════════
class OverlayWindow(QWidget):
    RADIUS = 20

    def __init__(self, channel: str, font_size: int, accent: str = PURPLE):
        super().__init__()
        self.channel   = channel
        self.on_close  = None
        self._drag_pos = None
        self._accent   = QColor(accent)
        self._bg       = QColor(30, 15, 45, 242)

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(340, 70)
        self.resize(860, 95)
        self._build(font_size)

    def _build(self, font_size: int):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 8)
        root.setSpacing(0)

        bar = QWidget()
        bar.setFixedHeight(34)
        bar.setAttribute(Qt.WA_TranslucentBackground)
        bar.setCursor(Qt.SizeAllCursor)
        bar.mousePressEvent   = self._drag_press
        bar.mouseMoveEvent    = self._drag_move
        bar.mouseReleaseEvent = lambda _: setattr(self, "_drag_pos", None)

        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 0, 14, 0)
        bl.setSpacing(6)
        for color, action in [("#e63946", self._close),
                               ("#f4a261", self._toggle_opacity),
                               ("#7a6a9a", None)]:
            bl.addWidget(TrafficLight(color, action, bar))
        bl.addStretch()
        icon = QLabel("🦄")
        icon.setFont(QFont(FONT, 11))
        icon.setAttribute(Qt.WA_TranslucentBackground)
        bl.addWidget(icon)
        name = QLabel(self.channel)
        name.setFont(QFont(FONT, 11, QFont.DemiBold))
        name.setStyleSheet("color: #9a7abf; background: transparent;")
        bl.addWidget(name)
        bl.addStretch()
        bl.addSpacing(44)
        root.addWidget(bar)

        self.text_lbl = QLabel(f"[{self.channel}]  {tr('connecting')}")
        self.text_lbl.setFont(QFont(FONT, font_size))
        self.text_lbl.setStyleSheet(f"color: {FG}; background: transparent;")
        self.text_lbl.setWordWrap(True)
        self.text_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.text_lbl.setContentsMargins(16, 0, 16, 0)
        root.addWidget(self.text_lbl, 1)

        self.grip = QSizeGrip(self)
        self.grip.setStyleSheet("background: transparent;")
        self.grip.resize(16, 16)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.grip.move(self.width() - 16, self.height() - 16)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(0, 0, self.width(), self.height()), self.RADIUS, self.RADIUS)
        p.fillPath(path, self._bg)
        border = QColor(self._accent)
        border.setAlpha(77)
        p.setPen(QPen(border, 1))
        p.drawPath(path)

    def _drag_press(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def _drag_move(self, e):
        if self._drag_pos and e.buttons() == Qt.LeftButton:
            self.move(e.globalPos() - self._drag_pos)

    def _toggle_opacity(self):
        self.setWindowOpacity(0.35 if self.windowOpacity() > 0.5 else 0.93)

    def _close(self):
        self.hide()
        if self.on_close:
            self.on_close()

    def set_text(self, text: str):
        self.text_lbl.setText(text)

    def set_font_size(self, size: int):
        f = self.text_lbl.font()
        f.setPointSize(size)
        self.text_lbl.setFont(f)


# ══════════════════════════════════════════════════════════════════════════════
#  WebSocketSession — connexion WebSocket vers le serveur pour une chaîne
# ══════════════════════════════════════════════════════════════════════════════
# Langues source : label → (code Whisper, code DeepL source)
SOURCE_LANGUAGES = {
    "Русский":    ("ru", "RU"),
    "Українська": ("uk", "UK"),
    "English":    ("en", "EN"),
    "Français":   ("fr", "FR"),
}

# Langues cibles : label → code DeepL cible
TARGET_LANGUAGES = {
    "Français":   "FR",
    "English":    "EN-US",
    "Русский":    "RU",
    "Українська": "UK",
}

# Correspondance label source → label cible à exclure (même langue)
_SRC_TO_TGT_EXCLUDE = {
    "Русский":    "Русский",
    "Українська": "Українська",
    "English":    "English",
    "Français":   "Français",
}

class WebSocketSession(QObject):
    text_signal = pyqtSignal(str)

    def __init__(self, channel: str, index: int, font_size: int,
                 panel: "ControlPanel", server_url: str,
                 source_lang: str = "RU", target_lang: str = "FR"):
        super().__init__()
        self.channel      = channel
        self._panel       = panel
        self._server_url  = server_url
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._running     = True

        accent = SESSION_COLORS[index % len(SESSION_COLORS)]
        self.win = OverlayWindow(channel, font_size, accent)
        self.win.move(60, max(40, 820 - index * 140))
        self.win.setWindowOpacity(0.93)
        self.win.on_close = self._on_win_close
        self.win.show()

        self.text_signal.connect(self.win.set_text)
        threading.Thread(target=self._run, daemon=True).start()

    def _on_win_close(self):
        self.stop()
        self._panel.remove_session(self.channel)

    def _run(self):
        """Lance la boucle asyncio dans ce thread."""
        asyncio.run(self._connect())

    async def _connect(self):
        import websockets
        url = f"{self._server_url}/ws"
        try:
            async with websockets.connect(url) as ws:
                await ws.send(json.dumps({
                    "action": "start",
                    "channel": self.channel,
                    "source_lang": self._source_lang,
                    "target_lang": self._target_lang,
                }))
                while self._running:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        data = json.loads(raw)
                        if data.get("channel") == self.channel:
                            self.text_signal.emit(
                                f"[{self.channel}]  {data['text']}")
                    except asyncio.TimeoutError:
                        continue
                    except Exception as ex:
                        self.text_signal.emit(
                            f"[{self.channel}]  {tr('err_generic')} : {ex}")
                        break
                try:
                    await ws.send(json.dumps({"action": "stop", "channel": self.channel}))
                except Exception:
                    pass
        except Exception as ex:
            self.text_signal.emit(
                f"[{self.channel}]  {tr('err_connect')} ({self._server_url}) : {ex}")

    def set_font_size(self, size: int):
        self.win.set_font_size(size)

    def stop(self):
        self._running = False
        try:
            self.win.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  ControlPanel
# ══════════════════════════════════════════════════════════════════════════════
_PANEL_SS = """
QWidget { background: transparent; }
QLabel  { color: #efeff1; background: transparent; }
QLineEdit {
    background: #18181b; color: #efeff1;
    border: 1px solid #4a2a6a; border-radius: 10px;
    padding: 8px 12px; font-size: 10pt;
    selection-background-color: #9147ff;
}
QLineEdit:focus { border: 1px solid #9147ff; }
QSlider::groove:horizontal {
    height: 4px; background: #18181b; border-radius: 2px;
}
QSlider::handle:horizontal {
    background: white; border: 2px solid #9147ff;
    width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #9147ff, stop:1 #fc5db4);
    border-radius: 2px;
}
QFrame#sep { background: #26262c; max-height: 1px; border: none; }
"""


class ControlPanel(QWidget):
    RADIUS = 18

    def __init__(self):
        super().__init__()
        self._sessions: dict[str, WebSocketSession] = {}
        self._rows:     dict[str, QWidget]          = {}
        self._drag_pos  = None
        self._bg        = QColor(14, 14, 16, 255)

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Subly")
        self.setMinimumSize(290, 480)
        self.resize(330, 620)
        self.setStyleSheet(_PANEL_SS)
        self._build()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.RADIUS, self.RADIUS)
        p.fillPath(path, self._bg)
        p.setPen(QPen(QColor(CARD_BDR), 1))
        p.drawPath(path)

    def _drag_press(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def _drag_move(self, e):
        if self._drag_pos and e.buttons() == Qt.LeftButton:
            self.move(e.globalPos() - self._drag_pos)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 16)
        root.setSpacing(0)

        # ── Barre de titre ─────────────────────────────────────────────────
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setAttribute(Qt.WA_TranslucentBackground)
        bar.setCursor(Qt.SizeAllCursor)
        bar.mousePressEvent   = self._drag_press
        bar.mouseMoveEvent    = self._drag_move
        bar.mouseReleaseEvent = lambda _: setattr(self, "_drag_pos", None)

        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 0, 14, 0)
        bl.setSpacing(6)
        for color, action in [
            ("#e63946", self.close),
            ("#f4a261", self.showMinimized),
            ("#7a6a9a", None),
        ]:
            bl.addWidget(TrafficLight(color, action, bar))
        bl.addStretch()
        lbl = QLabel("🦄  Subly")
        lbl.setFont(QFont(FONT, 12, QFont.DemiBold))
        lbl.setStyleSheet(f"color: {FG};")
        bl.addWidget(lbl)
        bl.addStretch()
        bl.addSpacing(50)
        root.addWidget(bar)

        self._status_lbl = QLabel(tr("status_idle"))
        self._status_lbl.setFont(QFont(FONT, 9))
        self._status_lbl.setStyleSheet(f"color: {LILAC}; padding-left: 16px;")
        root.addWidget(self._status_lbl)
        root.addSpacing(12)

        # ── Zone de contenu ────────────────────────────────────────────────
        inner = QWidget()
        inner.setAttribute(Qt.WA_TranslucentBackground)
        cl = QVBoxLayout(inner)
        cl.setContentsMargins(16, 0, 16, 0)
        cl.setSpacing(0)

        # Serveur
        cl.addWidget(self._section("Serveur"))
        cl.addSpacing(5)
        self._server_input = QLineEdit()
        self._server_input.setPlaceholderText("ws://localhost:8765")
        self._server_input.setText("ws://localhost:8765")
        self._server_input.setFont(QFont(FONT, 10))
        cl.addWidget(self._server_input)
        cl.addSpacing(14)
        cl.addWidget(self._sep())
        cl.addSpacing(10)

        # Langue source + langue cible
        _combo_ss = f"""
            QComboBox {{
                background: #18181b; color: #efeff1;
                border: 1px solid #4a2a6a; border-radius: 10px;
                padding: 6px 12px; font-size: 10pt;
            }}
            QComboBox:focus {{ border: 1px solid #9147ff; }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox QAbstractItemView {{
                background: #18181b; color: #efeff1;
                selection-background-color: #9147ff;
                border: 1px solid #4a2a6a;
            }}
        """
        lang_row = QHBoxLayout()
        lang_row.setSpacing(8)

        src_col = QVBoxLayout()
        src_col.setSpacing(4)
        src_col.addWidget(self._section(tr("source_lang")))
        self._src_lang_box = QComboBox()
        self._src_lang_box.addItems(list(SOURCE_LANGUAGES.keys()))
        self._src_lang_box.setFont(QFont(FONT, 10))
        self._src_lang_box.setStyleSheet(_combo_ss)
        src_col.addWidget(self._src_lang_box)
        lang_row.addLayout(src_col)

        arrow = QLabel("→")
        arrow.setFont(QFont(FONT, 14))
        arrow.setStyleSheet(f"color: {FG_DIM};")
        arrow.setAlignment(Qt.AlignCenter)
        lang_row.addWidget(arrow)

        tgt_col = QVBoxLayout()
        tgt_col.setSpacing(4)
        tgt_col.addWidget(self._section(tr("trans_lang")))
        self._tgt_lang_box = QComboBox()
        self._tgt_lang_box.setFont(QFont(FONT, 10))
        self._tgt_lang_box.setStyleSheet(_combo_ss)
        tgt_col.addWidget(self._tgt_lang_box)
        lang_row.addLayout(tgt_col)

        # Filtrage dynamique : la langue source est retirée des cibles
        self._src_lang_box.currentIndexChanged.connect(self._refresh_tgt_lang)
        self._refresh_tgt_lang()

        cl.addLayout(lang_row)
        cl.addSpacing(14)
        cl.addWidget(self._sep())
        cl.addSpacing(10)

        # Ajouter une chaîne
        cl.addWidget(self._section(tr("add_channel")))
        cl.addSpacing(5)
        irow = QHBoxLayout()
        irow.setSpacing(8)
        self._input = QLineEdit()
        self._input.setPlaceholderText(tr("placeholder"))
        self._input.setFont(QFont(FONT, 10))
        self._input.returnPressed.connect(self._start)
        irow.addWidget(self._input)
        add_btn = GradientButton("+", PURPLE, PINK)
        add_btn.setFont(QFont(FONT, 14, QFont.Bold))
        add_btn.setFixedSize(40, 36)
        add_btn.clicked.connect(self._start)
        irow.addWidget(add_btn)
        cl.addLayout(irow)
        cl.addSpacing(14)
        cl.addWidget(self._sep())
        cl.addSpacing(10)

        # Sessions actives
        cl.addWidget(self._section(tr("active")))
        cl.addSpacing(5)
        self._sessions_lay = QVBoxLayout()
        self._sessions_lay.setSpacing(5)
        self._no_session = QLabel(tr("none"))
        self._no_session.setFont(QFont(FONT, 9))
        self._no_session.setStyleSheet(f"color: {FG_DIM}; font-style: italic;")
        self._sessions_lay.addWidget(self._no_session)
        cl.addLayout(self._sessions_lay)
        cl.addSpacing(14)
        cl.addWidget(self._sep())
        cl.addSpacing(10)

        # Taille du texte
        sh = QHBoxLayout()
        sh.addWidget(self._section(tr("text_size")))
        sh.addStretch()
        self._size_lbl = QLabel("16 px")
        self._size_lbl.setFont(QFont(FONT, 9, QFont.Bold))
        self._size_lbl.setStyleSheet(f"color: {LILAC};")
        sh.addWidget(self._size_lbl)
        cl.addLayout(sh)
        cl.addSpacing(5)
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(8, 42)
        self._slider.setValue(16)
        self._slider.valueChanged.connect(self._on_size)
        cl.addWidget(self._slider)
        cl.addSpacing(14)
        cl.addWidget(self._sep())
        cl.addSpacing(10)

        # Tout arrêter
        stop_all = GradientButton(
            tr("stop_all"), "#2a1040", "#3a1a5a",
            text_color=LILAC, border_color="#6a3a9a")
        stop_all.setFont(QFont(FONT, 10, QFont.DemiBold))
        stop_all.setFixedHeight(40)
        stop_all.clicked.connect(self._stop_all)
        cl.addWidget(stop_all)
        cl.addStretch()

        root.addWidget(inner, 1)

    def _sep(self):
        f = QFrame()
        f.setObjectName("sep")
        f.setFrameShape(QFrame.HLine)
        return f

    def _section(self, text: str):
        l = QLabel(text.upper())
        l.setFont(QFont(FONT, 8, QFont.Bold))
        l.setStyleSheet(f"color: {FG_DIM}; letter-spacing: 0.08em;")
        return l

    def _refresh_tgt_lang(self):
        """Met à jour la liste des langues cibles en excluant la langue source."""
        src_label = self._src_lang_box.currentText()
        exclude   = _SRC_TO_TGT_EXCLUDE.get(src_label, "")
        current   = self._tgt_lang_box.currentText()
        self._tgt_lang_box.blockSignals(True)
        self._tgt_lang_box.clear()
        for label in TARGET_LANGUAGES:
            if label != exclude:
                self._tgt_lang_box.addItem(label)
        # Conserver la sélection précédente si encore disponible
        idx = self._tgt_lang_box.findText(current)
        self._tgt_lang_box.setCurrentIndex(max(idx, 0))
        self._tgt_lang_box.blockSignals(False)

    def _server_url(self) -> str:
        url = self._server_input.text().strip()
        if not url:
            url = "ws://localhost:8765"
        if not url.startswith("ws://") and not url.startswith("wss://"):
            url = "ws://" + url
        return url

    def _start(self):
        ch = self._input.text().strip().lower()
        if not ch or ch in self._sessions:
            return
        if not _TWITCH_RE.match(ch):
            return
        src_label  = self._src_lang_box.currentText()
        src_whisper, src_deepl = SOURCE_LANGUAGES[src_label]
        tgt_label  = self._tgt_lang_box.currentText()
        tgt_code   = TARGET_LANGUAGES[tgt_label]
        idx = len(self._sessions)
        s = WebSocketSession(ch, idx, self._slider.value(), self,
                             self._server_url(), src_deepl, tgt_code)
        self._sessions[ch] = s
        self._add_row(ch, idx, src_deepl, tgt_code)
        self._input.clear()
        self._update_status()

    def _add_row(self, channel: str, idx: int, src_code: str = "RU", tgt_code: str = "FR"):
        self._no_session.hide()
        color = SESSION_COLORS[idx % len(SESSION_COLORS)]
        row = QWidget()
        row.setStyleSheet(f"""
            QWidget {{ background: {CARD}; border-radius: 10px;
                       border: 1px solid {CARD_BDR}; }}
            QLabel  {{ color: {FG}; background: transparent; border: none; }}
        """)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(10, 8, 8, 8)
        rl.setSpacing(8)
        dot = QLabel("●")
        dot.setFont(QFont(FONT, 8))
        dot.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        dot.setFixedWidth(14)
        rl.addWidget(dot)
        name = QLabel(channel)
        name.setFont(QFont(FONT, 11, QFont.DemiBold))
        rl.addWidget(name)
        rl.addStretch()
        tag = QLabel(f"{src_code} → {tgt_code[:2]}")
        tag.setFont(QFont(FONT, 9))
        tag.setStyleSheet(f"color: {FG_DIM}; background: transparent; border: none;")
        rl.addWidget(tag)
        btn = QPushButton("✕")
        btn.setFont(QFont(FONT, 11, QFont.DemiBold))
        btn.setFixedSize(24, 24)
        btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {LILAC};
                           border: none; padding: 0; }}
            QPushButton:hover {{ color: {PINK}; }}
        """)
        btn.clicked.connect(lambda _, ch=channel, r=row: self._stop_one(ch, r))
        rl.addWidget(btn)
        self._sessions_lay.addWidget(row)
        self._rows[channel] = row

    def _stop_all(self):
        for s in list(self._sessions.values()):
            s.stop()
        self._sessions.clear()
        for r in self._rows.values():
            r.deleteLater()
        self._rows.clear()
        self._no_session.show()
        self._update_status()

    def _stop_one(self, channel: str, row: QWidget = None):
        if channel in self._sessions:
            self._sessions.pop(channel).stop()
        r = row or self._rows.pop(channel, None)
        if r:
            r.deleteLater()
        self._rows.pop(channel, None)
        if not self._sessions:
            self._no_session.show()
        self._update_status()

    def remove_session(self, channel: str):
        self._sessions.pop(channel, None)
        r = self._rows.pop(channel, None)
        if r:
            r.deleteLater()
        if not self._sessions:
            self._no_session.show()
        self._update_status()

    def _update_status(self):
        n = len(self._sessions)
        if n == 0:
            self._status_lbl.setText(tr("status_idle"))
        else:
            s = "s" if n > 1 else ""
            self._status_lbl.setText(tr("status_n", n=n, s=s))

    def _on_size(self, val: int):
        self._size_lbl.setText(f"{val} px")
        for s in self._sessions.values():
            s.set_font_size(val)

    def closeEvent(self, e):
        for s in list(self._sessions.values()):
            s.stop()
        e.accept()


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Subly")
    _load_fonts()
    cp = ControlPanel()
    cp.show()
    sys.exit(app.exec_())
