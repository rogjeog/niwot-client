import os, sys, json
from PySide6 import QtWidgets, QtCore, QtGui

from ui_login import LoginWidget
from ui_lobby import LobbyWidget
from ui_room import RoomWidget
from ui_quiz import QuizWidget
from ui_header import HeaderWidget
from ui_profile import ProfileWidget
from ui_admin import AdminWidget
from ui_suggest import SuggestWidget
from niwot_client import NiwotClient
from ui_theme import apply_theme


def load_config():
    """Charge API_BASE et WS_BASE depuis config.json et/ou variables d'env."""
    cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    api = os.environ.get("NIWOT_API_BASE", cfg.get("API_BASE", ""))
    ws  = os.environ.get("NIWOT_WS_BASE",  cfg.get("WS_BASE",  ""))
    return api, ws


def resource_path(name: str) -> str:
    """Chemin d'une ressource packagée (PyInstaller) ou en dev."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, name)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, client: NiwotClient):
        super().__init__()
        self.setWindowTitle("Niwot Desktop")
        self.resize(1100, 720)
        self.client = client

        # ---------- Conteneur central (Header + contenu centré) ----------
        central = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Header (visible partout sauf écran de connexion)
        self.header = HeaderWidget()
        self.header.set_client(self.client)  # pour charger l’avatar via session HTTP
        v.addWidget(self.header)

        # Couloir horizontal -> contenu centré et largeur limitée
        center_row = QtWidgets.QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.setSpacing(0)
        v.addLayout(center_row, 1)

        center_row.addStretch(1)

        self.content_frame = QtWidgets.QFrame()
        self.content_frame.setObjectName("ContentFrame")
        self.content_frame.setMaximumWidth(1100)  # limite pour éviter le plein écran sur les formulaires
        self.content_frame.setMinimumWidth(820)
        self.content_frame.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                                         QtWidgets.QSizePolicy.Policy.Expanding)

        cf_layout = QtWidgets.QVBoxLayout(self.content_frame)
        cf_layout.setContentsMargins(16, 16, 16, 16)
        cf_layout.setSpacing(12)

        # Pile de pages dans le cadre centré
        self.stack = QtWidgets.QStackedWidget()
        cf_layout.addWidget(self.stack, 1)

        center_row.addWidget(self.content_frame, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        center_row.addStretch(1)

        self.setCentralWidget(central)

        # ---------- Pages ----------
        self.login   = LoginWidget()
        self.lobby   = LobbyWidget()
        self.room    = RoomWidget()
        self.quiz    = QuizWidget()
        self.profile = ProfileWidget()
        self.admin   = AdminWidget()
        self.suggest = SuggestWidget()

        self.stack.addWidget(self.login)    # index 0
        self.stack.addWidget(self.lobby)    # index 1
        self.stack.addWidget(self.room)     # index 2
        self.stack.addWidget(self.quiz)     # index 3
        self.stack.addWidget(self.profile)  # index 4
        self.stack.addWidget(self.admin)    # index 5
        self.stack.addWidget(self.suggest)  # index 6

        # ---------- Injection du client ----------
        self.login.set_client(self.client)
        self.room.set_client(self.client)
        self.quiz.set_client(self.client)
        self.profile.set_client(self.client)
        self.admin.set_client(self.client)
        self.suggest.set_client(self.client)

        # ---------- Signals ----------
        # Login
        self.login.sig_logged_in.connect(self.on_logged_in)
        self.login.sig_error.connect(self.on_error)

        # Lobby
        self.lobby.sig_enter_room.connect(self.on_enter_room)   # string: room_code
        self.lobby.sig_error.connect(self.on_error)
        self.lobby.sig_goto_suggest.connect(self.on_goto_suggest)

        # Room
        self.room.sig_leave.connect(self.on_leave_room)
        self.room.sig_goto_quiz.connect(self.on_goto_quiz)

        # Quiz
        self.quiz.sig_goto_room.connect(self.on_back_to_room)  # retour à la salle
        self.quiz.sig_quit.connect(self.on_back_to_room)       # "Quitter le quiz" -> revenir à la salle

        # Sockets -> pages
        self.client.sig_socket_message.connect(self.room.on_message)
        self.client.sig_socket_message.connect(self.quiz.on_message)

        # 🔸 Hook global : si un évènement de démarrage passe "à côté", on force la redirection
        self.client.sig_socket_message.connect(self._maybe_goto_quiz)

        # Header nav
        self.header.sig_go_lobby.connect(self.on_goto_lobby)
        self.header.sig_go_admin.connect(self.on_goto_admin)
        self.header.sig_go_profile.connect(self.on_goto_profile)

        # Profil -> déconnexion
        self.profile.sig_logged_out.connect(self.on_logged_out)

        # Démarre sur l'écran de connexion
        self._show_header(False)
        self.stack.setCurrentIndex(0)

        # Raccourcis plein écran (F11/Esc)
        QtGui.QShortcut(QtGui.QKeySequence("F11"), self, self.toggle_fullscreen)
        QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, self.exit_fullscreen)

    # ---------- Plein écran ----------
    @QtCore.Slot()
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    @QtCore.Slot()
    def exit_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()

    # ---------- Helpers ----------
    def _show_header(self, show: bool):
        self.header.setVisible(show)

    def _set_user_everywhere(self, user: dict):
        """
        Assure l'ordre : d'abord les clients/pages, ensuite l'utilisateur.
        Garantit l'affichage immédiat des avatars (profil/header).
        """
        # rafraîchir données lobby qui dépendent du client (ex: liste de salles)
        try:
            self.lobby.refresh_rooms(self.client)
        except Exception:
            pass

        # pousser l'utilisateur dans les vues
        self.header.set_user(user)
        self.lobby.set_user(user)
        self.profile.set_user(user)
        self.admin.set_user(user)
        # room/quiz n'ont pas besoin du user directement ici

    # ---------- Hook global socket ----------
    @QtCore.Slot(object, object)
    def _maybe_goto_quiz(self, event, payload):
        """
        Forçage de redirection vers le quiz si un event de démarrage est reçu
        (peu importe la page courante).
        """
        try:
            ev = str(event)
        except Exception:
            return
        if ev in {"quiz:question", "quiz:started", "room:started", "room:running", "game:started"}:
            self.on_goto_quiz()

    # ---------- Slots (navigation / actions) ----------
    @QtCore.Slot(dict)
    def on_logged_in(self, user):
        self.statusBar().showMessage(f"Connecté: {user.get('username') or user.get('email','')}")
        # Connexion socket après login
        try:
            self.client.connect_socket()
        except Exception:
            pass
        self._set_user_everywhere(user)
        self._show_header(True)
        self.stack.setCurrentIndex(1)  # Lobby

    @QtCore.Slot(str)
    def on_error(self, message):
        QtWidgets.QMessageBox.critical(self, "Erreur", message)

    @QtCore.Slot(str)
    def on_enter_room(self, room_code: str):
        """
        Appelé depuis le lobby :
          - Rejoint (ou crée) la salle côté backend selon ton implémentation.
          - Affiche la page 'Room'.
        """
        try:
            self.room.set_room(room_code)
            self._show_header(True)
            self.stack.setCurrentIndex(2)  # Room
        except Exception as e:
            self.on_error(f"Impossible d'entrer dans la salle : {e}")

    @QtCore.Slot()
    def on_leave_room(self):
        """Retour lobby depuis la page Room (bouton Quitter)."""
        self._show_header(True)
        self.stack.setCurrentIndex(1)  # Lobby
        try:
            self.lobby.refresh_rooms(self.client)
        except Exception:
            pass

    @QtCore.Slot()
    def on_goto_quiz(self):
        """Basculer vers l'écran de quiz lorsque la partie démarre."""
        code = getattr(self.room, "room_code", None)
        if code:
            self.quiz.set_room(code)
        self._show_header(True)
        self.stack.setCurrentIndex(3)  # Quiz

    @QtCore.Slot()
    def on_back_to_room(self):
        """Retour à la salle depuis l'écran de quiz."""
        self._show_header(True)
        self.stack.setCurrentIndex(2)  # Room

    # --- Header actions ---
    @QtCore.Slot()
    def on_goto_lobby(self):
        self._show_header(True)
        self.stack.setCurrentIndex(1)
        try:
            self.lobby.refresh_rooms(self.client)
        except Exception:
            pass

    @QtCore.Slot()
    def on_goto_profile(self):
        self._show_header(True)
        self.stack.setCurrentIndex(4)

    @QtCore.Slot()
    def on_goto_admin(self):
        self._show_header(True)
        self.stack.setCurrentIndex(5)

    @QtCore.Slot()
    def on_goto_suggest(self):
        self._show_header(True)
        self.stack.setCurrentIndex(6)

    @QtCore.Slot()
    def on_logged_out(self):
        """
        Déconnexion depuis la page Profil.
        Ferme le socket, masque le header et renvoie à l'écran de connexion.
        """
        try:
            if self.client.sio and self.client.sio.connected:
                self.client.sio.disconnect()
        except Exception:
            pass
        self._show_header(False)
        self.stack.setCurrentIndex(0)  # Login
        self.statusBar().clearMessage()


def main():
    api, ws = load_config()
    app = QtWidgets.QApplication(sys.argv)

    # Thème global
    apply_theme(app)

    # Icône fenêtre
    app.setWindowIcon(QtGui.QIcon(resource_path("niwot-favicon.png")))

    # Client API/WS
    client = NiwotClient(api_base=api, ws_base=ws)

    mw = MainWindow(client)

    # Démarrage en plein écran
    mw.showFullScreen()

    sys.exit(app.exec())


if __name__ == "__main__":

    main()
