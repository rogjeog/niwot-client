# ui_profile.py
from __future__ import annotations
import os, sys, base64, mimetypes
from typing import Optional, Dict, Any

from PySide6 import QtWidgets, QtCore, QtGui
from niwot_client import NiwotClient


def resource_path(name: str) -> str:
    """Chemin d'une ressource packagée (PyInstaller) ou en dev."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, name)


DEFAULT_AVATAR_FILE = resource_path("niwotfren.png")


class ProfileWidget(QtWidgets.QWidget):
    """Page profil : avatar (photo actuelle si dispo, sinon niwotfren.png), pseudo, MDP, déconnexion."""

    sig_logged_out = QtCore.Signal()  # MainWindow écoute ceci pour revenir à l'écran de connexion

    def __init__(self):
        super().__init__()
        self._client: Optional[NiwotClient] = None
        self._user: Optional[Dict[str, Any]] = None
        self._selected_avatar_path: Optional[str] = None
        self._did_auto_refresh: bool = False   # pour éviter de spammer /me

        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(12)

        # En-tête + actions
        head_row = QtWidgets.QHBoxLayout()
        self.header = QtWidgets.QLabel("<h2>Mon profil</h2>")
        head_row.addWidget(self.header)
        head_row.addStretch()
        self.btn_refresh = QtWidgets.QPushButton("Rafraîchir")
        self.btn_refresh.clicked.connect(self._refresh_me)
        head_row.addWidget(self.btn_refresh)
        root.addLayout(head_row)

        # Message (statut / erreurs / debug)
        self.lbl_status = QtWidgets.QLabel("")
        self.lbl_status.setWordWrap(True)
        root.addWidget(self.lbl_status)

        # Bloc avatar + upload
        avatar_card = QtWidgets.QGroupBox("Photo de profil")
        root.addWidget(avatar_card)
        av_v = QtWidgets.QVBoxLayout(avatar_card)

        av_top = QtWidgets.QHBoxLayout()
        av_v.addLayout(av_top)

        self.lbl_avatar = QtWidgets.QLabel()
        self.lbl_avatar.setFixedSize(96, 96)
        self.lbl_avatar.setStyleSheet("border:1px solid #39406e; border-radius: 8px;")
        self._set_avatar_pixmap(self._load_default_avatar())
        av_top.addWidget(self.lbl_avatar)

        av_right = QtWidgets.QVBoxLayout()
        av_top.addLayout(av_right, stretch=1)

        self.btn_pick = QtWidgets.QPushButton("Choisir une image…")
        self.btn_pick.clicked.connect(self._pick_avatar)
        self.lbl_file = QtWidgets.QLabel("")  # nom du fichier choisi
        self.lbl_file.setStyleSheet("color:#aab2e6; font-size:12px;")
        av_right.addWidget(self.btn_pick, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        av_right.addWidget(self.lbl_file, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

        # Pseudo
        pseudo_card = QtWidgets.QGroupBox("Identité")
        root.addWidget(pseudo_card)
        form_id = QtWidgets.QFormLayout(pseudo_card)
        self.inp_username = QtWidgets.QLineEdit()
        form_id.addRow("Nom d'utilisateur", self.inp_username)

        # Mots de passe
        pwd_card = QtWidgets.QGroupBox("Changer le mot de passe")
        root.addWidget(pwd_card)
        form_pwd = QtWidgets.QGridLayout(pwd_card)
        self.inp_old = QtWidgets.QLineEdit(); self.inp_old.setEchoMode(QtWidgets.QLineEdit.Password)
        self.inp_new = QtWidgets.QLineEdit(); self.inp_new.setEchoMode(QtWidgets.QLineEdit.Password)
        self.inp_new2 = QtWidgets.QLineEdit(); self.inp_new2.setEchoMode(QtWidgets.QLineEdit.Password)
        form_pwd.addWidget(QtWidgets.QLabel("Ancien"), 0, 0); form_pwd.addWidget(self.inp_old, 0, 1)
        form_pwd.addWidget(QtWidgets.QLabel("Nouveau"), 1, 0); form_pwd.addWidget(self.inp_new, 1, 1)
        form_pwd.addWidget(QtWidgets.QLabel("Confirmer"), 2, 0); form_pwd.addWidget(self.inp_new2, 2, 1)

        # Actions
        actions = QtWidgets.QHBoxLayout()
        actions.addStretch()
        self.btn_save = QtWidgets.QPushButton("Enregistrer")
        self.btn_save.clicked.connect(self._save_profile)
        self.btn_logout = QtWidgets.QPushButton("Déconnexion")
        self.btn_logout.clicked.connect(self._logout)
        actions.addWidget(self.btn_save)
        actions.addWidget(self.btn_logout)
        root.addLayout(actions)

        root.addStretch()

    # ---------- wiring ----------
    def set_client(self, client: NiwotClient):
        self._client = client
        # Si un user est déjà là mais sans avatar exploitable, on recharge /me maintenant.
        if self._user and not self._extract_avatar_value(self._user):
            QtCore.QTimer.singleShot(0, self._refresh_me)

    def set_user(self, user: Dict[str, Any]):
        self._user = user
        self._render_user()
        # Si le client est déjà prêt mais que l'avatar manque, on recharge /me.
        if self._client and not self._extract_avatar_value(user or {}):
            QtCore.QTimer.singleShot(0, self._refresh_me)

    # Auto-refresh intelligent quand la page devient visible la première fois
    def showEvent(self, e: QtGui.QShowEvent) -> None:
        super().showEvent(e)
        if not self._did_auto_refresh:
            self._did_auto_refresh = True
            # Si l'avatar n'est toujours pas connu, recharge /me
            if not self._extract_avatar_value(self._user or {}):
                self._refresh_me()

    # ---------- UI helpers ----------
    def _render_user(self):
        """Hydrate le formulaire depuis self._user et charge l'avatar."""
        self._set_status("")
        u = self._user or {}
        self.inp_username.setText(str(u.get("username") or u.get("email") or ""))

        # avatar : on essaie d'abord l'avatar courant (profileImage...), sinon fallback niwotfren.png
        avatar_val = self._extract_avatar_value(u)
        pm = self._try_load_avatar(avatar_val) if avatar_val else self._load_default_avatar()
        self._set_avatar_pixmap(pm)

    def _extract_avatar_value(self, u: Dict[str, Any]) -> Optional[str]:
        """
        Récupère la valeur exploitable de l'avatar depuis divers formats possibles :
        - string (data:, http(s), chemin relatif), ex: u['profileImage'] == "/media/a.png"
        - objet { url: "...", href: "...", path: "...", src: "..." }
        - autres clés compatibles (avatarUrl, avatar, imageUrl, picture, photoURL, photoUrl, image)
        """
        candidates = [
            u.get("profileImage"),
            u.get("avatarUrl"),
            u.get("avatar"),
            u.get("imageUrl"),
            u.get("picture"),
            u.get("photoURL"),
            u.get("photoUrl"),
            u.get("image"),
        ]
        pi = u.get("profileImage")
        if isinstance(pi, dict):
            for k in ("url", "href", "path", "src"):
                val = pi.get(k)
                if isinstance(val, str) and val:
                    candidates.insert(0, val)  # priorité
                    break

        for c in candidates:
            if isinstance(c, str) and c.strip():
                return c.strip()
        return None

    def _set_status(self, text: str, ok: bool | None = None):
        if not text:
            self.lbl_status.setText("")
            return
        if ok is True:
            self.lbl_status.setStyleSheet("color:#69f0ae;")
        elif ok is False:
            self.lbl_status.setStyleSheet("color:#ff8b8b;")
        else:
            self.lbl_status.setStyleSheet("color:#e8ebff;")
        self.lbl_status.setText(text)

    def _pick_avatar(self):
        pth, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choisir une image", "", "Images (*.png *.jpg *.jpeg *.webp *.gif);;Tous les fichiers (*.*)"
        )
        if pth:
            self._selected_avatar_path = pth
            self.lbl_file.setText(os.path.basename(pth))
            # aperçu immédiat
            pm = QtGui.QPixmap(pth)
            if not pm.isNull():
                self._set_avatar_pixmap(pm)

    def _set_avatar_pixmap(self, pm: QtGui.QPixmap):
        scaled = pm.scaled(96, 96, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           QtCore.Qt.TransformationMode.SmoothTransformation)
        self.lbl_avatar.setPixmap(scaled)

    # ---------- avatar loaders ----------
    def _load_default_avatar(self) -> QtGui.QPixmap:
        if os.path.isfile(DEFAULT_AVATAR_FILE):
            pm = QtGui.QPixmap(DEFAULT_AVATAR_FILE)
            if not pm.isNull():
                return pm
        # fallback : pastille
        pm = QtGui.QPixmap(96, 96)
        pm.fill(QtCore.Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        p.setBrush(QtGui.QBrush(QtGui.QColor("#2a355f"))); p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 96, 96); p.end()
        return pm

    def _resolve_media_url(self, raw: str) -> Optional[str]:
        if not raw: return None
        v = str(raw)
        if v.startswith("data:"):  # data URL
            return v
        if v.startswith("http://") or v.startswith("https://"):
            return v
        base = getattr(self._client, "api_base", "") if self._client else ""
        base = str(base).rstrip("/")
        if not base: return None
        if v.startswith("/"): return f"{base}{v}"
        return f"{base}/{v}"

    def _try_load_avatar(self, raw: str) -> QtGui.QPixmap:
        """Charge l'avatar depuis data URL / HTTP / relatif. Fallback sur avatar par défaut."""
        # 1) Data URL
        if isinstance(raw, str) and raw.startswith("data:"):
            try:
                b64 = raw.split(",", 1)[1]
                img = QtGui.QImage.fromData(base64.b64decode(b64))
                if not img.isNull():
                    return QtGui.QPixmap.fromImage(img)
            except Exception:
                pass
        # 2) HTTP/relatif via session (cookies)
        url = self._resolve_media_url(raw)
        if url and self._client:
            try:
                r = self._client.sess.get(url, timeout=6)  # type: ignore
                if r.ok:
                    img = QtGui.QImage.fromData(r.content)
                    if not img.isNull():
                        return QtGui.QPixmap.fromImage(img)
                else:
                    self._set_status(f"Avatar HTTP échec: {r.status_code}", ok=False)
            except Exception as e:
                self._set_status(f"Avatar HTTP erreur: {e}", ok=False)
        # 3) Fallback fichier local
        return self._load_default_avatar()

    # ---------- save / logout / refresh ----------
    def _refresh_me(self):
        """Recharge /me pour mettre à jour le profil et l’avatar courant."""
        if not self._client:
            self._set_status("Client non disponible.", ok=False); return
        try:
            r = self._client.me()
            if r.get("ok"):
                self._user = r["user"]
                self._render_user()
                self._set_status("Profil rechargé.", ok=True)
            else:
                self._set_status("Impossible de récupérer /me.", ok=False)
        except Exception as e:
            self._set_status(f"Erreur /me : {e}", ok=False)

    def _save_profile(self):
        """Émet 'profile:update' via Socket.IO avec ACK, comme la webapp."""
        if not self._client:
            self._set_status("Client non disponible.", ok=False); return
        sio = getattr(self._client, "sio", None)
        if not sio or not sio.connected:
            self._client.connect_socket()
            sio = self._client.sio
            if not sio or not sio.connected:
                self._set_status("Socket non disponible.", ok=False); return

        username = self.inp_username.text().strip()
        oldPwd   = self.inp_old.text().strip()
        newPwd   = self.inp_new.text().strip()
        newPwd2  = self.inp_new2.text().strip()

        if (newPwd or newPwd2 or oldPwd) and newPwd != newPwd2:
            self._set_status("Les nouveaux mots de passe ne correspondent pas.", ok=False)
            return

        avatar_data_url: Optional[str] = None
        if self._selected_avatar_path:
            avatar_data_url = self._make_data_url(self._selected_avatar_path)

        self._set_status("Enregistrement en cours…")
        self.btn_save.setEnabled(False)

        def _ack(ack):
            QtCore.QTimer.singleShot(0, lambda a=ack: self._on_save_ack(a if isinstance(a, dict) else {"ok": False, "error": "update_failed"}))

        payload = {
            "username": username or None,
            "oldPassword": oldPwd or None,
            "newPassword": newPwd or None,
            "confirmPassword": newPwd2 or None,
            "avatarBase64": avatar_data_url or None
        }

        try:
            sio.emit("profile:update", payload, _ack)  # type: ignore
        except Exception as e:
            self.btn_save.setEnabled(True)
            self._set_status(f"Échec de l'envoi : {e}", ok=False)

    def _on_save_ack(self, ack: Dict[str, Any]):
        self.btn_save.setEnabled(True)
        if not ack.get("ok"):
            msg = str(ack.get("error") or "Échec de la mise à jour.")
            if msg == "bad_old_password":    msg = "Ancien mot de passe incorrect."
            elif msg == "password_mismatch": msg = "Les nouveaux mots de passe ne correspondent pas."
            elif msg == "missing_password_fields": msg = "Renseignez l'ancien, le nouveau et la confirmation."
            elif msg == "bad_image":         msg = "Image invalide."
            self._set_status(msg, ok=False)
            return

        # recharger /me pour récupérer l'URL de l'avatar fraîchement mise à jour
        self._refresh_me()
        self._selected_avatar_path = None
        self.inp_old.clear(); self.inp_new.clear(); self.inp_new2.clear()
        self._set_status("Profil mis à jour.", ok=True)

    def _logout(self):
        """Déconnecte côté API puis demande au MainWindow d'afficher l'écran de connexion."""
        if self._client:
            try:
                self._client.logout()
            except Exception:
                pass
        self.sig_logged_out.emit()

    # ---------- utils ----------
    def _make_data_url(self, file_path: str) -> Optional[str]:
        try:
            mime, _ = mimetypes.guess_type(file_path)
            if not mime:
                mime = "application/octet-stream"
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            return f"data:{mime};base64,{b64}"
        except Exception:
            return None
