from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from core.search import search_paths


class SearchDialog(QDialog):
    def __init__(self, start_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Поиск")
        self.resize(760, 520)

        self.start_dir = start_dir
        self.selected_path: Optional[Path] = None

        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("Введите часть имени файла/папки…")

        self.recursive_cb = QCheckBox("Искать рекурсивно (в подпапках)")
        self.recursive_cb.setChecked(True)

        self.btn_search = QPushButton("Найти")
        self.btn_search.clicked.connect(self.do_search)

        top = QHBoxLayout()
        top.addWidget(QLabel("Поиск:"))
        top.addWidget(self.query_edit, 1)
        top.addWidget(self.btn_search)

        self.listw = QListWidget()
        self.listw.itemDoubleClicked.connect(self.open_item)

        self.info = QLabel("")
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)

        bottom = QHBoxLayout()
        self.btn_open = QPushButton("Открыть")
        self.btn_open.clicked.connect(self.open_selected)
        self.btn_open.setEnabled(False)

        self.btn_goto = QPushButton("Перейти в папку")
        self.btn_goto.clicked.connect(self.goto_selected_dir)
        self.btn_goto.setEnabled(False)

        self.btn_close = QPushButton("Закрыть")
        self.btn_close.clicked.connect(self.reject)

        bottom.addWidget(self.btn_open)
        bottom.addWidget(self.btn_goto)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_close)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.recursive_cb)
        layout.addWidget(self.listw, 1)
        layout.addWidget(self.info)
        layout.addLayout(bottom)

        self.listw.currentItemChanged.connect(self.on_select)

    def do_search(self):
        self.listw.clear()
        self.selected_path = None
        self.btn_open.setEnabled(False)
        self.btn_goto.setEnabled(False)

        q = self.query_edit.text().strip()
        rec = self.recursive_cb.isChecked()

        results = list(search_paths(self.start_dir, q, recursive=rec, limit=5000))
        self.info.setText(f"Найдено: {len(results)} (папка: {self.start_dir})")

        for p in results[:5000]:
            item = QListWidgetItem(str(p))
            item.setData(Qt.UserRole, p)
            self.listw.addItem(item)

    def on_select(self, item: Optional[QListWidgetItem], _prev):
        if not item:
            self.selected_path = None
            self.btn_open.setEnabled(False)
            self.btn_goto.setEnabled(False)
            return
        p = item.data(Qt.UserRole)
        self.selected_path = p
        self.btn_open.setEnabled(True)
        self.btn_goto.setEnabled(True)

    def open_item(self, item: QListWidgetItem):
        p: Path = item.data(Qt.UserRole)
        if p.is_dir():
            # открыть папку системно
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def open_selected(self):
        if self.selected_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.selected_path)))

    def goto_selected_dir(self):
        """
        Возвращаемся в главное окно: просто закрываем диалог,
        а путь можно забрать через get_selected().
        """
        if self.selected_path:
            self.accept()

    def get_selected(self) -> Optional[Path]:
        return self.selected_path
