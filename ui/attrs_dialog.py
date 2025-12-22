from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QVBoxLayout,
)

from core.attrs import AttrsRequest
from core.locks import is_locked  # важно


def _tri_state_value(cb: QCheckBox) -> Optional[bool]:
    """
    Возвращает:
      True  - поставить атрибут
      False - снять атрибут
      None  - не менять (mixed/partially)
    """
    st = cb.checkState()
    if st == Qt.PartiallyChecked:
        return None
    return st == Qt.Checked


def _set_tristate_from_items(cb: QCheckBox, values: List[bool]) -> None:
    cb.setTristate(True)
    if all(values):
        cb.setCheckState(Qt.Checked)
    elif not any(values):
        cb.setCheckState(Qt.Unchecked)
    else:
        cb.setCheckState(Qt.PartiallyChecked)


class AttrsDialog(QDialog):
    def __init__(self, selected: List[Path], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Массовые атрибуты")
        self.resize(450, 240)
        self.selected = [p for p in selected if p.exists()]

        self.cb_ro = QCheckBox("Только чтение (Read-only)")
        self.cb_lock = QCheckBox("Заблокировать (внутри менеджера)")

        # времена — оставляем как “по галке применить”
        self.cb_mtime = QCheckBox("Изменить время модификации (mtime)")
        self.dt_mtime = QDateTimeEdit()
        self.dt_mtime.setCalendarPopup(True)
        self.dt_mtime.setDateTime(datetime.now())

        self.cb_atime = QCheckBox("Изменить время доступа (atime)")
        self.dt_atime = QDateTimeEdit()
        self.dt_atime.setCalendarPopup(True)
        self.dt_atime.setDateTime(datetime.now())

        # === ИНИЦИАЛИЗАЦИЯ текущих атрибутов по выделению ===
        ro_vals: List[bool] = []
        lock_vals: List[bool] = []

        for p in self.selected:
            try:
                # readonly: если нет прав на запись
                ro_vals.append(not p.stat().st_mode & 0o200)
            except Exception:
                ro_vals.append(False)

            try:
                lock_vals.append(is_locked(p))
            except Exception:
                lock_vals.append(False)

        _set_tristate_from_items(self.cb_ro, ro_vals)
        _set_tristate_from_items(self.cb_lock, lock_vals)

        form = QFormLayout()
        form.addRow(self.cb_ro)
        form.addRow(self.cb_lock)
        form.addRow(self.cb_mtime, self.dt_mtime)
        form.addRow(self.cb_atime, self.dt_atime)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(btns)

    def get_request(self) -> AttrsRequest:
        # ✅ теперь Unchecked = False (снять), Checked = True (поставить), Partially = None (не менять)
        ro: Optional[bool] = _tri_state_value(self.cb_ro)
        lock: Optional[bool] = _tri_state_value(self.cb_lock)

        mtime = self.dt_mtime.dateTime().toPython() if self.cb_mtime.isChecked() else None
        atime = self.dt_atime.dateTime().toPython() if self.cb_atime.isChecked() else None

        return AttrsRequest(set_readonly=ro, set_locked=lock, mtime=mtime, atime=atime)
