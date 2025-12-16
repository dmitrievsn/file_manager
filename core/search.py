from __future__ import annotations

from pathlib import Path
from typing import Iterable


def search_paths(root: Path, query: str, recursive: bool = True, limit: int = 5000) -> Iterable[Path]:
    """
    Поиск по подстроке в имени (case-insensitive).
    limit защищает от слишком долгого поиска.
    """
    q = query.strip().lower()
    if not q:
        return []

    root = root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return []

    results = []
    it = root.rglob("*") if recursive else root.iterdir()

    for p in it:
        try:
            name = p.name.lower()
        except Exception:
            continue

        if q in name:
            results.append(p)
            if len(results) >= limit:
                break

    return results
