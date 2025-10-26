# ui_room.py
from __future__ import annotations
import os, sys, base64, time
from typing import Optional, Dict, Any, List, Callable

from PySide6 import QtWidgets, QtCore, QtGui
from niwot_client import NiwotClient


def resource_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, name)


# -------------------- Dialog Paramètres --------------------
class RoomSettingsDialog(QtWidgets.QDialog):
    """Modal Paramètres de salle (proche de la webapp)."""
    def __init__(
        self,
        parent=None,
        *,
        is_private: bool = False,
        max_players: int = 10,
        answer_time_sec: int = 15,
        target_points: int = 100,
        scoring: str = "degressif",           # "degressif" | "fixe"
        show_proposals: bool = True,
        categories: List[Dict[str, Any]] = None,  # [{id,name,approvedCount?}]
        selected_cat_ids: List[int] = None,
        result_delay_sec: int = 5,
        excluded_usernames: List[str] = None,
        on_unban: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Paramètres de la salle")
        self.setModal(True)
        self._on_unban = on_unban

        cats = categories or []
        selected = set(selected_cat_ids or [])
        ex_users = excluded_usernames or []

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)

        # --- Colonne Salle ---
        group_room = QtWidgets.QGroupBox("Salle")
        fr = QtWidgets.QFormLayout(group_room)
        fr.setLabelAlignment(QtCore.Qt.AlignLeft)

        self.cmb_visibility = QtWidgets.QComboBox()
        self.cmb_visibility.addItems(["Publique", "Privée"])
        self.cmb_visibility.setCurrentIndex(1 if is_private else 0)

        self.spin_max = QtWidgets.QSpinBox(); self.spin_max.setRange(2, 999); self.spin_max.setValue(int(max_players))

        fr.addRow("Visibilité", self.cmb_visibility)
        fr.addRow("Joueurs max", self.spin_max)

        # --- Colonne Quiz ---
        group_quiz = QtWidgets.QGroupBox("Quiz")
        fq = QtWidgets.QFormLayout(group_quiz)
        fq.setLabelAlignment(QtCore.Qt.AlignLeft)

        self.spin_target = QtWidgets.QSpinBox(); self.spin_target.setRange(10, 1000); self.spin_target.setValue(int(target_points))
        self.spin_time   = QtWidgets.QSpinBox(); self.spin_time.setRange(5, 60); self.spin_time.setValue(int(answer_time_sec))

        self.cmb_scoring = QtWidgets.QComboBox()
        self.cmb_scoring.addItems(["Dégressif (10→1)", "Fixe (10)"])
        self.cmb_scoring.setCurrentIndex(1 if scoring == "fixe" else 0)

        self.chk_show = QtWidgets.QCheckBox("Afficher les propositions (hors bonnes réponses)")
        self.chk_show.setChecked(bool(show_proposals))

        fq.addRow("Points à atteindre", self.spin_target)
        fq.addRow("Temps par question (s)", self.spin_time)
        fq.addRow("Mode de points", self.cmb_scoring)
        fq.addRow(self.chk_show)

        # --- Ligne 1 du grid ---
        grid.addWidget(group_room, 0, 0)
        grid.addWidget(group_quiz, 0, 1)

        # --- Colonne Catégories ---
        group_cat = QtWidgets.QGroupBox("Catégories (optionnel)")
        vcat = QtWidgets.QVBoxLayout(group_cat)
        vcat.setContentsMargins(12, 12, 12, 12)
        self._cat_checks: List[QtWidgets.QCheckBox] = []

        if cats:
            scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
            cont = QtWidgets.QWidget()
            fl = QtWidgets.QFormLayout(cont)
            fl.setLabelAlignment(QtCore.Qt.AlignLeft)
            fl.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

            for c in cats:
                label_name = str(c.get('name','Catégorie'))
                ac = c.get('approvedCount')
                suffix = f" ({ac})" if isinstance(ac, (int,float)) else ""
                cb = QtWidgets.QCheckBox(f"{label_name}{suffix}")
                try:
                    cid = int(c.get("id"))
                except Exception:
                    cid = c.get("id")
                cb.setChecked(cid in selected)
                cb._cat_id = cid  # type: ignore
                self._cat_checks.append(cb)
                fl.addRow(cb)

            scroll.setWidget(cont)
            vcat.addWidget(scroll)
            hint = QtWidgets.QLabel("Si aucune catégorie n’est cochée, toutes les catégories seront utilisées.")
            hint.setStyleSheet("color: rgba(255,255,255,0.6); font-size:11px;")
            vcat.addWidget(hint)
        else:
            vcat.addWidget(QtWidgets.QLabel("Impossible de charger les catégories."))

        # --- Colonne Temporisations / bannis ---
        group_tempo = QtWidgets.QGroupBox("Temporisations & joueurs exclus")
        vt = QtWidgets.QVBoxLayout(group_tempo)
        vt.setContentsMargins(12, 12, 12, 12)

        form_t = QtWidgets.QFormLayout()
        form_t.setLabelAlignment(QtCore.Qt.AlignLeft)
        self.spin_result_delay = QtWidgets.QSpinBox(); self.spin_result_delay.setRange(0, 10); self.spin_result_delay.setValue(int(result_delay_sec))
        form_t.addRow("Délai affichage correction (s)", self.spin_result_delay)
        vt.addLayout(form_t)

        vt.addWidget(QtWidgets.QLabel("Joueurs exclus :"))
        self._ban_list = QtWidgets.QListWidget()
        for u in ex_users:
            self._ban_list.addItem(QtWidgets.QListWidgetItem(u))
        vt.addWidget(self._ban_list)

        hban = QtWidgets.QHBoxLayout()
        self.btn_unban = QtWidgets.QPushButton("Réintégrer le joueur sélectionné")
        self.btn_unban.clicked.connect(self._on_unban_clicked)
        hban.addStretch(1); hban.addWidget(self.btn_unban)
        vt.addLayout(hban)

        # --- Ligne 2 du grid ---
        grid.addWidget(group_cat, 1, 0)
        grid.addWidget(group_tempo, 1, 1)

        lay.addLayout(grid)

        # --- Boutons ---
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _on_unban_clicked(self):
        items = self._ban_list.selectedItems()
        if not items or not self._on_unban: return
        self._on_unban(items[0].text())

    def refresh_banned(self, usernames: List[str]):
        self._ban_list.clear()
        for u in usernames:
            self._ban_list.addItem(QtWidgets.QListWidgetItem(u))

    def values(self) -> Dict[str, Any]:
        cat_ids: List[int] = []
        for cb in self._cat_checks:
            if cb.isChecked():
                cat_ids.append(getattr(cb, "_cat_id"))  # peut être int ou str
        return {
            "private": (self.cmb_visibility.currentIndex() == 1),
            "maxPlayers": int(self.spin_max.value()),
            "answerTimeSec": int(self.spin_time.value()),
            "targetPoints": int(self.spin_target.value()),
            "scoring": "fixe" if self.cmb_scoring.currentIndex() == 1 else "degressif",
            "showProposals": bool(self.chk_show.isChecked()),
            "categories": cat_ids,
            "resultDelaySec": int(self.spin_result_delay.value()),
            "approvedOnly": True,
            "preCountdownSec": 0,
            "types": ["CITATION", "IMAGE", "TEXT"],
        }


# -------------------- Widget Salle --------------------
class RoomWidget(QtWidgets.QWidget):
    sig_leave = QtCore.Signal()        # MainWindow -> retour lobby
    sig_goto_quiz = QtCore.Signal()    # MainWindow -> affiche page quiz

    # ✅ nouveau signal pour déclencher un quiz:sync côté thread UI
    sig_request_quiz_sync = QtCore.Signal(int)  # delay_ms

    def __init__(self):
        super().__init__()
        self._client: Optional[NiwotClient] = None
        self.room_code: Optional[str] = None

        # état
        self._me: Optional[Dict[str, Any]] = None
        self._is_host: bool = False
        self._host_user_id: Optional[int] = None
        self._players: List[Dict[str, Any]] = []
        self._max_players: Optional[int] = None
        self._target_points: Optional[int] = None
        self._show_proposals: bool = True
        self._answer_time_sec: Optional[int] = None
        self._scoring: str = "degressif"
        self._is_private: bool = False
        self._categories: List[Dict[str, Any]] = []  # [{id,name,approvedCount}]
        self._selected_cat_ids: List[int] = []
        self._result_delay_sec: int = 5
        self._excluded_usernames: List[str] = []
        self._title: str = ""

        # throttle pour refresh HTTP
        self._last_sync_http_ms = 0

        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(12)

        # Header
        header = QtWidgets.QGroupBox(); header.setTitle("")
        root.addWidget(header)
        h = QtWidgets.QHBoxLayout(header); h.setContentsMargins(16, 16, 16, 16)

        self.lbl_title = QtWidgets.QLabel("Salle")
        self.lbl_title.setStyleSheet("font-size:16px; font-weight:600;")
        self.lbl_code  = QtWidgets.QLabel(""); self.lbl_code.setStyleSheet("color:#aab2e6;")

        title_col = QtWidgets.QVBoxLayout()
        title_col.addWidget(self.lbl_title); title_col.addWidget(self.lbl_code)
        h.addLayout(title_col, 1)

        h_btns = QtWidgets.QHBoxLayout()
        self.btn_quit = QtWidgets.QPushButton("Quitter")
        self.btn_params = QtWidgets.QPushButton("Paramètres")
        self.btn_start = QtWidgets.QPushButton("Démarrer le quiz")
        self.btn_params.setVisible(False); self.btn_start.setVisible(False)
        self.btn_quit.clicked.connect(self._on_quit_clicked)
        self.btn_start.clicked.connect(self._on_start_clicked)
        self.btn_params.clicked.connect(self._on_params_clicked)
        h_btns.addWidget(self.btn_quit); h_btns.addWidget(self.btn_params); h_btns.addWidget(self.btn_start)
        h.addLayout(h_btns)

        # Joueurs
        card_players = QtWidgets.QGroupBox("Joueurs")
        root.addWidget(card_players)
        vp = QtWidgets.QVBoxLayout(card_players); vp.setContentsMargins(16,16,16,16)
        self.lbl_count = QtWidgets.QLabel(""); self.lbl_count.setStyleSheet("color:#aab2e6;")
        vp.addWidget(self.lbl_count)
        self.list_widget = QtWidgets.QListWidget(); self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        vp.addWidget(self.list_widget)

        root.addStretch()

        # 🔗 connecter le signal thread-safe -> slot local
        self.sig_request_quiz_sync.connect(self._do_delayed_quiz_sync)

    # ---------- Wiring ----------
    def set_client(self, client: NiwotClient):
        self._client = client

    def set_room(self, code: str):
        self.room_code = code.upper().strip()
        # reset
        self._title = ""; self._host_user_id = None; self._players = []; self._is_host = False
        self._max_players = None; self._target_points = None; self._show_proposals = True
        self._answer_time_sec = None; self._scoring = "degressif"; self._is_private = False
        self._selected_cat_ids = []; self._result_delay_sec = 5; self._excluded_usernames = []
        self._me = None
        self._render_header(); self._render_players()
        QtCore.QTimer.singleShot(0, self._load_http_then_join)

    # ---------- HTTP + Socket ----------
    def _load_http_then_join(self):
        if not self._client or not self.room_code: return
        try:
            me = self._client.me()
            if me.get("ok"): self._me = me["user"]
        except Exception: pass

        # premier état HTTP
        self._refresh_room_http()

        # Charger les catégories
        try:
            cats = self._client.get_categories()
            if cats.get("ok") and isinstance(cats.get("categories"), list):
                self._categories = cats["categories"]
        except Exception:
            pass

        # Socket join
        self._ensure_socket()
        payload = {
            "code": self.room_code,
            "username": (self._me or {}).get("username"),
            "userId": (self._me or {}).get("id"),
            "avatar": (self._me or {}).get("profileImage"),
        }
        self._emit("room:join", payload)
        # demande un état complet côté WS — exécuté ici dans le thread UI
        QtCore.QTimer.singleShot(150, lambda: self._emit("room:sync", {"code": self.room_code}))

    def _ensure_socket(self):
        if not self._client: return
        try: self._client.connect_socket()
        except Exception: pass

    def _emit(self, event: str, data: dict, ack=None):
        if not self._client: return
        try:
            if ack: self._client.socket_emit(event, data, ack=ack)
            else:   self._client.socket_emit(event, data)
        except Exception:
            sio = getattr(self._client, "sio", None)
            if sio and getattr(sio, "emit", None):
                if ack: sio.emit(event, data, callback=ack)
                else: sio.emit(event, data)

    # ---------- UI ----------
    def _render_header(self):
        title = self._title or (self.room_code and f"Salle {self.room_code}") or "Salle"
        self.lbl_title.setText(title)
        self.lbl_code.setText(f"Code : <span style='font-family:monospace'>{self.room_code or ''}</span>")
        self.btn_start.setVisible(self._is_host is True)
        self.btn_params.setVisible(self._is_host is True)

    def _render_players(self):
        count = len(self._players)
        self.lbl_count.setText(f"{count} joueurs" if not self._max_players else f"{count} / {self._max_players} joueurs")
        self.list_widget.clear()
        for p in self._players:
            it = QtWidgets.QListWidgetItem()
            w = self._player_row(p); it.setSizeHint(w.sizeHint())
            self.list_widget.addItem(it); self.list_widget.setItemWidget(it, w)

    def _player_row(self, p: Dict[str, Any]) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w); h.setContentsMargins(6,4,6,4); h.setSpacing(8)
        avatar = QtWidgets.QLabel(); avatar.setFixedSize(36,36)
        avatar.setPixmap(self._avatar_pixmap(p.get("avatar")).scaled(36,36, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation))
        name = QtWidgets.QLabel(str(p.get("username") or ""))
        pts = QtWidgets.QLabel(f"{int(p.get('points') or 0)} pts"); pts.setStyleSheet("color:#aab2e6;")
        if p.get("userId") == self._host_user_id:
            name.setText(name.text() + "  <span style='font-size:11px; color:#aab2e6'>(Hôte)</span>")
        hl = QtWidgets.QHBoxLayout(); hl.addWidget(name, 1); hl.addWidget(pts, 0, QtCore.Qt.AlignRight)
        container = QtWidgets.QWidget(); container.setLayout(hl)
        h.addWidget(avatar); h.addWidget(container, 1)
        return w

    # ---------- Actions ----------
    def _on_quit_clicked(self):
        if not self._client or not self.room_code:
            self.sig_leave.emit(); return
        try: self._emit("room:leave", {"code": self.room_code})
        except Exception: pass
        self.sig_leave.emit()

    def _on_start_clicked(self):
        if not self._client or not self.room_code: return

        def _ack(ack: Any):
            ok = bool(isinstance(ack, dict) and ack.get("ok"))
            if ok:
                # ⚠️ NE PAS lancer de QTimer ici (thread socket)
                self.sig_goto_quiz.emit()
                # demander un quiz:sync côté thread UI
                self.sig_request_quiz_sync.emit(150)
            else:
                err = (ack or {}).get("error") if isinstance(ack, dict) else None
                QtWidgets.QMessageBox.warning(self, "Démarrer", f"Impossible de démarrer : {err or 'erreur'}")

        self._emit("room:start", {"code": self.room_code}, ack=_ack)

        # 🔒 filet de sécurité : ceci s'exécute DANS le thread UI, donc OK
        QtCore.QTimer.singleShot(2000, lambda: self._emit("quiz:sync", {"code": self.room_code}))

    @QtCore.Slot(int)
    def _do_delayed_quiz_sync(self, delay_ms: int):
        """Slot exécuté dans le thread UI -> peut utiliser QTimer sans crash."""
        QtCore.QTimer.singleShot(delay_ms, lambda: self._emit("quiz:sync", {"code": self.room_code}))

    def _on_params_clicked(self):
        # Assure d’avoir les catégories
        if not self._categories:
            try:
                cats = self._client.get_categories()
                if cats.get("ok") and isinstance(cats.get("categories"), list):
                    self._categories = cats["categories"]
            except Exception:
                pass

        dlg = RoomSettingsDialog(
            self,
            is_private=self._is_private,
            max_players=self._max_players or max(2, len(self._players)),
            answer_time_sec=self._answer_time_sec or 15,
            target_points=self._target_points or 100,
            scoring=self._scoring,
            show_proposals=self._show_proposals,
            categories=self._categories,
            selected_cat_ids=self._selected_cat_ids,
            result_delay_sec=self._result_delay_sec,
            excluded_usernames=self._excluded_usernames,
            on_unban=self._on_unban_username,
        )
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            params = dlg.values()
            # MAJ état local
            self._is_private       = bool(params["private"])
            self._max_players      = int(params["maxPlayers"])
            self._answer_time_sec  = int(params["answerTimeSec"])
            self._target_points    = int(params["targetPoints"])
            self._scoring          = str(params["scoring"])
            self._show_proposals   = bool(params["showProposals"])
            self._selected_cat_ids = list(params["categories"])
            self._result_delay_sec = int(params["resultDelaySec"])
            self._render_header()

            # Envoi WS + fallback HTTP
            self._emit("room:config", {"code": self.room_code, "params": params})
            try:
                if self._client:
                    url = f"{self._client.api_base}/rooms/{self.room_code}/settings"
                    http_body = {
                        "visibility": "private" if self._is_private else "public",
                        "maxPlayers": self._max_players,
                        "categories": self._selected_cat_ids,
                        "answerTimeSec": self._answer_time_sec,
                        "targetPoints": self._target_points,
                        "pointMode": "fixed" if self._scoring == "fixe" else "degressive",
                        "showProposals": self._show_proposals,
                        "resultDelaySec": self._result_delay_sec,
                    }
                    self._client.sess.put(url, json=http_body, timeout=8)  # type: ignore
            except Exception:
                pass

    def _on_unban_username(self, username: str):
        if not self._client or not self.room_code or not username: return
        def _ack(ack: Any):
            if isinstance(ack, dict) and isinstance(ack.get("excludedUsernames"), list):
                self._excluded_usernames = list(map(str, ack["excludedUsernames"]))
                for w in self.findChildren(RoomSettingsDialog):
                    w.refresh_banned(self._excluded_usernames)
        self._emit("room:unban", {"code": self.room_code, "username": username}, ack=_ack)

    # ---------- Socket messages ----------
    def on_message(self, event: str, payload: Any):
        if not isinstance(event, str): return

        # 1) Évènements de démarrage => redirection quiz
        if event in {"quiz:question", "quiz:started", "room:started", "room:running", "game:started"}:
            self.sig_goto_quiz.emit()
            return

        # 2) Évènements de mise à jour "room"
        if event.startswith("room:"):
            if event == "room:update" and isinstance(payload, dict):
                self._apply_room_payload(payload)
                return

            if event in {"room:join", "room:joined", "room:left", "room:leave",
                         "room:memberJoined", "room:memberLeft", "room:players",
                         "room:members", "room:sync"}:
                updated = self._apply_room_payload(payload)
                if not updated:
                    self._emit("room:sync", {"code": self.room_code})
                    self._refresh_room_http(throttled=True)
                return

        self._apply_room_payload(payload)

    # ---------- Appliquer payload room ----------
    def _apply_room_payload(self, payload: Any) -> bool:
        changed = False
        if not isinstance(payload, dict): return False

        code = (str(payload.get("code") or "")).upper()
        if code and self.room_code and code != self.room_code:
            return False

        if "hostUserId" in payload:
            self._host_user_id = payload.get("hostUserId", self._host_user_id); changed = True

        params = payload.get("params") or payload.get("settings") or {}
        if isinstance(params, dict) and params:
            self._is_private      = bool(params.get("private", self._is_private))
            self._max_players     = params.get("maxPlayers", self._max_players)
            self._answer_time_sec = params.get("answerTimeSec", self._answer_time_sec)
            self._target_points   = params.get("targetPoints", self._target_points)
            self._scoring         = str(params.get("scoring", self._scoring))
            sp = params.get("showProposals")
            if sp is not None: self._show_proposals = bool(sp)
            cats = params.get("categories")
            if isinstance(cats, list):
                self._selected_cat_ids = list(cats)
            rds = params.get("resultDelaySec")
            if rds is not None:
                try: self._result_delay_sec = int(rds)
                except Exception: pass
            ex = params.get("excludedUsernames")
            if isinstance(ex, list):
                self._excluded_usernames = [str(x) for x in ex]
            changed = True

        players = None
        if isinstance(payload.get("players"), list):
            players = payload["players"]
        elif isinstance(payload.get("members"), list):
            players = payload["members"]
        elif isinstance(payload.get("room"), dict):
            r = payload["room"]
            if isinstance(r.get("members"), list):
                players = r["members"]

        if isinstance(players, list):
            self._players = [
                {
                    "userId": p.get("userId"),
                    "username": p.get("username"),
                    "avatar": p.get("avatar") or p.get("profileImage"),
                    "points": p.get("points", 0),
                }
                for p in players if isinstance(p, dict)
            ]
            changed = True

        if self._me and self._host_user_id is not None:
            self._is_host = bool(self._host_user_id == self._me.get("id"))

        if changed:
            self._render_header()
            self._render_players()
        return changed

    # ---------- HTTP refresh (throttle) ----------
    def _refresh_room_http(self, throttled: bool = False):
        if not self._client or not self.room_code: return
        now = int(time.time() * 1000)
        if throttled and now - self._last_sync_http_ms < 800:  # max ~1 req/s
            return
        self._last_sync_http_ms = now
        try:
            url = f"{self._client.api_base}/rooms/{self.room_code}"
            r = self._client.sess.get(url, timeout=8)  # type: ignore
            if not r.ok: return
            room = r.json().get("room", {})
            self._title = room.get("name") or self._title
            self._host_user_id = room.get("hostId", self._host_user_id)
            settings = room.get("settings") or {}
            if settings:
                self._max_players = settings.get("maxPlayers", self._max_players)
                self._target_points = settings.get("TargetPoints", settings.get("targetPoints", self._target_points))
                self._answer_time_sec = settings.get("answerTimeSec", self._answer_time_sec)
                self._show_proposals = bool(settings.get("showProposals", self._show_proposals))
            mems = room.get("members") or []
            self._players = [
                {"userId": m.get("userId"), "username": m.get("username"), "avatar": m.get("profileImage"), "points": m.get("points", 0)}
                for m in mems
            ]
            if self._me and self._host_user_id is not None:
                self._is_host = bool(self._host_user_id == self._me.get("id"))
            self._render_header(); self._render_players()
        except Exception:
            pass

    # ---------- media ----------
    def _avatar_pixmap(self, raw: Any) -> QtGui.QPixmap:
        fallback = QtGui.QPixmap(resource_path("niwotfren.png"))
        if isinstance(raw, dict):
            for k in ("url","href","src","path"):
                if isinstance(raw.get(k), str) and raw.get(k):
                    raw = raw.get(k); break
        if not isinstance(raw, str) or not raw.strip(): return fallback
        v = raw.strip()
        if v.startswith("data:"):
            try:
                b64 = v.split(",",1)[1]
                img = QtGui.QImage.fromData(base64.b64decode(b64))
                if not img.isNull(): return QtGui.QPixmap.fromImage(img)
            except Exception: return fallback
            return fallback
        url = v
        if not (url.startswith("http://") or url.startswith("https://")) and self._client:
            base = str(getattr(self._client, "api_base", "")).rstrip("/")
            if base:
                url = (base + url) if url.startswith("/") else (base + "/" + url)
        if self._client:
            try:
                r = self._client.sess.get(url, timeout=6)  # type: ignore
                if r.ok:
                    img = QtGui.QImage.fromData(r.content)
                    if not img.isNull(): return QtGui.QPixmap.fromImage(img)
            except Exception:
                return fallback
        return fallback
