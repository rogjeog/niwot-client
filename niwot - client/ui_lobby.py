# ui_lobby.py
from __future__ import annotations
from PySide6 import QtWidgets, QtCore
import re
from typing import Any, Dict, Optional

ALNUM6 = re.compile(r"^[A-Z0-9]{6}$")

class LobbyWidget(QtWidgets.QWidget):
    """
    Lobby avec :
      - Créer une salle (nom + visibilité)
      - Rejoindre par code
      - Salles publiques (avec joueurs)
      - Classements (Top joueurs / Top contributeurs)
      - + Bouton "Proposer question" (ouvre la page Suggest) -> sig_goto_suggest
    """
    sig_enter_room = QtCore.Signal(str)  # room code
    sig_error = QtCore.Signal(str)
    sig_goto_suggest = QtCore.Signal()  # NEW

    def __init__(self):
        super().__init__()
        self._user: Optional[Dict[str, Any]] = None
        self._client = None

        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(12)

        self.title = QtWidgets.QLabel("<h2>Lobby</h2>")
        root.addWidget(self.title)

        # === Ligne créer / rejoindre ===
        two_col = QtWidgets.QHBoxLayout()
        two_col.setSpacing(12)
        root.addLayout(two_col)

        # -- Créer une salle --
        self.grp_create = QtWidgets.QGroupBox("Créer une salle")
        two_col.addWidget(self.grp_create, 1)
        create_layout = QtWidgets.QFormLayout(self.grp_create)
        self.inp_room_name = QtWidgets.QLineEdit()
        self.inp_room_name.setPlaceholderText("(Défaut : Salle de <votre pseudo>)")
        create_layout.addRow("Nom de la salle", self.inp_room_name)
        vis_container = QtWidgets.QWidget()
        vis_h = QtWidgets.QHBoxLayout(vis_container); vis_h.setContentsMargins(0,0,0,0)
        self.rb_public = QtWidgets.QRadioButton("Publique"); self.rb_private = QtWidgets.QRadioButton("Privée")
        self.rb_public.setChecked(True)
        vis_h.addWidget(self.rb_public); vis_h.addWidget(self.rb_private)
        create_layout.addRow("Visibilité", vis_container)
        self.btn_create = QtWidgets.QPushButton("Créer la salle")
        self.btn_create.clicked.connect(self._create_room)
        create_layout.addRow(self.btn_create)

        # -- Rejoindre par code --
        self.grp_join = QtWidgets.QGroupBox("Rejoindre une salle")
        two_col.addWidget(self.grp_join, 1)
        join_layout = QtWidgets.QFormLayout(self.grp_join)
        self.inp_code = QtWidgets.QLineEdit(); self.inp_code.setMaxLength(6)
        self.inp_code.setPlaceholderText("ABC123"); self.inp_code.textChanged.connect(self._uppercase_code)
        join_layout.addRow("Code (A-Z/0-9, 6)", self.inp_code)
        self.btn_join = QtWidgets.QPushButton("Rejoindre")
        self.btn_join.clicked.connect(self._join_code)
        join_layout.addRow(self.btn_join)

        # === Salles publiques ===
        self.grp_public = QtWidgets.QGroupBox("Salles publiques en cours")
        root.addWidget(self.grp_public, 2)
        pub_v = QtWidgets.QVBoxLayout(self.grp_public)
        hb_pub = QtWidgets.QHBoxLayout()
        hb_pub.addStretch()
        self.btn_refresh_pub = QtWidgets.QPushButton("Rafraîchir"); self.btn_refresh_pub.clicked.connect(self._refresh_public)
        hb_pub.addWidget(self.btn_refresh_pub)
        pub_v.addLayout(hb_pub)
        self.lst_public = QtWidgets.QListWidget(); self.lst_public.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        pub_v.addWidget(self.lst_public, 1)
        self.btn_join_public = QtWidgets.QPushButton("Rejoindre la salle sélectionnée")
        self.btn_join_public.clicked.connect(self._join_selected_public)
        pub_v.addWidget(self.btn_join_public)

        # === Classements ===
        two_col2 = QtWidgets.QHBoxLayout(); two_col2.setSpacing(12)
        root.addLayout(two_col2, 1)

        # Top joueurs
        self.grp_top_players = QtWidgets.QGroupBox("Top 10 joueurs (Wins)")
        two_col2.addWidget(self.grp_top_players, 1)
        tp_v = QtWidgets.QVBoxLayout(self.grp_top_players)
        self.lst_top_players = QtWidgets.QListWidget()
        tp_v.addWidget(self.lst_top_players)

        # Top contributeurs + bouton Proposer question
        self.grp_top_props = QtWidgets.QGroupBox("Top 10 contributeurs (Questions approuvées)")
        two_col2.addWidget(self.grp_top_props, 1)
        tpr_v = QtWidgets.QVBoxLayout(self.grp_top_props)

        # BOUTON demandé : "Proposer question" -> page Suggest
        self.btn_suggest = QtWidgets.QPushButton("Proposer question")
        self.btn_suggest.clicked.connect(lambda: self.sig_goto_suggest.emit())
        tpr_v.addWidget(self.btn_suggest)

        self.lst_top_props = QtWidgets.QListWidget()
        tpr_v.addWidget(self.lst_top_props)

        # Erreurs
        self.lbl_err = QtWidgets.QLabel(""); self.lbl_err.setStyleSheet("color:#ff8b8b;")
        root.addWidget(self.lbl_err)
        root.addStretch()

        # états
        self._busy_create = False
        self._busy_join = False
        self._refreshing = False

    # ------------- API helpers -------------
    def set_user(self, user: Dict[str, Any]):
        self._user = user
        name = user.get("username") or user.get("email") or "Utilisateur"
        self.title.setText(f"<h2>Lobby — {name}</h2>")

    def refresh_rooms(self, client):
        self._client = client
        self._load_leaderboards()
        self._load_public()

    # ------------- Actions UI -------------
    def _uppercase_code(self, text: str):
        import re
        t = re.sub(r"[^A-Za-z0-9]", "", text).upper()
        if t != text:
            pos = self.inp_code.cursorPosition()
            self.inp_code.setText(t)
            self.inp_code.setCursorPosition(min(pos, len(t)))

    @QtCore.Slot()
    def _create_room(self):
        c = self._client
        if not c or self._busy_create: return
        self._error("")
        self._busy_create = True; self.btn_create.setEnabled(False)
        name = self.inp_room_name.text().strip()
        visibility = "private" if self.rb_private.isChecked() else "public"
        try:
            payload = {"visibility": visibility}
            if name: payload["name"] = name
            r = c.sess.post(f"{c.api_base}/rooms", json=payload)
            data = r.json() if "application/json" in (r.headers.get("content-type") or "") else {}
            if not r.ok: raise RuntimeError(str(data.get("error") or "Erreur lors de la création"))
            code = (data.get("room") or {}).get("code") or data.get("code")
            if not code: raise RuntimeError("Code de salle manquant (réponse API)")
            self.sig_enter_room.emit(str(code).upper())
        except Exception as e:
            self._error(str(e))
        finally:
            self._busy_create = False; self.btn_create.setEnabled(True)

    @QtCore.Slot()
    def _join_code(self):
        c = self._client
        if not c or self._busy_join: return
        self._error("")
        code = (self.inp_code.text() or "").upper().strip()
        if not ALNUM6.match(code):
            self._error("Code invalide (6 caractères A-Z/0-9)")
            return
        self._busy_join = True; self.btn_join.setEnabled(False)
        try:
            r = c.sess.post(f"{c.api_base}/rooms/{code}/join", json={})
            data = r.json() if "application/json" in (r.headers.get("content-type") or "") else {}
            if not r.ok: raise RuntimeError(str(data.get("error") or "Impossible de rejoindre la salle"))
            self.sig_enter_room.emit(code)
        except Exception as e:
            self._error(str(e))
        finally:
            self._busy_join = False; self.btn_join.setEnabled(True)

    @QtCore.Slot()
    def _refresh_public(self):
        self._load_public(force=True)

    @QtCore.Slot()
    def _join_selected_public(self):
        item = self.lst_public.currentItem()
        if not item: return
        code = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if code: self._join_public(code)

    # ------------- Chargement données -------------
    def _load_public(self, force: bool=False):
        c = self._client
        if not c: return
        if self._refreshing: return
        self._refreshing = True; self.btn_refresh_pub.setEnabled(False)
        try:
            r = c.sess.get(f"{c.api_base}/rooms/public")
            data = r.json() if "application/json" in (r.headers.get("content-type") or "") else {}
            rooms = data.get("rooms") or []
            shown = []
            for x in rooms:
                try:
                    code = str(x.get("code") or "")
                    name = (None if x.get("name") is None else str(x.get("name")))
                    status = str(x.get("status") or "lobby")
                    if status not in ("running", "ended"): status = "lobby"
                    players = int(x.get("players") or 0)
                    maxp = int(x.get("maxPlayers") or 10)
                    if players > 0 and code:
                        shown.append({"code":code, "name":name, "status":status, "players":players, "maxPlayers":maxp})
                except Exception:
                    continue
            self.lst_public.clear()
            for rinfo in shown:
                label = f"{rinfo['name'] or ('Salle ' + rinfo['code'])}  [{rinfo['code']}]  —  {rinfo['players']}/{rinfo['maxPlayers']} · " + \
                        ("En cours" if rinfo["status"] == "running" else "Salle d'attente")
                it = QtWidgets.QListWidgetItem(label)
                it.setData(QtCore.Qt.ItemDataRole.UserRole, rinfo["code"])
                self.lst_public.addItem(it)
        except Exception as e:
            self.lst_public.clear()
            self._error(f"Impossible de charger les salles publiques : {e}")
        finally:
            self._refreshing = False; self.btn_refresh_pub.setEnabled(True)

    def _load_leaderboards(self):
        c = self._client
        if not c: return
        # Top joueurs
        try:
            r = c.sess.get(f"{c.api_base}/leaderboard")
            d = r.json() if "application/json" in (r.headers.get("content-type") or "") else {}
            arr = d.get("leaders") or d.get("top") or (d if isinstance(d, list) else [])
            norm = []
            for u in arr[:10]:
                try:
                    norm.append({"username": str(u.get("username") or ""), "wins": int(u.get("wins") or 0)})
                except Exception:
                    continue
            self.lst_top_players.clear()
            if not norm: self.lst_top_players.addItem("Pas encore de classement.")
            else:
                for i, u in enumerate(norm, start=1):
                    self.lst_top_players.addItem(f"{i}. {u['username']} — {u['wins']} wins")
        except Exception:
            self.lst_top_players.clear(); self.lst_top_players.addItem("Pas encore de classement.")

        # Top contributeurs
        try:
            r = c.sess.get(f"{c.api_base}/leaderboard/proposers")
            d = r.json() if "application/json" in (r.headers.get("content-type") or "") else {}
            arr = d.get("proposers") or (d if isinstance(d, list) else [])
            norm = []
            for u in arr[:10]:
                try:
                    norm.append({"username": str(u.get("username") or ""), "approvedCount": int(u.get("approvedCount") or 0)})
                except Exception:
                    continue
            self.lst_top_props.clear()
            if not norm: self.lst_top_props.addItem("Aucun contributeur pour le moment.")
            else:
                for i, u in enumerate(norm, start=1):
                    self.lst_top_props.addItem(f"{i}. {u['username']} — {u['approvedCount']} approuvées")
        except Exception:
            self.lst_top_props.clear(); self.lst_top_props.addItem("Aucun contributeur pour le moment.")

    # ------------- Helpers -------------
    def _join_public(self, code: str):
        c = self._client
        if not c: return
        self._error("")
        try:
            r = c.sess.post(f"{c.api_base}/rooms/{code}/join", json={})
            data = r.json() if "application/json" in (r.headers.get("content-type") or "") else {}
            if not r.ok: raise RuntimeError(str(data.get("error") or "Impossible de rejoindre la salle"))
            self.sig_enter_room.emit(code)
        except Exception as e:
            self._error(str(e))

    def _error(self, msg: str):
        self.lbl_err.setText(msg or "")
        if msg: self.sig_error.emit(msg)
