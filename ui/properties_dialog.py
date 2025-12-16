from __future__ import annotations

from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QDialogButtonBox,
    QVBoxLayout,
)


def _fmt_dt(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "—"


def _fmt_size(num: int) -> str:
    # человекочитаемый размер
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num)
    for u in units:
        if size < 1024 or u == units[-1]:
            if u == "B":
                return f"{int(size)} {u}"
            return f"{size:.2f} {u}"
        size /= 1024
    return f"{num} B"


class PropertiesDialog(QDialog):
    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Свойства")
        self.setMinimumWidth(520)

        p = path
        exists = p.exists()

        layout = QVBoxLayout(self)
        form = QFormLayout()

        form.addRow("Имя:", QLabel(p.name))
        form.addRow("Путь:", QLabel(str(p)))
        form.addRow("Тип:", QLabel("Папка" if p.is_dir() else "Файл"))

        if exists:
            try:
                st = p.stat()
                form.addRow("Размер:", QLabel(_fmt_size(st.st_size) if p.is_file() else "—"))
                form.addRow("Создан:", QLabel(_fmt_dt(getattr(st, "st_ctime", 0))))
                form.addRow("Изменён:", QLabel(_fmt_dt(getattr(st, "st_mtime", 0))))
            except Exception:
                form.addRow("Размер:", QLabel("—"))
                form.addRow("Создан:", QLabel("—"))
                form.addRow("Изменён:", QLabel("—"))
        else:
            form.addRow("Статус:", QLabel("Не существует"))

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
