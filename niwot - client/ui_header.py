# ui_header.py
from __future__ import annotations
import os, sys, base64
from typing import Optional, Dict, Any

from PySide6 import QtWidgets, QtCore, QtGui


def resource_path(name: str) -> str:
    """Chemin d'une ressource packagée (PyInstaller) ou en dev."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, name)


class HeaderWidget(QtWidgets.QWidget):
    """
    Entête global :
      - À gauche : [Niwot]  [Administrer*]
      - À droite : [avatar]  "Connecté en tant que <username>"  [Mon profil]
    * Administrer visible uniquement si user.role == 'admin'
    """
    sig_go_lobby   = QtCore.Signal()
    sig_go_admin   = QtCore.Signal()
    sig_go_profile = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("HeaderWidget")  # ciblé par le QSS global
        self._user: Optional[Dict[str, Any]] = None
        self._client = None     # pour récupérer l'avatar via HTTP (cookies)
        self._api_base = ""     # base URL pour résoudre les médias

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(10)

        # --- Groupe gauche : Niwot + Administrer ---
        left = QtWidgets.QHBoxLayout(); left.setSpacing(8)
        self.btn_home = QtWidgets.QPushButton("Niwot")
        self.btn_home.clicked.connect(self.sig_go_lobby.emit)

        self.btn_admin = QtWidgets.QPushButton("Administrer")
        self.btn_admin.clicked.connect(self.sig_go_admin.emit)
        self.btn_admin.setVisible(False)  # masqué par défaut

        left_w = QtWidgets.QWidget(); left_w.setLayout(left)
        left.addWidget(self.btn_home)
        left.addWidget(self.btn_admin)

        # --- Groupe droit : avatar + texte + Mon profil ---
        right = QtWidgets.QHBoxLayout(); right.setSpacing(10)

        self.lbl_avatar = QtWidgets.QLabel()
        self.lbl_avatar.setFixedSize(28, 28)
        self._set_avatar_pixmap(self._fallback_avatar_pixmap())  # fallback par défaut

        self.lbl_user = QtWidgets.QLabel("Connecté en tant que -")

        self.btn_profile = QtWidgets.QPushButton("Mon profil")
        self.btn_profile.clicked.connect(self.sig_go_profile.emit)

        right_w = QtWidgets.QWidget(); right_w.setLayout(right)
        right.addWidget(self.lbl_avatar)
        right.addWidget(self.lbl_user)
        right.addWidget(self.btn_profile)

        root.addWidget(left_w, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        root.addStretch()
        root.addWidget(right_w, 0, QtCore.Qt.AlignmentFlag.AlignRight)

        # Pas de setStyleSheet ici : on laisse le thème global (QSS) s'appliquer.

    # ---------- API ----------
    def set_client(self, client):
        """Permet d'utiliser client.sess pour télécharger l'avatar et récupérer api_base."""
        self._client = client
        try:
            self._api_base = str(getattr(client, "api_base", "")).rstrip("/")
        except Exception:
            self._api_base = ""

    def set_user(self, user: Dict[str, Any] | None):
        """Appelé après login / /me."""
        self._user = user or None
        username = (user or {}).get("username") or (user or {}).get("email") or "-"
        self.lbl_user.setText(f"Connecté en tant que {username}")
        self.btn_admin.setVisible(bool(user and user.get("role") == "admin"))

        # avatar courant : profil → sinon fallback niwotfren.png
        avatar_val = None
        if user:
            pi = user.get("profileImage")
            # profileImage peut être un objet { url: ... } ou une string
            if isinstance(pi, dict):
                for k in ("url", "href", "path", "src"):
                    if isinstance(pi.get(k), str) and pi.get(k):
                        avatar_val = pi.get(k)
                        break
            if not avatar_val:
                avatar_val = user.get("profileImage") or user.get("avatarUrl") or user.get("avatar") or user.get("imageUrl") or user.get("picture")

        if avatar_val:
            pm = self._load_avatar_from_value(avatar_val)
            if pm is not None:
                self._set_avatar_pixmap(pm)
                return
        # fallback
        self._set_avatar_pixmap(self._fallback_avatar_pixmap())

    # ---------- helpers ----------
    def _set_avatar_pixmap(self, pm: QtGui.QPixmap):
        scaled = pm.scaled(28, 28, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           QtCore.Qt.TransformationMode.SmoothTransformation)
        self.lbl_avatar.setPixmap(scaled)

    def _fallback_avatar_pixmap(self) -> QtGui.QPixmap:
        """Charge niwotfren.png comme avatar par défaut (embarqué via --add-data)."""
        path = resource_path("niwotfren.png")
        pm = QtGui.QPixmap(path)
        if not pm.isNull():
            return pm
        # dernier recours : petite pastille unie
        pm = QtGui.QPixmap(28, 28)
        pm.fill(QtCore.Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        p.setBrush(QtGui.QBrush(QtGui.QColor("#2a355f"))); p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 28, 28); p.end()
        return pm

    def _resolve_media_url(self, raw: str) -> Optional[str]:
        if not raw: return None
        v = str(raw)
        if v.startswith("data:"):  # data URL
            return v
        if v.startswith("http://") or v.startswith("https://"):
            return v
        base = self._api_base
        if not base: return None
        if v.startswith("/"): return f"{base}{v}"
        return f"{base}/{v}"

    def _load_avatar_from_value(self, raw: str) -> Optional[QtGui.QPixmap]:
        """Charge l'avatar depuis data URL / HTTP / relatif. Retourne None si échec."""
        # 1) Data URL
        if isinstance(raw, str) and raw.startswith("data:"):
            try:
                b64 = raw.split(",", 1)[1]
                img = QtGui.QImage.fromData(base64.b64decode(b64))
                if not img.isNull():
                    return QtGui.QPixmap.fromImage(img)
            except Exception:
                return None

        # 2) HTTP/relatif via session (cookies)
        url = self._resolve_media_url(raw)
        if url and self._client:
            try:
                r = self._client.sess.get(url, timeout=6)  # type: ignore
                if r.ok:
                    img = QtGui.QImage.fromData(r.content)
                    if not img.isNull():
                        return QtGui.QPixmap.fromImage(img)
            except Exception:
                return None

        return None
