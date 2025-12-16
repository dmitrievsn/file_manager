from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDir, Qt, QModelIndex, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QFileSystemModel,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from core.clipboard import Clipboard
from core.ops import copy_any, move_any, remove_any


class FileManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Файловый менеджер (Python / PySide6)")
        self.resize(1100, 650)

        self.clipboard = Clipboard()
        self.history: list[Path] = []
        self.history_index = -1

        # --- Model ---
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.rootPath())
        self.model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)

        # --- View ---
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.AscendingOrder)
        self.tree.doubleClicked.connect(self.on_double_click)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)

        # columns: 0 name, 1 size, 2 type, 3 modified
        self.tree.setColumnWidth(0, 420)
        self.tree.setColumnWidth(1, 120)
        self.tree.setColumnWidth(2, 180)
        self.tree.setColumnWidth(3, 180)

        # --- Top bar ---
        self.path_edit = QLineEdit()
        self.path_edit.returnPressed.connect(self.go_to_path)

        self.btn_back = QPushButton("←")
        self.btn_forward = QPushButton("→")
        self.btn_up = QPushButton("↑")

        self.btn_back.clicked.connect(self.go_back)
        self.btn_forward.clicked.connect(self.go_forward)
        self.btn_up.clicked.connect(self.go_up)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(8, 8, 8, 8)
        top_layout.addWidget(self.btn_back)
        top_layout.addWidget(self.btn_forward)
        top_layout.addWidget(self.btn_up)
        top_layout.addWidget(self.path_edit, 1)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(top)
        layout.addWidget(self.tree, 1)
        self.setCentralWidget(central)

        # --- Toolbar ---
        tb = QToolBar("Main")
        self.addToolBar(tb)

        act_refresh = QAction("Обновить", self)
        act_refresh.triggered.connect(self.refresh)
        tb.addAction(act_refresh)

        # --- Status bar ---
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # start dir
        self.set_current_dir(Path.home())
        self.tree.selectionModel().selectionChanged.connect(self.update_status)

    # ===================== Navigation =====================

    def set_current_dir(self, path: Path, push_history: bool = True):
        path = path.expanduser().resolve()
        if not path.exists() or not path.is_dir():
            self.show_error(f"Папка не существует: {path}")
            return

        if push_history:
            if self.history_index < len(self.history) - 1:
                self.history = self.history[: self.history_index + 1]
            self.history.append(path)
            self.history_index += 1

        self.path_edit.setText(str(path))
        root_index = self.model.index(str(path))
        if root_index.isValid():
            self.tree.setRootIndex(root_index)
            self.update_nav_buttons()
            self.update_status()

    def current_dir(self) -> Path:
        return Path(self.path_edit.text()).expanduser().resolve()

    def update_nav_buttons(self):
        self.btn_back.setEnabled(self.history_index > 0)
        self.btn_forward.setEnabled(self.history_index < len(self.history) - 1)

    def go_to_path(self):
        self.set_current_dir(Path(self.path_edit.text()))

    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.set_current_dir(self.history[self.history_index], push_history=False)
            self.update_nav_buttons()

    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.set_current_dir(self.history[self.history_index], push_history=False)
            self.update_nav_buttons()

    def go_up(self):
        d = self.current_dir()
        parent = d.parent
        if parent != d:
            self.set_current_dir(parent)

    def refresh(self):
        self.set_current_dir(self.current_dir(), push_history=False)

    # ===================== UI actions =====================

    def on_double_click(self, index: QModelIndex):
        path = Path(self.model.filePath(index))
        if path.is_dir():
            self.set_current_dir(path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_context_menu(self, pos):
        index = self.tree.indexAt(pos)
        menu = QMenu(self)

        target_path: Optional[Path] = None
        if index.isValid():
            target_path = Path(self.model.filePath(index))

        if target_path:
            act_open = QAction("Открыть", self)
            act_open.triggered.connect(lambda: self.open_item(target_path))
            menu.addAction(act_open)

            menu.addSeparator()

            act_copy = QAction("Копировать", self)
            act_copy.triggered.connect(lambda: self.copy_item(target_path))
            menu.addAction(act_copy)

            act_cut = QAction("Вырезать", self)
            act_cut.triggered.connect(lambda: self.cut_item(target_path))
            menu.addAction(act_cut)

            act_rename = QAction("Переименовать", self)
            act_rename.triggered.connect(lambda: self.rename_item(target_path))
            menu.addAction(act_rename)

            act_delete = QAction("Удалить", self)
            act_delete.triggered.connect(lambda: self.delete_item(target_path))
            menu.addAction(act_delete)

            menu.addSeparator()

        act_paste = QAction("Вставить", self)
        act_paste.setEnabled(self.clipboard.src is not None)
        act_paste.triggered.connect(self.paste_item)
        menu.addAction(act_paste)

        act_new_folder = QAction("Создать папку", self)
        act_new_folder.triggered.connect(self.create_folder)
        menu.addAction(act_new_folder)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def open_item(self, path: Path):
        if path.is_dir():
            self.set_current_dir(path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def copy_item(self, path: Path):
        self.clipboard = Clipboard(src=path, is_cut=False)
        self.status.showMessage(f"Буфер: копировать {path.name}", 2500)

    def cut_item(self, path: Path):
        self.clipboard = Clipboard(src=path, is_cut=True)
        self.status.showMessage(f"Буфер: переместить {path.name}", 2500)

    def paste_item(self):
        if not self.clipboard.src:
            return

        src = self.clipboard.src
        dst_dir = self.current_dir()
        dst = dst_dir / src.name

        try:
            if src.resolve() == dst.resolve():
                self.show_error("Источник и назначение совпадают.")
                return
        except Exception:
            pass

        if dst.exists():
            res = QMessageBox.question(
                self,
                "Перезаписать?",
                f"'{dst.name}' уже существует. Перезаписать?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if res != QMessageBox.Yes:
                return
            try:
                remove_any(dst)
            except Exception as e:
                self.show_error(f"Не удалось удалить существующий объект: {e}")
                return

        try:
            if self.clipboard.is_cut:
                move_any(src, dst)
                self.clipboard = Clipboard()  # clear after move
            else:
                copy_any(src, dst)
        except Exception as e:
            self.show_error(f"Ошибка вставки: {e}")
            return

        self.refresh()
        self.status.showMessage("Готово.", 2000)

    def rename_item(self, path: Path):
        new_name, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=path.name)
        if not ok or not new_name.strip():
            return
        new_path = path.parent / new_name.strip()
        if new_path.exists():
            self.show_error("Файл/папка с таким именем уже существует.")
            return
        try:
            path.rename(new_path)
            self.refresh()
        except Exception as e:
            self.show_error(f"Ошибка переименования: {e}")

    def delete_item(self, path: Path):
        res = QMessageBox.question(
            self,
            "Удаление",
            f"Удалить '{path.name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return
        try:
            remove_any(path)
            self.refresh()
        except Exception as e:
            self.show_error(f"Ошибка удаления: {e}")

    def create_folder(self):
        name, ok = QInputDialog.getText(self, "Создать папку", "Имя папки:", text="NewFolder")
        if not ok or not name.strip():
            return
        folder = self.current_dir() / name.strip()
        if folder.exists():
            self.show_error("Такая папка уже существует.")
            return
        try:
            folder.mkdir(parents=False)
            self.refresh()
        except Exception as e:
            self.show_error(f"Ошибка создания папки: {e}")

    # ===================== Helpers =====================

    def update_status(self, *_):
        index = self.tree.currentIndex()
        if index.isValid():
            p = Path(self.model.filePath(index))
            if p.exists():
                if p.is_dir():
                    self.status.showMessage(f"Папка: {p.name}")
                else:
                    try:
                        size = p.stat().st_size
                        self.status.showMessage(f"Файл: {p.name} | {size} байт")
                    except Exception:
                        self.status.showMessage(f"Файл: {p.name}")
            else:
                self.status.clearMessage()
        else:
            self.status.showMessage(str(self.current_dir()))

    def show_error(self, message: str):
        QMessageBox.critical(self, "Ошибка", message)
