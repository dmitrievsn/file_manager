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
    QMessageBox,
)

from core.search import search_paths


class SearchDialog(QDialog):
    """
    Диалог поиска файлов и папок.
    Использует самописный алгоритм поиска (core.search.search_paths).
    """

    def __init__(self, start_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Поиск")
        self.resize(750, 520)

        self.start_dir = start_dir
        self.selected_path: Optional[Path] = None

        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("Введите часть имени файла или папки")

        self.recursive_cb = QCheckBox("Искать в подпапках")
        self.recursive_cb.setChecked(True)

        self.btn_search = QPushButton("Найти")
        self.btn_search.clicked.connect(self.do_search)

        top = QHBoxLayout()
        top.addWidget(QLabel("Поиск:"))
        top.addWidget(self.query_edit, 1)
        top.addWidget(self.btn_search)

        self.listw = QListWidget()
        self.listw.itemDoubleClicked.connect(self.open_item)
        self.listw.currentItemChanged.connect(self.on_select)

        self.info = QLabel("")

        self.btn_open = QPushButton("Открыть")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self.open_selected)

        self.btn_goto = QPushButton("Перейти в папку")
        self.btn_goto.setEnabled(False)
        self.btn_goto.clicked.connect(self.goto_selected_dir)

        self.btn_close = QPushButton("Закрыть")
        self.btn_close.clicked.connect(self.reject)

        bottom = QHBoxLayout()
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

    def do_search(self):
        """Запуск поиска."""
        self.listw.clear()
        self.selected_path = None
        self.btn_open.setEnabled(False)
        self.btn_goto.setEnabled(False)

        query = self.query_edit.text().strip()
        if not query:
            QMessageBox.information(self, "Поиск", "Введите строку для поиска.")
            return

        recursive = self.recursive_cb.isChecked()

        results = search_paths(
            self.start_dir,
            query,
            recursive=recursive,
            limit=5000,
        )

        self.info.setText(
            f"Найдено объектов: {len(results)} (папка: {self.start_dir})"
        )

        for p in results:
            item = QListWidgetItem(str(p))
            item.setData(Qt.UserRole, p)
            self.listw.addItem(item)

    def on_select(self, item: Optional[QListWidgetItem], _prev):
        """Выбор элемента в списке."""
        if not item:
            self.selected_path = None
            self.btn_open.setEnabled(False)
            self.btn_goto.setEnabled(False)
            return

        self.selected_path = item.data(Qt.UserRole)
        self.btn_open.setEnabled(True)
        self.btn_goto.setEnabled(True)

    def open_item(self, item: QListWidgetItem):
        """Двойной клик по результату."""
        path: Path = item.data(Qt.UserRole)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_selected(self):
        """Открыть выбранный файл/папку."""
        if self.selected_path:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.selected_path))
            )

    def goto_selected_dir(self):
        """
        Закрывает диалог и сообщает главному окну,
        что нужно перейти в папку выбранного объекта.
        """
        if self.selected_path:
            self.accept()

    def get_selected(self) -> Optional[Path]:
        """Вернуть выбранный путь (для main_window)."""
        return self.selected_path
