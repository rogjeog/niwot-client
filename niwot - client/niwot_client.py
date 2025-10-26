# niwot_client.py
from __future__ import annotations
import requests
import socketio
from typing import Any, Dict, Optional, List, Tuple
from PySide6 import QtCore
import queue


class NiwotClient(QtCore.QObject):
    """
    Client HTTP + Socket.IO pour l'app Niwot Desktop.

    Signals:
      - sig_socket_message(event: str, payload: object)
    """
    sig_socket_message = QtCore.Signal(str, object)

    def __init__(self, api_base: str, ws_base: str):
        super().__init__()
        self.api_base = (api_base or "").rstrip("/")
        self.ws_base = (ws_base or "").rstrip("/")
        self.sess = requests.Session()
        self.bearer_token: Optional[str] = None

        # --- Queue thread-safe pour transférer les events socket -> UI ---
        self._evt_queue: "queue.SimpleQueue[Tuple[str, object]]" = queue.SimpleQueue()
        self._pump = QtCore.QTimer(self)
        self._pump.setInterval(10)  # 100 Hz
        self._pump.timeout.connect(self._drain_queue)
        self._pump.start()

        # --- Socket.IO ---
        self.sio = socketio.Client(
            logger=False,
            engineio_logger=False,
            reconnection=True,
        )

        # handlers SIO (ATTENTION: thread réseau)
        self.sio.on("connect", lambda: self._queue("connect", {"id": getattr(self.sio, "sid", None)}))
        self.sio.on("disconnect", lambda: self._queue("disconnect", {}))

        for ev in [
            "room:update", "room:started", "room:running",
            "room:join", "room:joined", "room:left", "room:leave",
            "room:memberJoined", "room:memberLeft", "room:members",
            "room:players", "room:sync", "room:kicked", "room:banned",
            "quiz:question", "quiz:proposals", "quiz:result",
            "quiz:ended", "quiz:gotoRoom", "quiz:started",
            "game:started"
        ]:
            self.sio.on(ev, self._mk(ev))

    # ---------------- HTTP helpers ----------------
    def _set_auth_header_if_needed(self):
        if self.bearer_token:
            self.sess.headers["Authorization"] = f"Bearer {self.bearer_token}"

    def me(self) -> Dict[str, Any]:
        endpoints = ["/auth/me", "/me", "/users/me"]
        self._set_auth_header_if_needed()
        last_err = ""
        for path in endpoints:
            url = f"{self.api_base}{path}"
            try:
                r = self.sess.get(url, timeout=10)
                if r.ok:
                    data = r.json()
                    user = (data.get("user") if isinstance(data, dict) and "user" in data else data)
                    return {"ok": True, "user": user}
                last_err = f"{r.status_code} {r.text[:200]}"
            except Exception as e:
                last_err = str(e)
        return {"ok": False, "error": f"Impossible de récupérer /me: {last_err}"}

    def login(self, email: str, password: str) -> Dict[str, Any]:
        login_paths = ["/auth/login", "/login"]
        last_err = ""
        for path in login_paths:
            url = f"{self.api_base}{path}"
            try:
                r = self.sess.post(url, json={"email": email, "password": password}, timeout=15)
                if not r.ok:
                    last_err = f"{r.status_code} {r.text[:200]}"; continue
                data = {}
                try: data = r.json()
                except Exception: pass
                token = (
                    (data.get("token") if isinstance(data, dict) else None) or
                    (data.get("accessToken") if isinstance(data, dict) else None) or
                    (data.get("jwt") if isinstance(data, dict) else None) or
                    (isinstance(data, dict) and isinstance(data.get("data"), dict) and data["data"].get("token"))
                )
                if token:
                    self.bearer_token = str(token)
                    self._set_auth_header_if_needed()
                user = (data.get("user") if isinstance(data, dict) else None)
                return {"ok": True, "user": user} if user else self.me()
            except Exception as e:
                last_err = str(e)
        return {"ok": False, "error": f"Impossible de se connecter: {last_err}"}

    def register(self, username: str, email: str, password: str) -> Dict[str, Any]:
        reg_paths = ["/auth/register", "/register"]
        last_err = ""
        for path in reg_paths:
            url = f"{self.api_base}{path}"
            try:
                r = self.sess.post(url, json={"username": username, "email": email, "password": password}, timeout=20)
                if not r.ok:
                    last_err = f"{r.status_code} {r.text[:200]}"; continue
                data = r.json()
                token = (
                    (data.get("token") if isinstance(data, dict) else None) or
                    (data.get("accessToken") if isinstance(data, dict) else None) or
                    (data.get("jwt") if isinstance(data, dict) else None) or
                    (isinstance(data, dict) and isinstance(data.get("data"), dict) and data["data"].get("token"))
                )
                if token:
                    self.bearer_token = str(token)
                    self._set_auth_header_if_needed()
                user = (data.get("user") if isinstance(data, dict) else None)
                return {"ok": True, "user": user} if user else self.me()
            except Exception as e:
                last_err = str(e)
        return {"ok": False, "error": f"Impossible de créer le compte: {last_err}"}

    def logout(self) -> Dict[str, Any]:
        try:
            r = self.sess.post(f"{self.api_base}/auth/logout", timeout=10)
            self.bearer_token = None
            self.sess.headers.pop("Authorization", None)
            return {"ok": r.ok}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_categories(self) -> Dict[str, Any]:
        self._set_auth_header_if_needed()
        candidates = [
            ("/categories/stats", None),
            ("/categories", {"approvedOnly": "true", "includeCounts": "true"}),
            ("/categories", None),
            ("/quiz/categories", None),
            ("/category/list", None),
            ("/categories/list", None),
            ("/api/categories", None),
            ("/api/v1/categories", None),
        ]
        last_err = ""
        for path, params in candidates:
            url = f"{self.api_base}{path}"
            try:
                r = self.sess.get(url, params=params, timeout=10)
                if not r.ok:
                    last_err = f"{r.status_code} {r.text[:160]}"; continue
                data = r.json()
                arr = None
                if isinstance(data, list): arr = data
                elif isinstance(data, dict):
                    for k in ("categories","data","items","result","rows","records"):
                        if isinstance(data.get(k), list): arr = data[k]; break
                if not isinstance(arr, list) or not arr: continue
                norm: List[Dict[str, Any]] = []
                for c in arr:
                    if not isinstance(c, dict): continue
                    cid = c.get("id") or c.get("_id") or c.get("ID") or c.get("uuid")
                    name = c.get("name") or c.get("label") or c.get("title")
                    approved = c.get("questionCount") or c.get("approvedCount") or c.get("count") or c.get("questionsApproved")
                    if cid is None or name is None: continue
                    try: cid = int(cid)
                    except Exception: cid = str(cid)
                    norm.append({"id": cid, "name": str(name), "approvedCount": approved if isinstance(approved,(int,float)) else None})
                if norm: return {"ok": True, "categories": norm}
            except Exception as e:
                last_err = str(e)
        return {"ok": False, "error": f"Échec de chargement des catégories: {last_err or 'aucune source valide'}"}

    # ---------------- Socket.IO ----------------
    def connect_socket(self):
        if not self.ws_base or self.sio.connected:
            return
        cookie = "; ".join([f"{k}={v}" for k, v in self.sess.cookies.get_dict().items()])
        headers = {}
        if cookie: headers["Cookie"] = cookie
        self._set_auth_header_if_needed()
        if "Authorization" in self.sess.headers:
            headers["Authorization"] = self.sess.headers["Authorization"]
        self.sio.connect(self.ws_base, transports=["websocket", "polling"], headers=headers)

    def disconnect_socket(self):
        try:
            if self.sio and self.sio.connected:
                self.sio.disconnect()
        except Exception:
            pass

    def socket_emit(self, event: str, data: Optional[dict] = None, ack=None):
        if not self.sio or not self.sio.connected:
            return
        if ack: self.sio.emit(event, data or {}, callback=ack)
        else:   self.sio.emit(event, data or {})

    # ---------------- Internes ----------------
    def _queue(self, ev: str, payload: object):
        # appelé depuis le thread socket
        try:
            self._evt_queue.put((ev, payload))
        except Exception:
            pass

    def _mk(self, ev: str):
        def _fwd(data=None):
            self._queue(ev, data if data is not None else {})
        return _fwd

    @QtCore.Slot()
    def _drain_queue(self):
        # appelé dans le thread UI (par QTimer self._pump)
        try:
            while True:
                ev, payload = self._evt_queue.get_nowait()
                try:
                    self.sig_socket_message.emit(ev, payload)
                except Exception:
                    pass
        except queue.Empty:
            return
