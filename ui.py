"""
Subly — interface PyQt5
Ce module est importe APRES la creation du WhisperModel (CTranslate2 CUDA)
pour eviter le conflit d'init GPU entre Qt et CTranslate2.
"""
import os
import re
import sys
import subprocess
import threading
import queue

import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QSlider, QVBoxLayout, QHBoxLayout, QFrame, QSizeGrip,
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QRectF
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QPainterPath,
    QFontDatabase, QLinearGradient,
)

# ── Constantes ─────────────────────────────────────────────────────────────────
_BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
FFMPEG_PATH = os.path.join(_BASE_DIR, "ffmpeg", "bin", "ffmpeg.exe")
_NLLB_NAME  = "facebook/nllb-200-distilled-1.3B"
_TWITCH_RE  = re.compile(r"^[a-zA-Z0-9_]{1,25}$")
SAMPLE_RATE = 16_000
CHUNK_SEC   = 5

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
#  Splash de chargement
# ══════════════════════════════════════════════════════════════════════════════
class LoadingSplash(QWidget):
    RADIUS = 16

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(320, 160)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(12)

        title = QLabel("🦄  Subly")
        title.setFont(QFont(FONT, 18, QFont.Bold))
        title.setStyleSheet(f"color: {PURPLE}; background: transparent;")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        self.status = QLabel("Initialisation...")
        self.status.setFont(QFont(FONT, 9))
        self.status.setStyleSheet(f"color: {LILAC}; background: transparent;")
        self.status.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.status)

        scr = QApplication.primaryScreen().geometry()
        self.move((scr.width() - self.width()) // 2,
                  (scr.height() - self.height()) // 2)

    def set_status(self, text: str):
        self.status.setText(text)
        QApplication.processEvents()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.RADIUS, self.RADIUS)
        p.fillPath(path, QColor(14, 14, 16, 248))
        p.setPen(QPen(QColor(CARD_BDR), 1))
        p.drawPath(path)


# ══════════════════════════════════════════════════════════════════════════════
#  GradientButton
# ══════════════════════════════════════════════════════════════════════════════
class GradientButton(QPushButton):
    RADIUS = 10

    def __init__(self, text, c1, c2, text_color="#fff", border_color=None,
                 parent=None):
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
#  IconSquare
# ══════════════════════════════════════════════════════════════════════════════
class IconSquare(QLabel):
    def __init__(self, text, c1, c2, radius=10, parent=None):
        super().__init__(text, parent)
        self._c1 = QColor(c1)
        self._c2 = QColor(c2)
        self._r  = radius
        self.setFixedSize(38, 38)
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0, self._c1)
        g.setColorAt(1, self._c2)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self._r, self._r)
        p.fillPath(path, QBrush(g))
        p.setPen(Qt.white)
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
        # Couleurs Subly — inspirees du concept sans copier la palette Apple
        for color, action in [("#e63946", self._close),       # cramoisie = fermer
                               ("#f4a261", self._toggle_opacity),  # orange = action
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

        self.text_lbl = QLabel(f"[{self.channel}]  En attente...")
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
#  SubtitleSession
# ══════════════════════════════════════════════════════════════════════════════
class SubtitleSession(QObject):
    text_signal = pyqtSignal(str)

    def __init__(self, channel: str, index: int, font_size: int,
                 panel: "ControlPanel",
                 whisper, tokenizer, nllb_model, fr_token_id):
        super().__init__()
        self.channel    = channel
        self._panel     = panel
        self._whisper   = whisper
        self._tokenizer = tokenizer
        self._nllb      = nllb_model
        self._fr_tok    = fr_token_id
        self._audio_q   = queue.Queue()
        self._running   = True
        self._sl_proc   = None
        self._ff_proc   = None
        self._ctx       = []   # buffer de contexte (2 derniers segments RU)

        accent = SESSION_COLORS[index % len(SESSION_COLORS)]
        self.win = OverlayWindow(channel, font_size, accent)
        self.win.move(60, max(40, 820 - index * 140))
        self.win.setWindowOpacity(0.93)
        self.win.on_close = self._on_win_close
        self.win.show()

        self.text_signal.connect(self.win.set_text)
        threading.Thread(target=self._capture, daemon=True).start()
        threading.Thread(target=self._process, daemon=True).start()

    def _on_win_close(self):
        self.stop()
        self._panel.remove_session(self.channel)

    def _capture(self):
        url = f"https://www.twitch.tv/{self.channel}"
        sl  = ["streamlink", "--stdout", url, "best"]
        ff  = [FFMPEG_PATH, "-i", "pipe:0",
               "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", "1", "pipe:1"]
        try:
            self._sl_proc = subprocess.Popen(
                sl, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW)
            self._ff_proc = subprocess.Popen(
                ff, stdin=self._sl_proc.stdout,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW)
            chunk = SAMPLE_RATE * 2 * CHUNK_SEC
            while self._running:
                data = self._ff_proc.stdout.read(chunk)
                if not data:
                    break
                self._audio_q.put(data)
        except Exception as ex:
            self.text_signal.emit(f"[{self.channel}]  Erreur capture : {ex}")

    def _process(self):
        while self._running:
            try:
                data = self._audio_q.get(timeout=1)
            except queue.Empty:
                continue

            audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            segs, _ = self._whisper.transcribe(audio, language="ru")
            ru = " ".join(s.text for s in segs).strip()
            if not ru:
                continue

            try:
                # Contexte glissant : concatène les 2 segments précédents pour
                # que NLLB comprenne la cohérence narrative du stream.
                self._ctx.append(ru)
                if len(self._ctx) > 2:
                    self._ctx.pop(0)
                ru_ctx = " ".join(self._ctx)

                inp = self._tokenizer(
                    ru_ctx,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=512,
                ).to("cuda")

                out = self._nllb.generate(
                    **inp,
                    forced_bos_token_id=self._fr_tok,
                    num_beams=2,          # 4→2 : ×1.8 plus rapide, qualité OK
                    max_new_tokens=128,   # évite les timeouts sur phrases courtes
                    repetition_penalty=1.2,
                    no_repeat_ngram_size=3,
                )
                fr = self._tokenizer.decode(out[0], skip_special_tokens=True)
                self.text_signal.emit(f"[{self.channel}]  {fr}")
            except Exception as ex:
                self.text_signal.emit(f"[{self.channel}]  Erreur traduction : {ex}")

    def set_font_size(self, size: int):
        self.win.set_font_size(size)

    def stop(self):
        self._running = False
        for proc in (self._ff_proc, self._sl_proc):
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
        try:
            self.win.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  ControlPanel  —  fenetre principale frameless, style coherent avec l'overlay
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

    def __init__(self, whisper, tokenizer, nllb_model, fr_token_id):
        super().__init__()
        self._whisper   = whisper
        self._tokenizer = tokenizer
        self._nllb      = nllb_model
        self._fr_tok    = fr_token_id
        self._sessions: dict[str, SubtitleSession] = {}
        self._rows:     dict[str, QWidget]         = {}
        self._drag_pos  = None
        self._bg        = QColor(14, 14, 16, 255)

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Subly")
        self.setMinimumSize(290, 420)
        self.resize(330, 580)
        self.setStyleSheet(_PANEL_SS)
        self._build()

    # ── Fond arrondi ───────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.RADIUS, self.RADIUS)
        p.fillPath(path, self._bg)
        p.setPen(QPen(QColor(CARD_BDR), 1))
        p.drawPath(path)

    # ── Drag ───────────────────────────────────────────────────────────────
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

        # ── Barre de titre draggable ───────────────────────────────────────
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

        # Traffic lights Subly (rouge cramoisie / orange / violet)
        for color, action in [
            ("#e63946", self.close),
            ("#f4a261", self.showMinimized),
            ("#7a6a9a", None),
        ]:
            bl.addWidget(TrafficLight(color, action, bar))

        bl.addStretch()

        lbl_title = QLabel("🦄  Subly")
        lbl_title.setFont(QFont(FONT, 12, QFont.DemiBold))
        lbl_title.setStyleSheet(f"color: {FG};")
        bl.addWidget(lbl_title)

        bl.addStretch()
        bl.addSpacing(50)   # equilibre les traffic lights a gauche
        root.addWidget(bar)

        # Ligne de statut juste sous la barre
        self._status_lbl = QLabel("● En ligne · aucune session")
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

        # Ajouter une chaine
        cl.addWidget(self._section("Ajouter une chaîne"))
        cl.addSpacing(5)
        irow = QHBoxLayout()
        irow.setSpacing(8)
        self._input = QLineEdit()
        self._input.setPlaceholderText("ex: b_a_s_y_a")
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
        cl.addWidget(self._section("Sessions actives"))
        cl.addSpacing(5)
        self._sessions_lay = QVBoxLayout()
        self._sessions_lay.setSpacing(5)
        self._no_session = QLabel("Aucune session")
        self._no_session.setFont(QFont(FONT, 9))
        self._no_session.setStyleSheet(f"color: {FG_DIM}; font-style: italic;")
        self._sessions_lay.addWidget(self._no_session)
        cl.addLayout(self._sessions_lay)
        cl.addSpacing(14)
        cl.addWidget(self._sep())
        cl.addSpacing(10)

        # Taille du texte
        sh = QHBoxLayout()
        sh.addWidget(self._section("Taille du texte"))
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

        # Tout arreter
        stop_all = GradientButton(
            "■  Tout arrêter", "#2a1040", "#3a1a5a",
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

    def _start(self):
        ch = self._input.text().strip().lower()
        if not ch or ch in self._sessions:
            return
        if not _TWITCH_RE.match(ch):
            return
        idx = len(self._sessions)
        s = SubtitleSession(
            ch, idx, self._slider.value(), self,
            self._whisper, self._tokenizer, self._nllb, self._fr_tok)
        self._sessions[ch] = s
        self._add_row(ch, idx)
        self._input.clear()
        self._update_status()

    def _add_row(self, channel: str, idx: int):
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
        tag = QLabel("RU → FR")
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
            self._status_lbl.setText("● En ligne · aucune session")
        else:
            s = "s" if n > 1 else ""
            self._status_lbl.setText(f"● En ligne · {n} session{s} active{s}")

    def _on_size(self, val: int):
        self._size_lbl.setText(f"{val} px")
        for s in self._sessions.values():
            s.set_font_size(val)

    def closeEvent(self, e):
        for s in list(self._sessions.values()):
            s.stop()
        e.accept()
