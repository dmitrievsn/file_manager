from __future__ import annotations

import json
from pathlib import Path
from typing import Set

# где храним “внутреннюю блокировку”
_DB_DIR = Path.home() / ".file_manager"
_DB_PATH = _DB_DIR / "locks.json"


def _norm(p: Path) -> str:
    return str(p.expanduser().resolve())


def _load_set() -> Set[str]:
    try:
        if not _DB_PATH.exists():
            return set()
        data = json.loads(_DB_PATH.read_text(encoding="utf-8"))
        items = data.get("locked", [])
        return set(str(x) for x in items)
    except Exception:
        return set()


def _save_set(s: Set[str]) -> None:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    data = {"locked": sorted(s)}
    _DB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_locked(p: Path) -> bool:
    """True если путь помечен как заблокированный (внутри менеджера)."""
    return _norm(p) in _load_set()


def set_locked(p: Path, locked: bool) -> None:
    """Установить/снять внутреннюю блокировку."""
    s = _load_set()
    key = _norm(p)
    if locked:
        s.add(key)
    else:
        s.discard(key)
    _save_set(s)
