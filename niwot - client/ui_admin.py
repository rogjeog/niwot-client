# ui_admin.py
from __future__ import annotations
from PySide6 import QtWidgets
from typing import Optional, Dict, Any
from niwot_client import NiwotClient

class AdminWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._client: Optional[NiwotClient] = None
        self._user: Optional[Dict[str, Any]] = None

        root = QtWidgets.QVBoxLayout(self)
        self.title = QtWidgets.QLabel("<h2>Administration</h2>")
        root.addWidget(self.title)
        self.lbl = QtWidgets.QLabel("Droite admin à implémenter ici…")
        root.addWidget(self.lbl)
        root.addStretch()

    def set_client(self, client: NiwotClient):
        self._client = client

    def set_user(self, user: Dict[str, Any]):
        self._user = user
        if user.get("role") != "admin":
            self.lbl.setText("Accès refusé — vous n'êtes pas administrateur.")
        else:
            self.lbl.setText("Bienvenue, administrateur.")
