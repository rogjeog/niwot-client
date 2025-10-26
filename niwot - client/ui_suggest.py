# ui_suggest.py
from __future__ import annotations
from PySide6 import QtWidgets, QtCore
from typing import Optional, Dict, Any, List
from niwot_client import NiwotClient
from requests_toolbelt import MultipartEncoder

class SuggestWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._client: Optional[NiwotClient] = None
        self._categories: List[Dict[str,Any]] = []
        self._selected: set[int] = set()
        self._image_path: Optional[str] = None

        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(12)

        self.title = QtWidgets.QLabel("<h2>Proposer une question</h2>")
        root.addWidget(self.title)

        form = QtWidgets.QFormLayout()
        root.addLayout(form)

        self.inp_text = QtWidgets.QLineEdit()
        form.addRow("Question *", self.inp_text)

        type_row = QtWidgets.QWidget(); thr = QtWidgets.QHBoxLayout(type_row); thr.setContentsMargins(0,0,0,0)
        self.rb_citation = QtWidgets.QRadioButton("Citation"); self.rb_image = QtWidgets.QRadioButton("Image")
        self.rb_citation.setChecked(True)
        thr.addWidget(self.rb_citation); thr.addWidget(self.rb_image)
        form.addRow("Type *", type_row)

        self.txt_quote = QtWidgets.QTextEdit()
        form.addRow("Texte de la citation *", self.txt_quote)

        img_row = QtWidgets.QWidget(); ihr = QtWidgets.QHBoxLayout(img_row); ihr.setContentsMargins(0,0,0,0)
        self.inp_img = QtWidgets.QLineEdit(); self.inp_img.setReadOnly(True)
        btn_pick = QtWidgets.QPushButton("Choisir…"); btn_pick.clicked.connect(self._pick_image)
        ihr.addWidget(self.inp_img); ihr.addWidget(btn_pick)
        form.addRow("Image *", img_row)

        self.inp_answer = QtWidgets.QLineEdit()
        form.addRow("Réponse *", self.inp_answer)

        self.txt_alts = QtWidgets.QTextEdit()
        self.txt_alts.setPlaceholderText("Alternatives (une par ligne ou séparées par des virgules)")
        form.addRow("Alternatives", self.txt_alts)

        self.txt_expl = QtWidgets.QTextEdit()
        form.addRow("Explication *", self.txt_expl)

        # Catégories
        self.grp_cat = QtWidgets.QGroupBox("Catégories * (au moins une)")
        root.addWidget(self.grp_cat)
        self.cat_layout = QtWidgets.QGridLayout(self.grp_cat)

        # Messages + actions
        self.lbl_msg = QtWidgets.QLabel("")
        root.addWidget(self.lbl_msg)
        btns = QtWidgets.QHBoxLayout()
        btns.addStretch()
        self.btn_send = QtWidgets.QPushButton("Envoyer")
        self.btn_send.clicked.connect(self._submit)
        btns.addWidget(self.btn_send)
        root.addLayout(btns)
        root.addStretch()

        # toggle champs selon type
        self.rb_citation.toggled.connect(self._toggle_type)
        self._toggle_type()

    def set_client(self, client: NiwotClient):
        self._client = client
        self._load_categories()

    def _toggle_type(self):
        is_cit = self.rb_citation.isChecked()
        self.txt_quote.setEnabled(is_cit)
        self.inp_img.setEnabled(not is_cit)

    def _pick_image(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Choisir une image", "", "Images (*.png *.jpg *.jpeg *.webp *.gif);;Tous les fichiers (*.*)")
        if path:
            self._image_path = path
            self.inp_img.setText(path)

    def _load_categories(self):
        self._categories.clear()
        self._selected.clear()
        for i in reversed(range(self.cat_layout.count())):
            item = self.cat_layout.itemAt(i); w = item.widget()
            if w: w.setParent(None)

        if not self._client: return
        try:
            r = self._client.sess.get(f"{self._client.api_base}/categories")
            data = r.json() if "application/json" in (r.headers.get("content-type") or "") else {}
            cats = data.get("categories") or data or []
            # Affiche en 3 colonnes
            row = col = 0
            for c in cats:
                cb = QtWidgets.QCheckBox(c.get("name",""))
                cid = int(c.get("id"))
                cb.stateChanged.connect(lambda st, i=cid: self._toggle_cat(i, st))
                self.cat_layout.addWidget(cb, row, col)
                col += 1
                if col >= 3:
                    col = 0; row += 1
                self._categories.append(c)
        except Exception:
            pass

    def _toggle_cat(self, cid: int, state: int):
        if state:
            self._selected.add(cid)
        else:
            self._selected.discard(cid)

    @QtCore.Slot()
    def _submit(self):
        self.lbl_msg.setStyleSheet("color:#ff8b8b;")
        self.lbl_msg.setText("")
        if not self._client: 
            self.lbl_msg.setText("Client non disponible.")
            return

        text = self.inp_text.text().strip()
        qtype = "CITATION" if self.rb_citation.isChecked() else "IMAGE"
        quote = self.txt_quote.toPlainText().strip()
        answer = self.inp_answer.text().strip()
        alts = [x.strip() for x in (self.txt_alts.toPlainText().replace(",", "\n")).split("\n") if x.strip()]
        expl = self.txt_expl.toPlainText().strip()
        cats = list(self._selected)

        # Vérifs
        if not text:
            self.lbl_msg.setText("La question est obligatoire."); return
        if qtype == "CITATION" and not quote:
            self.lbl_msg.setText("La citation est obligatoire."); return
        if qtype == "IMAGE" and not self._image_path:
            self.lbl_msg.setText("L'image est obligatoire."); return
        if not answer:
            self.lbl_msg.setText("La réponse est obligatoire."); return
        if not cats:
            self.lbl_msg.setText("Choisissez au moins une catégorie."); return

        try:
            fields = {
                "text": text,
                "type": qtype,
                "answer": answer,
                "alternatives": QtCore.QByteArray(json.dumps(alts).encode("utf-8")) if alts else "",
                "explanation": expl,
                "categoryIds": QtCore.QByteArray(json.dumps(cats).encode("utf-8")),
            }
        except NameError:
            import json
            fields = {
                "text": text, "type": qtype, "answer": answer,
                "alternatives": json.dumps(alts) if alts else "",
                "explanation": expl,
                "categoryIds": json.dumps(cats),
            }

        if qtype == "CITATION":
            fields["citationText"] = quote
        else:
            # image binaire
            try:
                with open(self._image_path, "rb") as f:
                    img_bytes = f.read()
                fields["image"] = ("image", img_bytes, "application/octet-stream")
            except Exception:
                self.lbl_msg.setText("Impossible de lire le fichier image.")
                return

        # Envoie multipart
        try:
            m = MultipartEncoder(fields=fields)
            r = self._client.sess.post(f"{self._client.api_base}/suggest", data=m, headers={"Content-Type": m.content_type})
            if not r.ok:
                try:
                    err = r.json().get("error")
                except Exception:
                    err = r.text
                raise RuntimeError(err or "Erreur lors de l'envoi.")
            self.lbl_msg.setStyleSheet("color:#69f0ae;")
            self.lbl_msg.setText("Proposition envoyée ! Elle sera visible après validation.")
            # reset
            self.inp_text.clear(); self.txt_quote.clear(); self.inp_img.clear()
            self._image_path = None; self.inp_answer.clear(); self.txt_alts.clear(); self.txt_expl.clear()
        except Exception as e:
            self.lbl_msg.setText(str(e))
