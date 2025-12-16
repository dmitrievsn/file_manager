import os
from pathlib import Path
from typing import List


def search_paths(root: Path, query: str, recursive: bool = True, limit: int = 5000) -> List[Path]:
    """
    Самостоятельная реализация поиска по подстроке имени (case-insensitive).
    - обход файловой системы через os.scandir()
    - DFS (стек каталогов)
    - обработка PermissionError/OSError
    - limit для защиты от слишком долгого поиска
    - follow_symlinks=False, чтобы не попадать в циклы

    Возвращает список найденных Path.
    """
    # 1) Нормализуем запрос
    if not isinstance(query, str):
        raise TypeError(f"query must be str, got {type(query).__name__}")

    q = query.strip().lower()
    if not q:
        return []

    # 2) Нормализуем root
    root = root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return []

    results: List[Path] = []

    # 3) DFS стек: если recursive=False — просто обрабатываем root без углубления
    stack: List[Path] = [root]

    while stack and len(results) < limit:
        cur_dir = stack.pop()

        try:
            with os.scandir(cur_dir) as it:
                for entry in it:
                    if len(results) >= limit:
                        break

                    # имя
                    try:
                        name = entry.name.lower()
                    except Exception:
                        continue

                    # совпадение по подстроке
                    if q in name:
                        results.append(Path(entry.path))
                        if len(results) >= limit:
                            break

                    # углубление
                    if recursive:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(Path(entry.path))
                        except OSError:
                            # нет прав/битый entry/ошибка ФС
                            pass

        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            # нет доступа, каталог удалили, или другая ошибка
            continue

    return results
