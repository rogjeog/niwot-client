# ui_theme.py
from __future__ import annotations
from PySide6 import QtWidgets

def qss() -> str:
    return """
/* ===== Base ===== */
QWidget { color: #e8ebff; background-color: #0b0b12; }
QMainWindow, QDialog { background-color: #0b0b12; }
QStatusBar { color: #aab2e6; background: transparent; border: none; }

/* ===== Header (par objectName) ===== */
#HeaderWidget {
    background-color: #141a33;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
#HeaderWidget QLabel { color: #e8ebff; }

/* ===== Cartes ===== */
QGroupBox {
    background-color: rgba(17,17,26,0.80);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 16px;
    margin-top: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: #aab2e6;
}

/* ===== Boutons ===== */
QPushButton {
    color: #ffffff;
    border: 1px solid #6b4fd6;
    border-radius: 10px;
    padding: 7px 12px;
    background-color: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                                      stop:0 #7a3cff, stop:1 #5b2fd6);
}
QPushButton:hover {
    border-color: #7a3cff;
}
QPushButton:disabled {
    background-color: #2a2f4a;
    color: #a0a6ce;
    border-color: #2a2f4a;
}

/* ===== Champs de saisie ===== */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: rgba(0,0,0,0.30);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 10px;
    padding: 6px 10px;
    selection-background-color: rgba(122,60,255,0.45);
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #7a3cff;
}

/* ===== Listes / tableaux ===== */
QListWidget, QTreeWidget, QTableWidget, QTableView {
    background-color: rgba(0,0,0,0.20);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
}
QListWidget::item { padding: 6px; }
QListWidget::item:selected {
    background: rgba(122,60,255,0.30);
}

/* ===== Scrollbars (discret) ===== */
QScrollBar:vertical {
    background: transparent; width: 10px; margin: 2px;
}
QScrollBar::handle:vertical {
    background: rgba(255,255,255,0.12); min-height: 24px; border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background: transparent; height: 10px; margin: 2px;
}
QScrollBar::handle:horizontal {
    background: rgba(255,255,255,0.12); min-width: 24px; border-radius: 5px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
"""

def apply_theme(app: QtWidgets.QApplication) -> None:
    app.setStyleSheet(qss())
