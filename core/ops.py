import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def remove_any(path: Path) -> None:
    """Удалить файл или папку рекурсивно."""
    logger.info("DELETE | %s", path)
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def copy_any(src: Path, dst: Path) -> None:
    """Скопировать файл или папку."""
    logger.info("COPY | %s -> %s", src, dst)
    if src.is_dir():
        shutil.copytree(str(src), str(dst))
    else:
        shutil.copy2(str(src), str(dst))


def move_any(src: Path, dst: Path) -> None:
    """Переместить файл или папку."""
    logger.info("MOVE | %s -> %s", src, dst)
    shutil.move(str(src), str(dst))


def create_file(path: Path, content: str = "") -> None:
    """
    Создать файл по указанному пути.
    Если файл уже существует — будет выброшено исключение.
    """
    if path.exists():
        raise FileExistsError(f"Файл уже существует: {path}")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def unique_path(path: Path) -> Path:
    """
    Возвращает уникальный путь, добавляя ' (n)' перед расширением (для файлов)
    или ' (n)' к имени (для папок).
    """
    if not path.exists():
        return path

    parent = path.parent

    # Папки (или что-то без расширения), нумеруем по имени
    if path.exists() and path.is_dir():
        base = path.name
        i = 1
        while True:
            cand = parent / f"{base} ({i})"
            if not cand.exists():
                return cand
            i += 1

    # Файлы: stem (n).suffix
    stem = path.stem
    suffix = path.suffix
    i = 1
    while True:
        cand = parent / f"{stem} ({i}){suffix}"
        if not cand.exists():
            return cand
        i += 1


def merge_copy_dir(src_dir: Path, dst_dir: Path) -> None:
    """
    Слияние каталогов: копирует содержимое ИЗ src_dir В dst_dir.

    Правила:
    - Папки объединяются рекурсивно.
    - Файлы с одинаковыми именами сохраняются оба: добавляется номер (keep both).
    - В src_dir ничего не создаётся и не изменяется.
    """
    src_dir = src_dir.expanduser().resolve()
    dst_dir = dst_dir.expanduser().resolve()

    if not src_dir.exists() or not src_dir.is_dir():
        raise ValueError(f"merge_copy_dir: src_dir is not a directory: {src_dir}")

    # создаём dst_dir при необходимости
    dst_dir.mkdir(parents=True, exist_ok=True)

    for src_item in src_dir.iterdir():
        dst_item = dst_dir / src_item.name

        if src_item.is_dir():
            # если в назначении файл с таким именем — создаём новую папку с номером
            if dst_item.exists() and dst_item.is_file():
                dst_item = unique_dir_path(dst_item)

            # рекурсивный merge
            merge_copy_dir(src_item, dst_item)

        else:
            # src_item — файл
            if dst_item.exists():
                # если в назначении папка с таким именем или файл — keep both
                dst_item = unique_file_path(dst_item)

            shutil.copy2(src_item, dst_item)


def unique_file_path(dst: Path) -> Path:
    """
    Уникальное имя именно ДЛЯ ФАЙЛА (с сохранением расширения),
    даже если dst уже существует и является папкой.
    """
    parent = dst.parent
    stem = dst.stem
    suffix = dst.suffix  # '.txt'

    i = 1
    while True:
        cand = parent / f"{stem} ({i}){suffix}"
        if not cand.exists():
            return cand
        i += 1


def unique_dir_path(dst: Path) -> Path:
    """
    Уникальное имя именно ДЛЯ ПАПКИ, даже если в имени есть точки.
    """
    parent = dst.parent
    base = dst.name

    i = 1
    while True:
        cand = parent / f"{base} ({i})"
        if not cand.exists():
            return cand
        i += 1
