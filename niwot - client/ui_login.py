# ui_login.py
from __future__ import annotations
import os, sys
from typing import Optional, Dict, Any

from PySide6 import QtWidgets, QtCore, QtGui
from niwot_client import NiwotClient


def resource_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, name)


class LoginWidget(QtWidgets.QWidget):
    """
    Écran d'authentification compact (équivalent pages/index.tsx) :
      - Onglets: Connexion | Créer un compte
      - Carte centrée (H & V), largeur limitée
      - HAUTEUR = contenu (ne s'étire plus)
    """
    sig_logged_in = QtCore.Signal(dict)
    sig_error = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        self._client: Optional[NiwotClient] = None
        self._loaded = False
        self._tab: str = "login"
        self._selected_avatar_path: Optional[str] = None

        # =========== Shell centrage ===========
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 24, 20, 20)
        root.setSpacing(0)

        root.addStretch(1)  # centrage vertical (haut)

        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addStretch(1)  # centrage horizontal (gauche)

        # ---------- Carte ----------
        self.card = QtWidgets.QGroupBox()
        self.card.setTitle("")
        self.card.setObjectName("LoginCard")
        self.card.setMaximumWidth(520)
        self.card.setMinimumWidth(360)
        # Hauteur contrôlée par sizeHint de son contenu
        self.card.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                                QtWidgets.QSizePolicy.Policy.Fixed)

        card_v = QtWidgets.QVBoxLayout(self.card)
        card_v.setContentsMargins(14, 14, 14, 14)
        card_v.setSpacing(10)

        title = QtWidgets.QLabel(
            '<div style="text-align:center">'
            ' <span style="font-size:20px; font-weight:700;">Bienvenue sur '
            '<span style="color:#7a3cff;">Niwot</span>'
            '</span>'
            '</div>'
        )
        title.setContentsMargins(0, 0, 0, 2)
        card_v.addWidget(title, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        # Onglets
        tabs = QtWidgets.QHBoxLayout()
        tabs.setSpacing(6)
        self.btn_tab_login = QtWidgets.QPushButton("Connexion")
        self.btn_tab_reg   = QtWidgets.QPushButton("Créer un compte")
        self.btn_tab_login.clicked.connect(lambda: self._set_tab("login"))
        self.btn_tab_reg.clicked.connect(lambda: self._set_tab("register"))
        tabs.addWidget(self.btn_tab_login, 1)
        tabs.addWidget(self.btn_tab_reg, 1)
        card_v.addLayout(tabs)

        # Stack formulaires
        self.forms = QtWidgets.QStackedWidget()
        # Par défaut QStackedWidget veut s'étendre -> on contrôle sa hauteur nous-mêmes
        self.forms.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                                 QtWidgets.QSizePolicy.Policy.Fixed)
        self.forms.currentChanged.connect(lambda _: self._update_forms_height())
        card_v.addWidget(self.forms, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        # ===== Form Connexion (compact) =====
        login_w = QtWidgets.QWidget()
        login_w.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                              QtWidgets.QSizePolicy.Policy.Fixed)
        f1 = QtWidgets.QVBoxLayout(login_w)
        f1.setSpacing(8); f1.setContentsMargins(0, 0, 0, 0)

        urow = QtWidgets.QVBoxLayout(); urow.setSpacing(4)
        lbl_u = QtWidgets.QLabel("Nom d'utilisateur")
        self.inp_login_user = QtWidgets.QLineEdit(); self.inp_login_user.setMinimumHeight(34)
        urow.addWidget(lbl_u); urow.addWidget(self.inp_login_user)
        f1.addLayout(urow)

        prow = QtWidgets.QVBoxLayout(); prow.setSpacing(4)
        lbl_p = QtWidgets.QLabel("Mot de passe")
        self.inp_login_pwd = QtWidgets.QLineEdit()
        self.inp_login_pwd.setEchoMode(QtWidgets.QLineEdit.Password)
        self.inp_login_pwd.setMinimumHeight(34)
        self.inp_login_pwd.returnPressed.connect(lambda: self.btn_do_login.click())
        prow.addWidget(lbl_p); prow.addWidget(self.inp_login_pwd)
        f1.addLayout(prow)

        self.lbl_login_error = QtWidgets.QLabel(""); self.lbl_login_error.setStyleSheet("color:#ff8b8b;")
        f1.addWidget(self.lbl_login_error)

        self.btn_do_login = QtWidgets.QPushButton("Se connecter"); self.btn_do_login.setMinimumHeight(34)
        self.btn_do_login.clicked.connect(self._do_login)
        f1.addWidget(self.btn_do_login)

        self.forms.addWidget(login_w)

        # ===== Form Register (compact) =====
        reg_w = QtWidgets.QWidget()
        reg_w.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                            QtWidgets.QSizePolicy.Policy.Fixed)
        f2 = QtWidgets.QVBoxLayout(reg_w)
        f2.setSpacing(8); f2.setContentsMargins(0, 0, 0, 0)

        arow = QtWidgets.QVBoxLayout(); arow.setSpacing(4)
        lbl_a = QtWidgets.QLabel("Photo de profil")
        self.btn_pick_avatar = QtWidgets.QPushButton("Choisir un fichier…"); self.btn_pick_avatar.setMinimumHeight(32)
        self.btn_pick_avatar.clicked.connect(self._pick_avatar)
        self.lbl_avatar_file = QtWidgets.QLabel(""); self.lbl_avatar_file.setStyleSheet("color:#aab2e6; font-size:12px;")
        arow.addWidget(lbl_a); arow.addWidget(self.btn_pick_avatar); arow.addWidget(self.lbl_avatar_file)
        f2.addLayout(arow)

        r_user_row = QtWidgets.QVBoxLayout(); r_user_row.setSpacing(4)
        lbl_ru = QtWidgets.QLabel("Nom d'utilisateur (unique)")
        self.inp_reg_user = QtWidgets.QLineEdit(); self.inp_reg_user.setMinimumHeight(34)
        r_user_row.addWidget(lbl_ru); r_user_row.addWidget(self.inp_reg_user)
        f2.addLayout(r_user_row)

        grid = QtWidgets.QGridLayout(); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(6)
        col1 = QtWidgets.QVBoxLayout(); col1.setSpacing(4)
        lbl_rp = QtWidgets.QLabel("Mot de passe")
        self.inp_reg_pwd = QtWidgets.QLineEdit(); self.inp_reg_pwd.setEchoMode(QtWidgets.QLineEdit.Password); self.inp_reg_pwd.setMinimumHeight(34)
        hint = QtWidgets.QLabel("8+ caractères, 1 majuscule, 1 minuscule"); hint.setStyleSheet("color: rgba(255,255,255,0.6); font-size:11px; margin-top:2px;")
        col1.addWidget(lbl_rp); col1.addWidget(self.inp_reg_pwd); col1.addWidget(hint)

        col2 = QtWidgets.QVBoxLayout(); col2.setSpacing(4)
        lbl_rc = QtWidgets.QLabel("Confirmer le mot de passe")
        self.inp_reg_pwd2 = QtWidgets.QLineEdit(); self.inp_reg_pwd2.setEchoMode(QtWidgets.QLineEdit.Password); self.inp_reg_pwd2.setMinimumHeight(34)
        col2.addWidget(lbl_rc); col2.addWidget(self.inp_reg_pwd2)

        wcol1 = QtWidgets.QWidget(); wcol1.setLayout(col1)
        wcol2 = QtWidgets.QWidget(); wcol2.setLayout(col2)
        wcol1.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        wcol2.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        grid.addWidget(wcol1, 0, 0); grid.addWidget(wcol2, 0, 1)

        grid_w = QtWidgets.QWidget(); grid_w.setLayout(grid)
        grid_w.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        f2.addWidget(grid_w)

        self.lbl_reg_error = QtWidgets.QLabel(""); self.lbl_reg_error.setStyleSheet("color:#ff8b8b;")
        f2.addWidget(self.lbl_reg_error)

        self.btn_do_register = QtWidgets.QPushButton("Créer mon compte"); self.btn_do_register.setMinimumHeight(34)
        self.btn_do_register.clicked.connect(self._do_register)
        f2.addWidget(self.btn_do_register)

        self.forms.addWidget(reg_w)

        # Ajout au shell de centrage
        row.addWidget(self.card, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        row.addStretch(1)
        root.addLayout(row)

        root.addStretch(1)  # centrage vertical (bas)

        # Style des onglets + affichage
        self._apply_tab_styles()
        self._set_loaded(False)

        # Force la hauteur correcte au premier affichage
        QtCore.QTimer.singleShot(0, self._update_forms_height)

    # ------------------ API ------------------
    def set_client(self, client: NiwotClient):
        self._client = client
        QtCore.QTimer.singleShot(0, self._check_me)

    # ------------------ Tabs ------------------
    def _set_tab(self, tab: str):
        if tab not in ("login", "register"): return
        self._tab = tab
        self.forms.setCurrentIndex(0 if tab == "login" else 1)
        self._apply_tab_styles()
        self._update_forms_height()

    def _apply_tab_styles(self):
        active = (
            "QPushButton{color:#fff;border:1px solid #6b4fd6;border-radius:10px;"
            "padding:6px 10px;background-color:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #7a3cff, stop:1 #5b2fd6);}"
            "QPushButton:hover{border-color:#7a3cff;}"
        )
        inactive = (
            "QPushButton{color:rgba(255,255,255,0.85);border:1px solid rgba(255,255,255,0.12);"
            "border-radius:10px;padding:6px 10px;background-color:rgba(255,255,255,0.05);}"
        )
        if self._tab == "login":
            self.btn_tab_login.setStyleSheet(active); self.btn_tab_reg.setStyleSheet(inactive)
        else:
            self.btn_tab_login.setStyleSheet(inactive); self.btn_tab_reg.setStyleSheet(active)

    # ------------------ Taille contrôlée ------------------
    def _update_forms_height(self):
        """
        Fixe la hauteur du QStackedWidget à la sizeHint du formulaire courant.
        Empêche toute extension verticale.
        """
        w = self.forms.currentWidget()
        if not w:
            return
        # Calcul de la hauteur idéale du formulaire
        h = w.sizeHint().height()
        # On applique exactement cette hauteur au stack
        self.forms.setFixedHeight(h)
        # Ajuste la carte et ce widget après changement
        self.card.adjustSize()
        self.adjustSize()

    # ------------------ Helpers ------------------
    def _set_loaded(self, ok: bool):
        self._loaded = ok
        self.card.setVisible(ok)
        if ok:
            self._update_forms_height()

    def _check_me(self):
        if not self._client:
            self._set_loaded(True); return
        try:
            r = self._client.me()
            if r.get("ok") and r.get("user"):
                self.sig_logged_in.emit(r["user"]); return
        except Exception:
            pass
        self._set_loaded(True)

    def _pick_avatar(self):
        pth, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choisir une image", "", "Images (*.png *.jpg *.jpeg *.webp *.gif);;Tous les fichiers (*.*)"
        )
        if pth:
            self._selected_avatar_path = pth
            self.lbl_avatar_file.setText(os.path.basename(pth))

    # ------------------ Actions ------------------
    def _do_login(self):
        self.lbl_login_error.clear()
        if not self._client:
            msg = "Client non initialisé."
            self.lbl_login_error.setText(msg); self.sig_error.emit(msg); return

        username = self.inp_login_user.text().strip()
        password = self.inp_login_pwd.text().strip()
        if not username or not password:
            self.lbl_login_error.setText("Veuillez remplir tous les champs.")
            return

        self.btn_do_login.setEnabled(False)
        try:
            url = f"{self._client.api_base}/auth/login"
            r = self._client.sess.post(url, json={"username": username, "password": password}, timeout=10)  # type: ignore
            if r.ok:
                me = self._client.me()
                user = me["user"] if me.get("ok") else {"username": username}
                self.sig_logged_in.emit(user)
            else:
                try: err = r.json().get("error") or r.text
                except Exception: err = r.text
                self.lbl_login_error.setText(err or "Erreur"); self.sig_error.emit(err or "Erreur")
        except Exception as e:
            msg = str(e) or "Erreur de connexion"
            self.lbl_login_error.setText(msg); self.sig_error.emit(msg)
        finally:
            self.btn_do_login.setEnabled(True)
            self._update_forms_height()

    def _do_register(self):
        self.lbl_reg_error.clear()
        if not self._client:
            msg = "Client non initialisé."
            self.lbl_reg_error.setText(msg); self.sig_error.emit(msg); return

        username = self.inp_reg_user.text().strip()
        pwd  = self.inp_reg_pwd.text().strip()
        pwd2 = self.inp_reg_pwd2.text().strip()
        if not username or not pwd or not pwd2:
            self.lbl_reg_error.setText("Veuillez remplir tous les champs."); return
        if pwd != pwd2:
            self.lbl_reg_error.setText("Les mots de passe ne correspondent pas."); return

        self.btn_do_register.setEnabled(False)
        try:
            url = f"{self._client.api_base}/auth/register"
            files = {}
            data = {"username": username, "password": pwd, "password2": pwd2}
            if self._selected_avatar_path:
                try:
                    files["avatar"] = (os.path.basename(self._selected_avatar_path),
                                       open(self._selected_avatar_path, "rb"),
                                       "application/octet-stream")
                except Exception:
                    pass
            r = self._client.sess.post(url, data=data, files=files if files else None, timeout=20)  # type: ignore
            if r.ok:
                me = self._client.me()
                user = me["user"] if me.get("ok") else {"username": username}
                self.sig_logged_in.emit(user)
            else:
                try: err = r.json().get("error") or r.text
                except Exception: err = r.text
                self.lbl_reg_error.setText(err or "Erreur"); self.sig_error.emit(err or "Erreur")
        except Exception as e:
            msg = str(e) or "Erreur d'inscription"
            self.lbl_reg_error.setText(msg); self.sig_error.emit(msg)
        finally:
            self.btn_do_register.setEnabled(True)
            self._update_forms_height()
