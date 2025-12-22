from __future__ import annotations

from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.batch_rename import build_plan, RenamePlanItem


class BatchRenameDialog(QDialog):
    def __init__(self, selected: List[Path], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Пакетное переименование")
        self.resize(900, 600)
        self.selected = [p for p in selected if p.exists()]

        self.mode = QComboBox()
        self.mode.addItem("Префикс", "prefix")
        self.mode.addItem("Суффикс", "suffix")
        self.mode.addItem("Замена текста", "replace")
        self.mode.addItem("Regex замена", "regex")
        self.mode.addItem("Шаблон + нумерация ({n})", "template")

        self.a_edit = QLineEdit()
        self.b_edit = QLineEdit()
        self.tpl_edit = QLineEdit("file_{n:03}")

        self.start_spin = QSpinBox()
        self.start_spin.setRange(1, 1_000_000)
        self.start_spin.setValue(1)

        self.step_spin = QSpinBox()
        self.step_spin.setRange(1, 1_000_000)
        self.step_spin.setValue(1)

        form = QFormLayout()
        form.addRow("Режим:", self.mode)
        form.addRow("A (префикс/суффикс/что искать/regex):", self.a_edit)
        form.addRow("B (на что заменить):", self.b_edit)
        form.addRow("Шаблон (для template):", self.tpl_edit)
        form.addRow("Старт номера:", self.start_spin)
        form.addRow("Шаг:", self.step_spin)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Было", "Станет"])
        self.table.horizontalHeader().setStretchLastSection(True)

        preview_btn = QPushButton("Предпросмотр")
        preview_btn.clicked.connect(self.preview)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(preview_btn)
        layout.addWidget(self.table, 1)
        layout.addWidget(btns)

        self.plan: List[RenamePlanItem] = []

    def preview(self):
        try:
            mode = self.mode.currentData()
            self.plan = build_plan(
                self.selected,
                mode=mode,
                a=self.a_edit.text(),
                b=self.b_edit.text(),
                template=self.tpl_edit.text(),
                start=int(self.start_spin.value()),
                step=int(self.step_spin.value()),
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
            self.plan = []
            self.table.setRowCount(0)
            return

        self.table.setRowCount(0)
        for it in self.plan:
            r = self.table.rowCount()
            self.table.insertRow(r)
            a = QTableWidgetItem(it.src.name)
            b = QTableWidgetItem(it.dst.name)
            a.setFlags(a.flags() ^ Qt.ItemIsEditable)
            b.setFlags(b.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(r, 0, a)
            self.table.setItem(r, 1, b)

    def get_plan(self) -> List[RenamePlanItem]:
        return self.plan
