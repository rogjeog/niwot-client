# ui_quiz.py
from __future__ import annotations
import os, sys, time, base64
from typing import Any, Dict, List, Optional

from PySide6 import QtWidgets, QtCore, QtGui
from niwot_client import NiwotClient


def resource_path(name: str) -> str:
    """Chemin d'une ressource packagée (compatible PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, name)


def _abs_media_url(path_or_url: Optional[str], api_base: str) -> Optional[str]:
    if not path_or_url:
        return None
    v = str(path_or_url)
    if v.startswith("http://") or v.startswith("https://"):
        return v
    api_base = (api_base or "").rstrip("/")
    if not api_base:
        return v
    if v.startswith("/"):
        return api_base + v
    return api_base + "/" + v


class QuizWidget(QtWidgets.QWidget):
    """
    Implémentation PySide6 alignée sur la page web Quiz:
    - Events écoutés: room:update, room:started, quiz:question, quiz:proposals, quiz:result, quiz:ended, quiz:gotoRoom
    - Emissions: room:join, room:leave, quiz:sync, quiz:answer, quiz:restart, quiz:gotoRoom
    - Etat local: room, question, proposals, result, serverDrift, endsAt
    """
    sig_quit = QtCore.Signal()
    sig_goto_room = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self._client: Optional[NiwotClient] = None
        self.room_code: str = ""

        # Etat utilisateur / room
        self._me: Optional[Dict[str, Any]] = None
        self._room: Optional[Dict[str, Any]] = None  # RoomWS
        self._is_host: bool = False

        # Etat quiz
        self._question: Optional[Dict[str, Any]] = None  # { id, text, type, citationText?, imagePath? }
        self._proposals: List[Dict[str, Any]] = []       # [{ userId, username, avatar, points, guess }]
        self._result: Optional[Dict[str, Any]] = None    # { correct, first?, explanation? }
        self._game_ended: Optional[Dict[str, Any]] = None

        self._server_drift_ms: int = 0
        self._ends_at_ms: Optional[int] = None
        self._answered_correct: bool = False

        # --- UI ---
        self.setObjectName("quiz-root")
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # TOP BAR (Quitter + Infos)
        top_card = QtWidgets.QGroupBox()
        top_card.setStyleSheet("QGroupBox{ border:1px solid rgba(255,255,255,0.1); border-radius:12px; }")
        top_h = QtWidgets.QHBoxLayout(top_card)
        top_h.setContentsMargins(12, 12, 12, 12)
        top_h.setSpacing(8)

        left_h = QtWidgets.QHBoxLayout()
        self.btn_quit = QtWidgets.QPushButton("Quitter le quiz")
        self.btn_quit.clicked.connect(self._on_quit)
        self.lbl_room_small = QtWidgets.QLabel("")   # "Salle CODE • Objectif : XX pts"
        self.lbl_room_small.setStyleSheet("color:#bfc7ff;")
        left_h.addWidget(self.btn_quit)
        left_h.addSpacing(8)
        left_h.addWidget(self.lbl_room_small)
        left_h.addStretch(1)

        right_h = QtWidgets.QHBoxLayout()
        self.lbl_host_and_time = QtWidgets.QLabel("En attente du quiz…")
        self.lbl_host_and_time.setStyleSheet("color:#bfc7ff;")
        right_h.addWidget(self.lbl_host_and_time)

        top_h.addLayout(left_h, 1)
        top_h.addLayout(right_h, 0)

        root.addWidget(top_card, 0)

        # GRID deux colonnes
        grid = QtWidgets.QHBoxLayout()
        grid.setSpacing(12)
        root.addLayout(grid, 1)

        # --- Colonne Question ---
        q_col = QtWidgets.QVBoxLayout()
        q_card = QtWidgets.QGroupBox()
        q_card.setStyleSheet("QGroupBox{ border:1px solid rgba(255,255,255,0.1); border-radius:12px; }")
        q_v = QtWidgets.QVBoxLayout(q_card)
        q_v.setContentsMargins(16, 16, 16, 16)
        q_v.setSpacing(12)

        self.lbl_question_text = QtWidgets.QLabel("En attente de la première question…")
        self.lbl_question_text.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_question_text.setWordWrap(True)
        self.lbl_question_text.setStyleSheet("font-size:18px; font-weight:600;")
        q_v.addWidget(self.lbl_question_text)

        # Zone indice (citation / image / résultat)
        self.stack_hint = QtWidgets.QStackedWidget()
        # 0: empty
        self.page_empty = QtWidgets.QWidget()
        self.stack_hint.addWidget(self.page_empty)
        # 1: citation
        self.page_cit = QtWidgets.QWidget()
        cit_l = QtWidgets.QVBoxLayout(self.page_cit)
        cit_l.setContentsMargins(0, 0, 0, 0)
        self.lbl_citation = QtWidgets.QLabel("")
        self.lbl_citation.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_citation.setWordWrap(True)
        self.lbl_citation.setStyleSheet("font-style: italic;")
        cit_l.addWidget(self.lbl_citation)
        self.stack_hint.addWidget(self.page_cit)
        # 2: image
        self.page_img = QtWidgets.QWidget()
        img_l = QtWidgets.QVBoxLayout(self.page_img)
        img_l.setContentsMargins(0, 0, 0, 0)
        self.lbl_image = QtWidgets.QLabel("")
        self.lbl_image.setAlignment(QtCore.Qt.AlignCenter)
        img_l.addWidget(self.lbl_image)
        self.stack_hint.addWidget(self.page_img)
        # 3: résultat
        self.page_res = QtWidgets.QWidget()
        res_l = QtWidgets.QVBoxLayout(self.page_res)
        res_l.setContentsMargins(0, 0, 0, 0)
        self.lbl_result = QtWidgets.QLabel("")
        self.lbl_result.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_result.setWordWrap(True)
        res_l.addWidget(self.lbl_result)
        self.stack_hint.addWidget(self.page_res)

        q_v.addWidget(self.stack_hint, 1)

        # Saisie réponse
        form = QtWidgets.QVBoxLayout()
        form.setSpacing(6)
        lab = QtWidgets.QLabel("Votre réponse")
        self.inp_answer = QtWidgets.QLineEdit()
        self.inp_answer.setPlaceholderText("Tapez votre réponse…")
        self.inp_answer.returnPressed.connect(self._submit)
        self.btn_send = QtWidgets.QPushButton("Envoyer")
        self.btn_send.clicked.connect(self._submit)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.inp_answer, 1)
        row.addWidget(self.btn_send, 0)
        self.lbl_status = QtWidgets.QLabel("")
        form.addWidget(lab)
        form.addLayout(row)
        form.addWidget(self.lbl_status)
        q_v.addLayout(form)

        q_col.addWidget(q_card, 1)
        grid.addLayout(q_col, 2)

        # --- Colonne Joueurs ---
        p_col = QtWidgets.QVBoxLayout()
        p_card = QtWidgets.QGroupBox("Joueurs")
        p_card.setStyleSheet("QGroupBox{ border:1px solid rgba(255,255,255,0.1); border-radius:12px; }")
        p_v = QtWidgets.QVBoxLayout(p_card)
        p_v.setContentsMargins(16, 16, 16, 16)
        p_v.setSpacing(8)

        self.list_players = QtWidgets.QListWidget()
        self.list_players.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        p_v.addWidget(self.list_players)
        p_col.addWidget(p_card, 1)
        grid.addLayout(p_col, 1)

        # --- Timers UI (strictement dans le thread UI) ---
        self._timer_now = QtCore.QTimer(self)
        self._timer_now.timeout.connect(self._tick)
        self._timer_now.start(200)

        # resync initial en cas de latence
        self._timer_resync = QtCore.QTimer(self)
        self._timer_resync.setSingleShot(True)
        self._timer_resync.timeout.connect(lambda: self._emit("quiz:sync", {"code": self.room_code}))
        self._resync_started_once = False

    # ========== Wiring externe ==========
    def set_client(self, client: NiwotClient):
        self._client = client

    def set_room(self, code: str):
        self.room_code = (code or "").upper().strip()
        self._reset_state()
        # Affiche le code salle en haut
        self._update_topbar()
        # Join + sync (même logique que la webapp)
        QtCore.QTimer.singleShot(0, self._join_and_sync)

    # ========== Emissions ==========
    def _emit(self, event: str, data: dict, ack=None):
        if not self._client:
            return
        try:
            if ack:
                self._client.socket_emit(event, data, ack=ack)
            else:
                self._client.socket_emit(event, data)
        except Exception:
            # Fallback direct
            sio = getattr(self._client, "sio", None)
            if sio and getattr(sio, "emit", None):
                if ack:
                    sio.emit(event, data, callback=ack)
                else:
                    sio.emit(event, data)

    # ========== Actions utilisateur ==========
    def _on_quit(self):
        if not self._client or not self.room_code:
            self.sig_quit.emit()
            return
        def _go(_=None):
            self.sig_quit.emit()
        try:
            self._emit("room:leave", {"code": self.room_code}, ack=_go)
            QtCore.QTimer.singleShot(500, _go)  # fallback
        except Exception:
            _go()

    def _submit(self):
        if not self._client or not self._question or not self.room_code:
            return
        if self._answered_correct or self._result is not None:
            return
        val = self.inp_answer.text().strip()
        if not val:
            return
        self.lbl_status.setText("")
        def _ack(ack: Any):
            if isinstance(ack, dict) and ack.get("correct"):
                self._answered_correct = True
                self.lbl_status.setStyleSheet("color:#69f0ae;")
                self.lbl_status.setText("Trouvé !")
            else:
                self.lbl_status.setStyleSheet("color:#ff8b8b;")
                self.lbl_status.setText("Faux !")
        self._emit("quiz:answer", {"code": self.room_code, "answer": val}, ack=_ack)

    # ========== Socket -> UI ==========
    def on_message(self, event: str, payload: Any):
        """
        Brancher ceci depuis main.py:
            client.sig_socket_message.connect(self.quiz.on_message)
        """
        # Sûr contre les events inattendus
        try:
            if event == "room:update":
                if isinstance(payload, dict):
                    self._room = payload
                    self._recompute_host_flag()
                    self._update_topbar()
                    # Si on n'est plus dans la room, retourner au lobby (même logique que web)
                    my_id = (self._me or {}).get("id")
                    if my_id and not any((p.get("userId")==my_id) for p in (payload.get("players") or [])):
                        self.sig_goto_room.emit()
                return

            if event == "room:started":
                # relancer une sync immédiate
                self._game_ended = None
                self._emit("quiz:sync", {"code": self.room_code})
                return

            if event == "quiz:question" and isinstance(payload, dict):
                self._apply_question(payload)
                return

            if event == "quiz:proposals":
                if isinstance(payload, list):
                    self._proposals = payload
                elif isinstance(payload, dict) and isinstance(payload.get("proposals"), list):
                    self._proposals = payload["proposals"]
                else:
                    self._proposals = []
                self._render_players()
                return

            if event == "quiz:result" and isinstance(payload, dict):
                self._result = payload
                self._render_result()
                return

            if event == "quiz:ended":
                self._game_ended = payload if isinstance(payload, dict) else {"reason": "Partie terminée"}
                # Affiche un dialog simple avec top; on reste cohérent avec web (overlay)
                self._show_end_dialog()
                return

            if event == "quiz:gotoRoom":
                # le backend peut envoyer url ou juste code
                self.sig_goto_room.emit()
                return

            if event in {"room:kicked", "room:banned"}:
                self.sig_goto_room.emit()
                return
        except Exception as e:
            # Ne JAMAIS crasher l'UI si une donnée est manquante
            # Affiche silencieusement dans la barre de statut
            self.lbl_status.setStyleSheet("color:#ff8b8b;")
            self.lbl_status.setText(f"Erreur: {type(e).__name__}")
            # et tenter une resync prudente
            self._safe_resync()

    # ========== Helpers d'état ==========
    def _join_and_sync(self):
        if not self._client or not self.room_code:
            return
        # /me
        try:
            me = self._client.me()
            if me and me.get("ok") and isinstance(me.get("user"), dict):
                self._me = me["user"]
        except Exception:
            self._me = None
        # connexion socket
        try:
            self._client.connect_socket()
        except Exception:
            pass
        # rejoindre
        payload = {
            "code": self.room_code,
            "username": (self._me or {}).get("username"),
            "userId": (self._me or {}).get("id"),
            "avatar": (self._me or {}).get("profileImage"),
        }
        self._emit("room:join", payload, ack=lambda _=None: None)
        # sync immédiate + rappel léger (comme web: setTimeout 800ms)
        self._emit("quiz:sync", {"code": self.room_code})
        if not self._resync_started_once:
            self._resync_started_once = True
            self._timer_resync.start(800)

    def _apply_question(self, p: Dict[str, Any]):
        # Web payload: { serverNow, params, question, startsAt, endsAt }
        try:
            client_now = int(time.time() * 1000)
            server_now = int(p.get("serverNow"))
            self._server_drift_ms = server_now - client_now
        except Exception:
            self._server_drift_ms = 0

        self._result = None
        self._proposals = []
        self._answered_correct = False
        self.inp_answer.clear()
        self.lbl_status.setText("")
        self.lbl_status.setStyleSheet("")

        q = p.get("question") if isinstance(p.get("question"), dict) else {}
        self._question = q if isinstance(q, dict) else {}

        # endsAt exact
        try:
            self._ends_at_ms = int(p.get("endsAt"))
        except Exception:
            self._ends_at_ms = None

        # Affichage question
        text = str(self._question.get("text") or "Question")
        q_type = str(self._question.get("type") or "").upper().strip()
        citation = self._question.get("citationText")
        img_path = self._question.get("imagePath")

        self.lbl_question_text.setText(text)

        self.stack_hint.setCurrentIndex(0)
        if q_type == "CITATION" and isinstance(citation, str) and citation.strip():
            self.lbl_citation.setText(f"“{citation.strip()}”")
            self.stack_hint.setCurrentIndex(1)
        elif q_type == "IMAGE" and img_path:
            pm = self._image_pixmap(img_path)
            if not pm.isNull():
                self.lbl_image.setPixmap(pm.scaledToHeight(360, QtCore.Qt.SmoothTransformation))
                self.stack_hint.setCurrentIndex(2)
            else:
                # Pas d'image dispo -> rester vide
                self.stack_hint.setCurrentIndex(0)
        else:
            # Type TEXT -> rien dans la zone indice
            self.stack_hint.setCurrentIndex(0)

        # Met à jour topbar (host, objectif, timer)
        self._update_topbar()
        # Render joueurs (reset des propositions)
        self._render_players()

    def _render_players(self):
        self.list_players.clear()
        # Map userId -> guess
        last_guess: Dict[int, str] = {}
        for item in (self._proposals or []):
            if isinstance(item, dict) and "userId" in item:
                g = item.get("guess")
                if isinstance(g, str):
                    last_guess[item["userId"]] = g

        players = (self._room or {}).get("players") or []
        for p in players:
            if not isinstance(p, dict):
                continue
            uid = p.get("userId")
            username = str(p.get("username") or "")
            pts = int(p.get("points") or 0)
            avatar = p.get("avatar")

            it = QtWidgets.QListWidgetItem()
            row = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(row)
            h.setContentsMargins(6, 6, 6, 6)
            h.setSpacing(8)

            lbl_avatar = QtWidgets.QLabel()
            lbl_avatar.setFixedSize(40, 40)
            pm = self._avatar_pixmap(avatar)
            if pm.isNull():
                pm = QtGui.QPixmap(resource_path("niwotfren.png"))
            lbl_avatar.setPixmap(pm.scaled(40, 40, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation))

            name = QtWidgets.QLabel(f"{username} ")
            pts_lbl = QtWidgets.QLabel(f"({pts} pts)")
            pts_lbl.setStyleSheet("color:#bfc7ff;")

            h.addWidget(lbl_avatar)
            v = QtWidgets.QVBoxLayout()
            v.setContentsMargins(0, 0, 0, 0)
            top_line = QtWidgets.QHBoxLayout()
            top_line.setContentsMargins(0, 0, 0, 0)
            top_line.addWidget(name)
            top_line.addWidget(pts_lbl)
            top_line.addStretch(1)
            # Badge hôte
            if self._room and uid == self._room.get("hostUserId"):
                badge = QtWidgets.QLabel("Hôte")
                badge.setStyleSheet("font-size:11px; padding:2px 6px; border:1px solid rgba(255,255,255,0.1); border-radius:8px;")
                top_line.addWidget(badge)
            v.addLayout(top_line)

            # Dernière proposition
            guess = last_guess.get(uid)
            sub = QtWidgets.QLabel(f"Proposition : <span style='font-family:monospace'>{guess}</span>" if guess else "<span style='color:#9aa0c6'>Aucune proposition</span>")
            sub.setTextFormat(QtCore.Qt.RichText)
            sub.setWordWrap(True)
            v.addWidget(sub)

            h.addLayout(v, 1)
            row.setLayout(h)
            it.setSizeHint(row.sizeHint())
            self.list_players.addItem(it)
            self.list_players.setItemWidget(it, row)

    def _render_result(self):
        r = self._result or {}
        correct = r.get("correct")
        first = r.get("first")
        explanation = r.get("explanation")
        parts = []
        if correct is not None:
            parts.append(f"<div style='color:#69f0ae; font-weight:600;'>Bonne réponse : <span style='font-family:monospace'>{correct}</span></div>")
        if first:
            parts.append(f"<div style='color:#e8ebff;'>Premier trouvé : <b>{first}</b></div>")
        if explanation:
            parts.append(f"<div style='color:#e8ebff; margin-top:6px;'>{explanation}</div>")
        if not parts:
            parts.append("<div>Correction affichée.</div>")
        parts.append("<div style='color:#9aa0c6; font-size:12px; margin-top:6px;'>Nouvelle question dans quelques secondes…</div>")

        self.lbl_result.setText("".join(parts))
        self.lbl_result.setTextFormat(QtCore.Qt.RichText)
        self.stack_hint.setCurrentIndex(3)

    def _show_end_dialog(self):
        # Simple message de fin (+ top si fourni)
        p = self._game_ended or {}
        top = p.get("top") or []
        msg = p.get("reason") or "Partie terminée"
        text = f"<h3 style='margin:0 0 8px 0;'>Partie terminée</h3><div style='color:#bfc7ff;'>{msg}</div>"
        if isinstance(top, list) and top:
            text += "<div style='margin-top:10px; color:#bfc7ff; font-size:13px;'>Top joueurs</div>"
            for i, t in enumerate(top, start=1):
                if not isinstance(t, dict):
                    continue
                text += f"<div>{i}. {t.get('username','?')} — {int(t.get('points') or 0)} pts</div>"
        QtWidgets.QMessageBox.information(self, "Quiz", text)

    def _recompute_host_flag(self):
        if not self._room or not self._me:
            self._is_host = False
            return
        self._is_host = (self._room.get("hostUserId") == self._me.get("id"))

    def _tick(self):
        # MAJ du bandeau (timer restant)
        self._update_topbar()

    def _update_topbar(self):
        # gauche: Salle CODE • Objectif : targetPoints
        target = None
        try:
            target = self._room.get("params", {}).get("targetPoints")
        except Exception:
            pass
        left_txt = f"Salle <span style='font-family:monospace'>{self.room_code}</span>"
        if target is not None:
            left_txt += f" <span style='color:#8ea0ff;'>•</span> Objectif : <span style='font-family:monospace'>{target} pts</span>"
        self.lbl_room_small.setText(left_txt)
        self.lbl_room_small.setTextFormat(QtCore.Qt.RichText)

        # droite: Hôte + temps restant
        host_name = "—"
        try:
            for p in (self._room or {}).get("players") or []:
                if p.get("userId") == (self._room or {}).get("hostUserId"):
                    host_name = p.get("username") or "—"
                    break
        except Exception:
            pass

        time_left_txt = "En attente du quiz…"
        if self._ends_at_ms is not None:
            client_now = int(time.time() * 1000)
            left_ms = max(0, int(self._ends_at_ms) - (client_now + int(self._server_drift_ms)))
            time_left_txt = f"Temps restant : <span style='font-family:monospace'>{(left_ms + 999)//1000}s</span>"

        self.lbl_host_and_time.setText(f"Hôte : <b>{host_name}</b> &nbsp; {time_left_txt}")
        self.lbl_host_and_time.setTextFormat(QtCore.Qt.RichText)

    def _safe_resync(self):
        if not self.room_code:
            return
        self._emit("quiz:sync", {"code": self.room_code})

    def _reset_state(self):
        self._room = None
        self._is_host = False
        self._question = None
        self._result = None
        self._proposals = []
        self._game_ended = None
        self._server_drift_ms = 0
        self._ends_at_ms = None
        self._answered_correct = False
        self.lbl_question_text.setText("En attente de la première question…")
        self.stack_hint.setCurrentIndex(0)
        self.lbl_citation.clear()
        self.lbl_image.clear()
        self.lbl_result.clear()
        self.inp_answer.clear()
        self.lbl_status.setText("")
        self.lbl_status.setStyleSheet("")
        self.list_players.clear()

    # ===== Utils images / avatars =====
    def _avatar_pixmap(self, raw: Any) -> QtGui.QPixmap:
        # data: URL, URL absolue, chemin relatif
        try:
            if not raw:
                return QtGui.QPixmap()
            if isinstance(raw, dict):
                for k in ("url", "href", "src", "path"):
                    if isinstance(raw.get(k), str) and raw[k]:
                        raw = raw[k]
                        break
            if not isinstance(raw, str):
                return QtGui.QPixmap()
            v = raw.strip()
            if not v:
                return QtGui.QPixmap()
            if v.startswith("data:"):
                b64 = v.split(",", 1)[1]
                img = QtGui.QImage.fromData(base64.b64decode(b64))
                return QtGui.QPixmap.fromImage(img) if not img.isNull() else QtGui.QPixmap()
            # URL/chemin
            url = _abs_media_url(v, getattr(self._client, "api_base", "") or "")
            if not url:
                return QtGui.QPixmap()
            # requête HTTP via session du client (cookies conservés)
            sess = getattr(self._client, "sess", None)
            if not sess:
                return QtGui.QPixmap()
            r = sess.get(url, timeout=6)
            if not r.ok:
                return QtGui.QPixmap()
            img = QtGui.QImage.fromData(r.content)
            return QtGui.QPixmap.fromImage(img) if not img.isNull() else QtGui.QPixmap()
        except Exception:
            return QtGui.QPixmap()

    def _image_pixmap(self, path_or_url: Any) -> QtGui.QPixmap:
        # même logique que _avatar_pixmap, mais pour l'indice image
        try:
            if not path_or_url:
                return QtGui.QPixmap()
            if isinstance(path_or_url, dict):
                for k in ("url", "href", "src", "path"):
                    if isinstance(path_or_url.get(k), str) and path_or_url[k]:
                        path_or_url = path_or_url[k]
                        break
            if not isinstance(path_or_url, str):
                return QtGui.QPixmap()
            v = path_or_url.strip()
            if not v:
                return QtGui.QPixmap()
            if v.startswith("data:"):
                b64 = v.split(",", 1)[1]
                img = QtGui.QImage.fromData(base64.b64decode(b64))
                return QtGui.QPixmap.fromImage(img) if not img.isNull() else QtGui.QPixmap()
            url = _abs_media_url(v, getattr(self._client, "api_base", "") or "")
            if not url:
                return QtGui.QPixmap()
            sess = getattr(self._client, "sess", None)
            if not sess:
                return QtGui.QPixmap()
            r = sess.get(url, timeout=8)
            if not r.ok:
                return QtGui.QPixmap()
            img = QtGui.QImage.fromData(r.content)
            return QtGui.QPixmap.fromImage(img) if not img.isNull() else QtGui.QPixmap()
        except Exception:
            return QtGui.QPixmap()
