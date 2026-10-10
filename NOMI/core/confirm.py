"""Real confirmation for actions that can't be taken back.

A tool marked ``"confirm": True`` (deleting a task or a note, erasing memory)
waits for a button the user presses. Claude can ask, but it can never answer for
the user: the dialog runs on the Qt main thread and only a click closes it.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.log import log

_parent: QWidget | None = None
_auto_answer: bool | None = None   # tests only


def set_parent(widget: QWidget) -> None:
    global _parent
    _parent = widget


def ask(title: str, detail: str = "") -> bool:
    """Show a Yes / No dialog. Must be called on the Qt main thread."""
    if _auto_answer is not None:
        return _auto_answer
    dlg = QDialog(_parent)
    dlg.setWindowTitle("Confirm — NOMI")
    dlg.setWindowModality(Qt.ApplicationModal)
    dlg.setStyleSheet("QDialog { background: #0a1626; border: 1px solid #2a6aa3; }")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(18, 16, 18, 16)
    t = QLabel(title)
    t.setWordWrap(True)
    t.setStyleSheet("font-weight: 600; font-size: 11pt;")
    d = QLabel(detail)
    d.setWordWrap(True)
    d.setStyleSheet("color: #6f8aa6;")
    row = QHBoxLayout()
    row.addStretch(1)
    no, yes = QPushButton("Cancel"), QPushButton("Yes, do it")
    yes.setObjectName("Danger")
    no.setDefault(True)  # Enter never confirms by accident
    no.clicked.connect(dlg.reject)
    yes.clicked.connect(dlg.accept)
    row.addWidget(no)
    row.addWidget(yes)
    lay.addWidget(t)
    lay.addWidget(d)
    lay.addLayout(row)
    ok = dlg.exec() == QDialog.Accepted
    log(f"{'✅ Confirmed' if ok else '✋ Declined'}: {title}")
    return ok
