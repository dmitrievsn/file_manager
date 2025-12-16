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
    Слить содержимое src_dir в dst_dir.
    Если файлы конфликтуют — новый файл сохраняется под уникальным именем.
    """
    dst_dir.mkdir(exist_ok=True)

    for item in src_dir.iterdir():
        dst_item = dst_dir / item.name

        if item.is_dir():
            # если папка уже есть — продолжаем merge внутрь неё
            merge_copy_dir(item, dst_item)
        else:
            # конфликт файла — сохраняем "оба" через unique_path
            final_dst = dst_item if not dst_item.exists() else unique_path(dst_item)
            logger.info("MERGE_COPY_FILE | %s -> %s", item, final_dst)
            shutil.copy2(str(item), str(final_dst))
