from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDir, Qt, QModelIndex, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QFileSystemModel,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from core.clipboard import Clipboard
from core.ops import (
    copy_any,
    move_any,
    remove_any,
    create_file,
    merge_copy_dir,
    unique_file_path,
    unique_dir_path,
)

from ui.properties_dialog import PropertiesDialog
from ui.search_dialog import SearchDialog

logger = logging.getLogger(__name__)


class FileManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Файловый менеджер")
        self.resize(1200, 700)

        self.clipboard = Clipboard()
        self.history: list[Path] = []
        self.history_index = -1

        # ===== Models =====
        self.dir_model = QFileSystemModel()
        self.dir_model.setRootPath(QDir.rootPath())
        self.dir_model.setFilter(QDir.Dirs | QDir.NoDotAndDotDot)

        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(QDir.rootPath())
        self.file_model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)

        # ===== Views =====
        self.dir_tree = QTreeView()
        self.dir_tree.setModel(self.dir_model)
        self.dir_tree.setHeaderHidden(False)
        self.dir_tree.setColumnWidth(0, 260)
        self.dir_tree.clicked.connect(self.on_dir_clicked)

        # Спрячем лишние колонки у дерева папок
        for col in [1, 2, 3]:
            self.dir_tree.setColumnHidden(col, True)

        self.file_view = QTreeView()
        self.file_view.setModel(self.file_model)
        self.file_view.setSortingEnabled(True)
        self.file_view.sortByColumn(0, Qt.AscendingOrder)
        self.file_view.doubleClicked.connect(self.on_file_double_click)
        self.file_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_view.customContextMenuRequested.connect(self.open_context_menu)

        self.file_view.setColumnWidth(0, 480)
        self.file_view.setColumnWidth(1, 120)
        self.file_view.setColumnWidth(2, 200)
        self.file_view.setColumnWidth(3, 180)

        # ===== Top bar =====
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

        # ===== Splitter (two-panel) =====
        splitter = QSplitter()
        splitter.addWidget(self.dir_tree)
        splitter.addWidget(self.file_view)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(top)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        # ===== Toolbar =====
        tb = QToolBar("Main")
        self.addToolBar(tb)

        act_refresh = QAction("Обновить", self)
        act_refresh.triggered.connect(self.refresh)
        tb.addAction(act_refresh)

        act_search = QAction("Поиск", self)
        act_search.setShortcut(QKeySequence("Ctrl+F"))
        act_search.triggered.connect(self.open_search)
        tb.addAction(act_search)

        # ===== Hotkeys via Actions =====
        self._setup_hotkeys()

        # ===== Status bar =====
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # start dir
        self.set_current_dir(Path.home())
        self.file_view.selectionModel().selectionChanged.connect(self.update_status)

    # ===================== Hotkeys =====================

    def _setup_hotkeys(self):
        # Copy
        a_copy = QAction(self)
        a_copy.setShortcut(QKeySequence.Copy)
        a_copy.triggered.connect(self.copy_selected)
        self.addAction(a_copy)

        # Cut
        a_cut = QAction(self)
        a_cut.setShortcut(QKeySequence.Cut)
        a_cut.triggered.connect(self.cut_selected)
        self.addAction(a_cut)

        # Paste
        a_paste = QAction(self)
        a_paste.setShortcut(QKeySequence.Paste)
        a_paste.triggered.connect(lambda: self.paste_item(self.paste_target_dir()))
        self.addAction(a_paste)

        # Delete
        a_del = QAction(self)
        a_del.setShortcut(QKeySequence.Delete)
        a_del.triggered.connect(self.delete_selected)
        self.addAction(a_del)

        # Rename (F2)
        a_rename = QAction(self)
        a_rename.setShortcut(QKeySequence(Qt.Key_F2))
        a_rename.triggered.connect(self.rename_selected)
        self.addAction(a_rename)

        # Properties (Alt+Enter)
        a_props = QAction(self)
        a_props.setShortcut(QKeySequence("Alt+Return"))
        a_props.triggered.connect(self.show_properties_selected)
        self.addAction(a_props)

    # ===================== Navigation =====================

    def paste_target_dir(self) -> Path:
        """
        Вычисляет папку-назначение для Ctrl+V:
        - если выделена папка -> вставляем в неё
        - если выделен файл -> вставляем в его родителя
        - если ничего не выделено -> вставляем в текущую папку
        """
        p = self.selected_path()
        if p and p.exists():
            return p if p.is_dir() else p.parent
        return self.current_dir()

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

        # right panel root
        root_index = self.file_model.index(str(path))
        if root_index.isValid():
            self.file_view.setRootIndex(root_index)

        # left panel highlight
        d_idx = self.dir_model.index(str(path))
        if d_idx.isValid():
            self.dir_tree.setCurrentIndex(d_idx)
            self.dir_tree.scrollTo(d_idx)

        self.update_nav_buttons()
        self.update_status()
        logger.info("CD | %s", path)

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

    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.set_current_dir(self.history[self.history_index], push_history=False)

    def go_up(self):
        d = self.current_dir()
        parent = d.parent
        if parent != d:
            self.set_current_dir(parent)

    def refresh(self):
        self.set_current_dir(self.current_dir(), push_history=False)

    # ===================== Left panel =====================

    def on_dir_clicked(self, index: QModelIndex):
        path = Path(self.dir_model.filePath(index))
        if path.exists() and path.is_dir():
            self.set_current_dir(path)

    # ===================== Right panel actions =====================

    def selected_path(self) -> Optional[Path]:
        idx = self.file_view.currentIndex()
        if not idx.isValid():
            return None
        return Path(self.file_model.filePath(idx))

    def on_file_double_click(self, index: QModelIndex):
        path = Path(self.file_model.filePath(index))
        if path.is_dir():
            self.set_current_dir(path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_context_menu(self, pos):
        index = self.file_view.indexAt(pos)
        menu = QMenu(self)

        target_path: Optional[Path] = None
        if index.isValid():
            target_path = Path(self.file_model.filePath(index))

        if target_path:
            menu.addAction(self._mk_action("Открыть", lambda: self.open_item(target_path)))
            menu.addSeparator()
            menu.addAction(self._mk_action("Копировать", lambda: self.copy_item(target_path)))
            menu.addAction(self._mk_action("Вырезать", lambda: self.cut_item(target_path)))
            dst_dir = target_path if target_path.is_dir() else target_path.parent
            menu.addAction(
                self._mk_action(
                    "Вставить",
                    lambda: self.paste_item(dst_dir),
                    enabled=self.clipboard.src is not None,
                )
            )
            menu.addSeparator()
            menu.addAction(self._mk_action("Переименовать", lambda: self.rename_item(target_path)))
            menu.addAction(self._mk_action("Удалить", lambda: self.delete_item(target_path)))
            menu.addSeparator()
            menu.addAction(self._mk_action("Свойства", lambda: self.show_properties(target_path)))

        else:
            menu.addAction(
                self._mk_action(
                    "Вставить",
                    lambda: self.paste_item(self.current_dir()),
                    enabled=self.clipboard.src is not None,
                )
            )

        menu.addSeparator()
        menu.addAction(self._mk_action("Создать папку", self.create_folder))
        menu.addAction(self._mk_action("Создать файл", self.create_file))
        menu.exec(self.file_view.viewport().mapToGlobal(pos))

    def _mk_action(self, text, fn, enabled=True):
        a = QAction(text, self)
        a.setEnabled(enabled)
        a.triggered.connect(fn)
        return a

    def open_item(self, path: Path):
        if path.is_dir():
            self.set_current_dir(path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # ===== Clipboard operations =====

    def copy_item(self, path: Path):
        self.clipboard = Clipboard(src=path, is_cut=False)
        self.status.showMessage(f"Буфер: копировать {path.name}", 2000)
        logger.info("CLIPBOARD | COPY | %s", path)

    def cut_item(self, path: Path):
        self.clipboard = Clipboard(src=path, is_cut=True)
        self.status.showMessage(f"Буфер: переместить {path.name}", 2000)
        logger.info("CLIPBOARD | CUT | %s", path)

    def copy_selected(self):
        p = self.selected_path()
        if p:
            self.copy_item(p)

    def cut_selected(self):
        p = self.selected_path()
        if p:
            self.cut_item(p)

    def create_file(self):
        name, ok = QInputDialog.getText(
            self,
            "Создать файл",
            "Имя файла (например test.txt):",
            text="new_file.txt",
        )
        if not ok or not name.strip():
            return

        file_path = self.current_dir() / name.strip()

        # авто-нумерация именно для файла (важно: даже если существует папка с таким именем)
        if file_path.exists():
            file_path = unique_file_path(file_path)

        try:
            logger.info("CREATE_FILE | %s", file_path)
            create_file(file_path)
            self.refresh()
        except Exception as e:
            self.show_error(f"Ошибка создания файла: {e}")

    def paste_item(self, dst_dir: Optional[Path] = None):
        if not self.clipboard.src:
            return

        src = self.clipboard.src
        dst_dir = (dst_dir or self.current_dir()).expanduser().resolve()
        dst = dst_dir / src.name

        try:
            if src.is_dir():
                # ===== Вставляем ПАПКУ =====
                if dst.exists():
                    if dst.is_dir():
                        # merge папок
                        if not self.confirm_merge_dirs(dst.name):
                            return

                        logger.info("MERGE_DIR | %s -> %s", src, dst)
                        merge_copy_dir(src, dst)

                        if self.clipboard.is_cut:
                            remove_any(src)
                            self.clipboard = Clipboard()
                    else:
                        # конфликт: в месте папки уже есть ФАЙЛ => даём папке новое имя
                        dst2 = unique_dir_path(dst)
                        logger.info("DIR_CONFLICT_WITH_FILE | %s -> %s", src, dst2)

                        if self.clipboard.is_cut:
                            move_any(src, dst2)
                            self.clipboard = Clipboard()
                        else:
                            copy_any(src, dst2)
                else:
                    # dst свободен
                    if self.clipboard.is_cut:
                        move_any(src, dst)
                        self.clipboard = Clipboard()
                    else:
                        copy_any(src, dst)

            else:
                # ===== Вставляем ФАЙЛ =====
                if dst.exists():
                    if dst.is_dir():
                        # конфликт: в месте файла уже есть ПАПКА => даём файлу новое имя
                        dst2 = unique_file_path(dst)  # dst = ".../new_file.txt" (папка), получим ".../new_file (1).txt"
                        logger.info("FILE_CONFLICT_WITH_DIR | %s -> %s", src, dst2)
                    else:
                        # конфликт: файл-файл => keep both
                        dst2 = unique_file_path(dst)
                        logger.info("FILE_CONFLICT_WITH_FILE | %s -> %s", src, dst2)
                else:
                    dst2 = dst

                if self.clipboard.is_cut:
                    move_any(src, dst2)
                    self.clipboard = Clipboard()
                else:
                    copy_any(src, dst2)

        except Exception as e:
            self.show_error(f"Ошибка вставки: {e}")
            return

        self.refresh()
        self.status.showMessage("Готово.", 1500)

    # ===== Rename/Delete/Create =====

    def rename_item(self, path: Path):
        new_name, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=path.name)
        if not ok or not new_name.strip():
            return
        new_path = path.parent / new_name.strip()
        if new_path.exists():
            self.show_error("Файл/папка с таким именем уже существует.")
            return
        try:
            logger.info("RENAME | %s -> %s", path, new_path)
            path.rename(new_path)
            self.refresh()
        except Exception as e:
            self.show_error(f"Ошибка переименования: {e}")

    def rename_selected(self):
        p = self.selected_path()
        if p:
            self.rename_item(p)

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

    def delete_selected(self):
        p = self.selected_path()
        if p:
            self.delete_item(p)

    def create_folder(self):
        name, ok = QInputDialog.getText(self, "Создать папку", "Имя папки:", text="NewFolder")
        if not ok or not name.strip():
            return

        folder = self.current_dir() / name.strip()

        # авто-нумерация именно для папки
        if folder.exists():
            folder = unique_dir_path(folder)

        try:
            logger.info("MKDIR | %s", folder)
            folder.mkdir(parents=False)
            self.refresh()
        except Exception as e:
            self.show_error(f"Ошибка создания папки: {e}")

    def show_properties(self, path: Path):
        dlg = PropertiesDialog(path, self)
        dlg.exec()

    def show_properties_selected(self):
        p = self.selected_path()
        if p:
            self.show_properties(p)

    # ===== Search =====

    def open_search(self):
        dlg = SearchDialog(self.current_dir(), self)
        res = dlg.exec()
        if res:  # accept
            p = dlg.get_selected()
            if p:
                # если файл — перейдём в папку
                target_dir = p if p.is_dir() else p.parent
                self.set_current_dir(target_dir)

    # ===================== Status =====================

    def update_status(self, *_):
        # статус текущей папки: количество объектов
        try:
            root = self.current_dir()
            count = 0
            for _ in root.iterdir():
                count += 1
            msg = f"{root} | объектов: {count}"
        except Exception:
            msg = str(self.current_dir())

        sel = self.selected_path()
        if sel and sel.exists():
            if sel.is_file():
                try:
                    msg += f" | выделено: {sel.name} ({sel.stat().st_size} B)"
                except Exception:
                    msg += f" | выделено: {sel.name}"
            else:
                msg += f" | выделено: {sel.name} (папка)"
        self.status.showMessage(msg)

    def show_error(self, message: str):
        logger.error("ERROR | %s", message)
        QMessageBox.critical(self, "Ошибка", message)

    def confirm_merge_dirs(self, folder_name: str) -> bool:
        """
        Диалог подтверждения слияния папок.
        Возвращает True, если пользователь согласился.
        """
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Слияние папок")
        msg.setText(
            f'В целевой папке уже существует каталог "{folder_name}".\n\n'
            "При нажатии «OK» содержимое папок будет объединено.\n"
            "Файлы с одинаковыми именами будут сохранены в обоих вариантах "
            "с автоматическим добавлением номера.\n\n"
            "Продолжить?"
        )

        btn_ok = msg.addButton("OK", QMessageBox.AcceptRole)
        btn_cancel = msg.addButton("Отмена", QMessageBox.RejectRole)
        btn_help = msg.addButton("Справка", QMessageBox.HelpRole)

        msg.exec()

        if msg.clickedButton() == btn_help:
            QMessageBox.information(
                self,
                "Справка",
                "Слияние папок объединяет содержимое каталогов.\n\n"
                "• Существующие файлы не удаляются\n"
                "• При совпадении имён создаётся копия с номером\n"
                "• Операция необратима",
            )
            # после справки снова спрашиваем
            return self.confirm_merge_dirs(folder_name)

        return msg.clickedButton() == btn_ok

