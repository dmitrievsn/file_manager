import shutil
from pathlib import Path


def remove_any(path: Path) -> None:
    """Удалить файл или папку рекурсивно."""
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def copy_any(src: Path, dst: Path) -> None:
    """Скопировать файл или папку в новое место."""
    if src.is_dir():
        shutil.copytree(str(src), str(dst))
    else:
        shutil.copy2(str(src), str(dst))


def move_any(src: Path, dst: Path) -> None:
    """Переместить файл или папку в новое место."""
    shutil.move(str(src), str(dst))
