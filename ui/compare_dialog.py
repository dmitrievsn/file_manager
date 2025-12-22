from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
)

from core.compare import compare_dirs, CompareResult


class CompareDialog(QDialog):
    def __init__(self, left_root: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Сравнение каталогов")
        self.resize(900, 600)

        self.left_root = left_root
        self.right_root: Optional[Path] = None
        self.result: Optional[CompareResult] = None

        top = QHBoxLayout()
        self.left_edit = QLineEdit(str(left_root))
        self.left_edit.setReadOnly(True)

        self.right_edit = QLineEdit("")
        self.right_btn = QPushButton("Выбрать правую папку…")
        self.right_btn.clicked.connect(self.pick_right)

        self.hash_cb = QCheckBox("Сравнивать по SHA-256 (медленно)")
        top.addWidget(QLabel("Левая:"))
        top.addWidget(self.left_edit, 2)
        top.addWidget(QLabel("Правая:"))
        top.addWidget(self.right_edit, 2)
        top.addWidget(self.right_btn)
        top.addWidget(self.hash_cb)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Статус", "Относительный путь", "Левая", "Правая"])
        self.table.horizontalHeader().setStretchLastSection(True)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)

        run_btn = QPushButton("Сравнить")
        run_btn.clicked.connect(self.run_compare)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(run_btn)
        layout.addWidget(self.table, 1)
        layout.addWidget(btns)

    def pick_right(self):
        d = QFileDialog.getExistingDirectory(self, "Выберите правую папку", str(self.left_root))
        if d:
            self.right_root = Path(d)
            self.right_edit.setText(d)

    def run_compare(self):
        if not self.right_root:
            QMessageBox.warning(self, "Нет правой папки", "Сначала выберите правую папку.")
            return

        use_hash = self.hash_cb.isChecked()
        self.result = compare_dirs(self.left_root, self.right_root, use_hash=use_hash)
        self.fill_table(self.result)

    def fill_table(self, r: CompareResult):
        self.table.setRowCount(0)

        def add_row(status: str, rel: str, l: str, rr: str):
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, val in enumerate([status, rel, l, rr]):
                it = QTableWidgetItem(val)
                it.setFlags(it.flags() ^ Qt.ItemIsEditable)
                self.table.setItem(row, col, it)

        for x in r.only_left:
            add_row("Только слева", x.rel, "есть", "нет")
        for x in r.only_right:
            add_row("Только справа", x.rel, "нет", "есть")
        for a, b in r.different:
            add_row("Разные", a.rel, f"{a.size}B", f"{b.size}B")
        for a, b in r.same:
            add_row("Одинаковые", a.rel, "=", "=")
