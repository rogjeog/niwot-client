# Niwot Desktop (PySide6) — UI neuve (sans web tech)

Client Windows **.exe** en **Python + PySide6** (Qt) qui se connecte à **ton Node.js existant** :
- HTTP: `requests.Session` (cookies de session gérés)
- Socket.IO: `python-socketio` (transports WebSocket)
- UI: PySide6 (Qt Widgets) — pas de React/JS/TS

## Configuration
Définis ces variables d’environnement (ou modifie dans `config.json`) :
- `NIWOT_API_BASE` (ex: `https://api-game.niwot.btsinfo.nc`)
- `NIWOT_WS_BASE` (ex: `wss://api-game.niwot.btsinfo.nc`)

Sous **CMD** :
```
setx NIWOT_API_BASE "https://api-game.niwot.btsinfo.nc"
setx NIWOT_WS_BASE  "wss://api-game.niwot.btsinfo.nc"
```

## Installation (dev)
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Build .exe (Windows)
```bat
.venv\Scripts\activate
pyinstaller --noconsole --onefile --name NiwotDesktop main.py
```
L’exécutable est dans `dist\NiwotDesktop.exe`.
> Si besoin d’un build plus robuste (icône, nom d’entreprise, ressources), on pourra ajouter un fichier `.spec` personnalisé.

## Adapter à ton API
- Les routes d’exemple: `/auth/login`, `/rooms`, `/rooms/join`, `/rooms/<id>/join` (à ajuster).
- Les événements Socket.IO d’exemple: `room:update`, `message`, `room:join`, `room:leave` (à aligner).

