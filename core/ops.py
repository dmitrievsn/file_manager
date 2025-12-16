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
