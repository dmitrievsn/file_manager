from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import QDir, Qt, QModelIndex, QUrl, QEvent
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
    QAbstractItemView
)

from core.clipboard import Clipboard
from core.ops import (
    copy_any,
    move_any,
    remove_any,
    create_file as core_create_file,
    merge_copy_dir,
    unique_file_path,
    unique_dir_path,
)
from ui.properties_dialog import PropertiesDialog
from ui.search_dialog import SearchDialog
from ui.compare_dialog import CompareDialog
from ui.batch_rename_dialog import BatchRenameDialog
from ui.attrs_dialog import AttrsDialog
from core.attrs import apply_attrs
from core.locks import is_locked


logger = logging.getLogger(__name__)


class FilePanel:
    def __init__(self):
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.rootPath())
        self.model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)

        self.view = QTreeView()
        self.view.setModel(self.model)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Ctrl/Shift мультивыбор
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.AscendingOrder)
        self.view.setColumnWidth(0, 380)

        self.path_edit = QLineEdit()
        self.root: Path = Path.home()

        # история как в проводнике
        self.history: list[Path] = []
        self.history_index: int = -1

        # кнопки навигации
        self.btn_back = QPushButton("←")
        self.btn_forward = QPushButton("→")
        self.btn_up = QPushButton("↑")


class FileManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Файловый менеджер (двухпанельный)")
        self.resize(1400, 750)

        self.clipboard = Clipboard()
        self.active: str = "L"  # "L" or "R"

        # ===== Panels =====
        self.left = FilePanel()
        self.right = FilePanel()

        # Важно: активность панели должна определяться и кликом, и фокусом (клавиатура!)
        self.left.view.clicked.connect(lambda _: self.set_active("L"))
        self.right.view.clicked.connect(lambda _: self.set_active("R"))
        self.left.view.installEventFilter(self)
        self.right.view.installEventFilter(self)

        self.left.view.doubleClicked.connect(lambda idx: self.on_double_click(self.left, idx))
        self.right.view.doubleClicked.connect(lambda idx: self.on_double_click(self.right, idx))

        self.left.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.right.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.left.view.customContextMenuRequested.connect(lambda pos: self.open_context_menu(self.left, pos))
        self.right.view.customContextMenuRequested.connect(lambda pos: self.open_context_menu(self.right, pos))

        # ===== Top bar (две панели со стрелками) =====
        def _wire_panel_nav(panel: FilePanel, which: str):
            panel.btn_back.clicked.connect(lambda: self.go_back(panel))
            panel.btn_forward.clicked.connect(lambda: self.go_forward(panel))
            panel.btn_up.clicked.connect(lambda: self.go_up(panel))
            panel.path_edit.returnPressed.connect(lambda: self.go_to_path(panel))

            # клики по кнопкам/полю тоже делают панель активной
            panel.btn_back.clicked.connect(lambda: self.set_active(which))
            panel.btn_forward.clicked.connect(lambda: self.set_active(which))
            panel.btn_up.clicked.connect(lambda: self.set_active(which))
            panel.path_edit.focusInEvent = lambda e, w=which, old=panel.path_edit.focusInEvent: (self.set_active(w),
                                                                                                 old(e))

        _wire_panel_nav(self.left, "L")
        _wire_panel_nav(self.right, "R")

        top = QWidget()
        top_l = QHBoxLayout(top)
        top_l.setContentsMargins(8, 8, 8, 8)
        top_l.setSpacing(6)

        # Левая панель: ← → ↑ [path]
        top_l.addWidget(self.left.btn_back)
        top_l.addWidget(self.left.btn_forward)
        top_l.addWidget(self.left.btn_up)
        top_l.addWidget(self.left.path_edit, 1)

        # Правая панель: ← → ↑ [path]
        top_l.addWidget(self.right.btn_back)
        top_l.addWidget(self.right.btn_forward)
        top_l.addWidget(self.right.btn_up)
        top_l.addWidget(self.right.path_edit, 1)

        # ===== Splitter =====
        split = QSplitter()
        split.addWidget(self.left.view)
        split.addWidget(self.right.view)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(top)
        lay.addWidget(split, 1)
        self.setCentralWidget(central)

        # ===== Toolbar =====
        tb = QToolBar("Main")
        self.addToolBar(tb)

        tb.addAction(self._act("Обновить", self.refresh_panels, "F5"))
        tb.addSeparator()
        tb.addAction(self._act("Поиск", self.open_search, "Ctrl+F"))
        tb.addAction(self._act("Сравнить панели", self.open_compare, "Ctrl+Alt+C"))
        tb.addAction(self._act("Пакетное переименование", self.open_batch_rename, "Ctrl+R"))
        tb.addAction(self._act("Массовые атрибуты", self.open_attrs, "Ctrl+Alt+A"))
        tb.addSeparator()
        tb.addAction(self._act("Создать папку", self.create_folder, "F7"))
        tb.addAction(self._act("Создать файл", self.create_file, "F8"))

        # ===== Hotkeys =====
        self._setup_hotkeys()

        # ===== Status =====
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # Start dirs
        self.set_panel_dir(self.left, Path.home())
        self.set_panel_dir(self.right, Path.home())
        self.set_active("L")
        self.update_status()

    # -------------------- Event Filter (focus) --------------------
    def go_back(self, panel: FilePanel):
        if panel.history_index > 0:
            panel.history_index -= 1
            self.set_panel_dir(panel, panel.history[panel.history_index], push_history=False)

    def go_forward(self, panel: FilePanel):
        if panel.history_index < len(panel.history) - 1:
            panel.history_index += 1
            self.set_panel_dir(panel, panel.history[panel.history_index], push_history=False)

    def go_up(self, panel: FilePanel):
        cur = panel.root
        parent = cur.parent
        if parent != cur:
            self.set_panel_dir(panel, parent)


    def eventFilter(self, obj, event):
        # если пользователь перемещается клавиатурой/Tab/кликает — ловим фокус
        if event.type() == QEvent.FocusIn:
            if obj is self.left.view:
                self.set_active("L")
            elif obj is self.right.view:
                self.set_active("R")
        return super().eventFilter(obj, event)

    # ===================== UTILS =====================

    def _act(self, text, fn, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(fn)
        return a

    def set_active(self, which: str):
        self.active = which
        self.status.showMessage(f"Активная панель: {'левая' if which=='L' else 'правая'}", 1000)

    def active_panel(self) -> FilePanel:
        return self.left if self.active == "L" else self.right

    def passive_panel(self) -> FilePanel:
        return self.right if self.active == "L" else self.left

    def update_panel_nav_buttons(self, panel: FilePanel):
        panel.btn_back.setEnabled(panel.history_index > 0)
        panel.btn_forward.setEnabled(panel.history_index < len(panel.history) - 1)

    def set_panel_dir(self, panel: FilePanel, path: Path, push_history: bool = True):
        path = path.expanduser().resolve()
        if not path.exists() or not path.is_dir():
            self.show_error(f"Папка не существует: {path}")
            return

        if push_history:
            # если мы “откатились назад” и идём в новую папку — обрезаем хвост
            if panel.history_index < len(panel.history) - 1:
                panel.history = panel.history[: panel.history_index + 1]
            panel.history.append(path)
            panel.history_index += 1

        panel.root = path
        panel.path_edit.setText(str(path))
        idx = panel.model.index(str(path))
        if idx.isValid():
            panel.view.setRootIndex(idx)

        self.update_panel_nav_buttons(panel)
        self.update_status()

    def go_to_path(self, panel: FilePanel):
        self.set_panel_dir(panel, Path(panel.path_edit.text()))

    # ===================== SELECTION =====================

    def selected_paths(self, panel: FilePanel) -> List[Path]:
        sel = panel.view.selectionModel().selectedRows(0)
        return [Path(panel.model.filePath(i)) for i in sel]

    def current_item(self, panel: FilePanel) -> Optional[Path]:
        idx = panel.view.currentIndex()
        if not idx.isValid():
            return None
        return Path(panel.model.filePath(idx))

    def paste_target_dir(self, panel: FilePanel) -> Path:
        # Ctrl+V / вставка: если выделена папка — в неё, иначе в корень панели
        p = self.current_item(panel)
        if p and p.exists():
            return p if p.is_dir() else p.parent
        return panel.root

    # ===================== DOUBLE CLICK =====================

    def on_double_click(self, panel: FilePanel, index: QModelIndex):
        p = Path(panel.model.filePath(index))

        if is_locked(p):
            self.show_error(f"Объект заблокирован: {p.name}")
            return

        if p.is_dir():
            self.set_panel_dir(panel, p)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    # ===================== HOTKEYS =====================

    def _setup_hotkeys(self):
        self.addAction(self._hk(QKeySequence.Copy, self.copy_selected))
        self.addAction(self._hk(QKeySequence.Cut, self.cut_selected))
        self.addAction(self._hk(QKeySequence.Paste, self.paste_hotkey))
        self.addAction(self._hk(QKeySequence.Delete, self.delete_selected))

        a_rename = QAction(self)
        a_rename.setShortcut(QKeySequence(Qt.Key_F2))
        a_rename.triggered.connect(self.rename_selected)
        self.addAction(a_rename)

    def _hk(self, seq, fn):
        a = QAction(self)
        a.setShortcut(seq)
        a.triggered.connect(fn)
        return a

    # ===================== CLIPBOARD =====================

    def copy_selected(self):
        panel = self.active_panel()
        items = self.selected_paths(panel)
        if not items:
            return

        p = items[0]
        if is_locked(p):
            self.show_error(f"Объект заблокирован: {p.name}")
            return

        self.clipboard = Clipboard(src=p, is_cut=False)
        logger.info("CLIPBOARD | COPY | %s", p)

    def cut_selected(self):
        panel = self.active_panel()
        items = self.selected_paths(panel)
        if not items:
            return

        p = items[0]
        if is_locked(p):
            self.show_error(f"Объект заблокирован: {p.name}")
            return

        self.clipboard = Clipboard(src=p, is_cut=True)
        logger.info("CLIPBOARD | CUT | %s", p)

    def paste_hotkey(self):
        panel = self.active_panel()
        dst_dir = self.paste_target_dir(panel)
        self.paste_item(dst_dir)

    def paste_item(self, dst_dir: Path):
        if not self.clipboard.src:
            return

        src = self.clipboard.src

        # 1️⃣ Проверка: источник заблокирован?
        if is_locked(src):
            self.show_error(f"Объект заблокирован: {src.name}")
            return

        dst_dir = dst_dir.expanduser().resolve()

        # 2️⃣ Проверка: нельзя вставлять в заблокированную папку
        if is_locked(dst_dir):
            self.show_error(f"Нельзя вставить в заблокированную папку: {dst_dir.name}")
            return

        dst = dst_dir / src.name

        try:
            if src.is_dir():
                # ===== Вставка папки =====
                if dst.exists() and dst.is_dir():
                    if not self.confirm_merge_dirs(dst.name):
                        return

                    logger.info("MERGE_DIR | %s -> %s", src, dst)
                    merge_copy_dir(src, dst)

                    if self.clipboard.is_cut:
                        remove_any(src)

                else:
                    if dst.exists() and dst.is_file():
                        dst = unique_dir_path(dst)

                    if self.clipboard.is_cut:
                        move_any(src, dst)
                    else:
                        copy_any(src, dst)

            else:
                # ===== Вставка файла =====
                if dst.exists():
                    dst = unique_file_path(dst)

                if self.clipboard.is_cut:
                    move_any(src, dst)
                else:
                    copy_any(src, dst)

        except Exception as e:
            self.show_error(f"Ошибка вставки: {e}")
            return

        self.clipboard = Clipboard()
        self.refresh_panels()

    # ===================== CREATE / RENAME / DELETE =====================

    def create_folder(self):
        panel = self.active_panel()
        base_dir = self.paste_target_dir(panel)

        name, ok = QInputDialog.getText(self, "Создать папку", "Имя папки:", text="NewFolder")
        if not ok or not name.strip():
            return

        folder = base_dir / name.strip()
        if folder.exists():
            folder = unique_dir_path(folder)

        try:
            logger.info("MKDIR | %s", folder)
            folder.mkdir(parents=False)
            self.refresh_panels()
        except Exception as e:
            self.show_error(f"Ошибка создания папки: {e}")

    def create_file(self):
        panel = self.active_panel()
        base_dir = self.paste_target_dir(panel)

        name, ok = QInputDialog.getText(
            self,
            "Создать файл",
            "Имя файла (например test.txt):",
            text="new_file.txt",
        )
        if not ok or not name.strip():
            return

        p = base_dir / name.strip()
        if p.exists():
            p = unique_file_path(p)

        try:
            logger.info("CREATE_FILE | %s", p)
            core_create_file(p)
            self.refresh_panels()
        except Exception as e:
            self.show_error(f"Ошибка создания файла: {e}")

    def rename_selected(self):
        panel = self.active_panel()
        p = self.current_item(panel)
        if not p:
            return

        if is_locked(p):
            self.show_error(f"Объект заблокирован: {p.name}")
            return

        new_name, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=p.name)
        if not ok or not new_name.strip():
            return

        new_path = p.parent / new_name.strip()
        if new_path.exists():
            self.show_error("Файл/папка с таким именем уже существует.")
            return

        try:
            logger.info("RENAME | %s -> %s", p, new_path)
            p.rename(new_path)
            self.refresh_panels()
        except Exception as e:
            self.show_error(f"Ошибка переименования: {e}")

    def delete_selected(self):
        panel = self.active_panel()
        items = self.selected_paths(panel)
        if not items:
            return

        locked = [x for x in items if is_locked(x)]
        if locked:
            self.show_error("Есть заблокированные объекты:\n" + "\n".join(f"• {x.name}" for x in locked))
            return

        if QMessageBox.question(
                self,
                "Удаление",
                f"Удалить выбранные объекты ({len(items)})?",
                QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return

        try:
            for x in items:
                remove_any(x)
            self.refresh_panels()
        except Exception as e:
            self.show_error(f"Ошибка удаления: {e}")

    # ===================== CONTEXT MENU =====================

    def open_context_menu(self, panel: FilePanel, pos):
        self.set_active("L" if panel is self.left else "R")  # важно: меню делает панель активной

        menu = QMenu(self)
        idx = panel.view.indexAt(pos)
        target = Path(panel.model.filePath(idx)) if idx.isValid() else None

        # вставка всегда в "правильную" цель
        paste_dir = (target if (target and target.is_dir()) else (target.parent if target else panel.root))

        if target:
            menu.addAction(self._mk_action("Открыть", lambda: self.open_item(target)))
            menu.addSeparator()
            menu.addAction(self._mk_action("Копировать", self.copy_selected))
            menu.addAction(self._mk_action("Вырезать", self.cut_selected))
            menu.addAction(self._mk_action("Вставить", lambda: self.paste_item(paste_dir), enabled=self.clipboard.src is not None))
            menu.addSeparator()
            menu.addAction(self._mk_action("Переименовать", self.rename_selected))
            menu.addAction(self._mk_action("Удалить", self.delete_selected))
            menu.addSeparator()
            menu.addAction(self._mk_action("Свойства", lambda: self.show_properties(target)))
        else:
            menu.addAction(self._mk_action("Вставить", lambda: self.paste_item(panel.root), enabled=self.clipboard.src is not None))

        menu.addSeparator()
        menu.addAction(self._mk_action("Создать папку", self.create_folder))
        menu.addAction(self._mk_action("Создать файл", self.create_file))

        menu.addSeparator()
        menu.addAction(self._mk_action("Поиск…", self.open_search))
        menu.addAction(self._mk_action("Сравнить панели…", self.open_compare))
        menu.addAction(self._mk_action("Пакетное переименование…", self.open_batch_rename))
        menu.addAction(self._mk_action("Массовые атрибуты…", self.open_attrs))

        menu.exec(panel.view.viewport().mapToGlobal(pos))

    def _mk_action(self, text, fn, enabled=True):
        a = QAction(text, self)
        a.setEnabled(enabled)
        a.triggered.connect(fn)
        return a

    def open_item(self, p: Path):
        if is_locked(p):
            self.show_error(f"Объект заблокирован: {p.name}")
            return
        if p.is_dir():
            self.set_panel_dir(self.active_panel(), p)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def show_properties(self, p: Path):
        dlg = PropertiesDialog(p, self)
        dlg.exec()

    # ===================== TOOLS: SEARCH / COMPARE / BATCH / ATTRS =====================

    def open_search(self):
        # ВАЖНО: поиск запускается из АКТИВНОЙ панели
        panel = self.active_panel()
        dlg = SearchDialog(panel.root, self)
        if dlg.exec():
            p = dlg.get_selected()
            if p:
                self.set_panel_dir(panel, p if p.is_dir() else p.parent)

    def open_compare(self):
        # сравнение всегда: левая vs правая (как в двухпанельниках)
        dlg = CompareDialog(self.left.root, self)
        dlg.right_root = self.right.root
        dlg.right_edit.setText(str(self.right.root))
        dlg.run_compare()
        dlg.exec()

    def open_batch_rename(self):
        panel = self.active_panel()
        items = self.selected_paths(panel)
        if not items:
            self.show_error("Ничего не выбрано.")
            return

        dlg = BatchRenameDialog(items, self)
        if dlg.exec():
            plan = dlg.get_plan()
            if not plan:
                self.show_error("Сначала нажми «Предпросмотр», чтобы сформировать план.")
                return
            try:
                for it in plan:
                    it.src.rename(it.dst)
                self.refresh_panels()
            except Exception as e:
                self.show_error(f"Ошибка переименования: {e}")

    def open_attrs(self):
        panel = self.active_panel()

        items = self.selected_paths(panel)
        if not items:
            cur = self.current_item(panel)
            if cur:
                items = [cur]
            else:
                self.show_error("Ничего не выбрано.")
                return

        dlg = AttrsDialog(items, self)
        if dlg.exec():
            try:
                apply_attrs(items, dlg.get_request())
                self.refresh_panels()
            except Exception as e:
                self.show_error(f"Ошибка изменения атрибутов: {e}")

    # ===================== REFRESH / STATUS =====================

    def refresh_panels(self):
        self.set_panel_dir(self.left, self.left.root)
        self.set_panel_dir(self.right, self.right.root)

    def update_status(self):
        try:
            l_count = sum(1 for _ in self.left.root.iterdir())
        except Exception:
            l_count = -1
        try:
            r_count = sum(1 for _ in self.right.root.iterdir())
        except Exception:
            r_count = -1

        self.status.showMessage(
            f"Левая: {self.left.root} (объектов: {l_count}) | "
            f"Правая: {self.right.root} (объектов: {r_count}) | "
            f"Активная: {'левая' if self.active=='L' else 'правая'}"
        )

    # ===================== MISC =====================

    def show_error(self, msg: str):
        logger.error("ERROR | %s", msg)
        QMessageBox.critical(self, "Ошибка", msg)

    def confirm_merge_dirs(self, name: str) -> bool:
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Слияние папок")
        msg.setText(
            f'В целевой папке уже существует каталог "{name}".\n\n'
            "При нажатии «OK» содержимое будет объединено.\n"
            "При конфликтах имён файлы будут сохранены с нумерацией.\n\n"
            "Продолжить?"
        )
        ok = msg.addButton("OK", QMessageBox.AcceptRole)
        msg.addButton("Отмена", QMessageBox.RejectRole)
        msg.exec()
        return msg.clickedButton() == ok
