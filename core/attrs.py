from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.locks import set_locked  # важно


@dataclass(frozen=True)
class AttrsRequest:
    set_readonly: Optional[bool] = None
    set_locked: Optional[bool] = None
    mtime: Optional[datetime] = None
    atime: Optional[datetime] = None


def apply_attrs(paths: List[Path], req: AttrsRequest) -> None:
    for p in paths:
        p = p.expanduser().resolve()
        if not p.exists():
            continue

        # read-only
        if req.set_readonly is not None:
            try:
                mode = p.stat().st_mode
                if req.set_readonly:
                    os.chmod(p, mode & ~stat.S_IWUSR)
                else:
                    os.chmod(p, mode | stat.S_IWUSR)
            except Exception:
                pass

        # locked (внутренняя блокировка менеджера)
        if req.set_locked is not None:
            try:
                set_locked(p, req.set_locked)
            except Exception:
                pass

        # times
        if req.mtime is not None or req.atime is not None:
            try:
                st = p.stat()
                at = req.atime.timestamp() if req.atime else st.st_atime
                mt = req.mtime.timestamp() if req.mtime else st.st_mtime
                os.utime(p, (at, mt))
            except Exception:
                pass
