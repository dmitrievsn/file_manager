from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib
import os


@dataclass(frozen=True)
class FileInfo:
    rel: str
    size: int
    mtime_ns: int
    is_dir: bool
    sha256: Optional[str] = None


@dataclass
class CompareResult:
    left_root: Path
    right_root: Path
    only_left: List[FileInfo]
    only_right: List[FileInfo]
    different: List[Tuple[FileInfo, FileInfo]]
    same: List[Tuple[FileInfo, FileInfo]]


def _sha256_file(p: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def index_tree(root: Path, use_hash: bool = False, limit: int = 200_000) -> Dict[str, FileInfo]:
    """
    Индексирует дерево root в словарь rel_path -> FileInfo.
    use_hash=True: для файлов считает sha256 (медленнее, но точнее).
    """
    root = root.expanduser().resolve()
    out: Dict[str, FileInfo] = {}

    # DFS вручную через стек + os.scandir (быстро и контролируемо)
    stack = [root]
    while stack and len(out) < limit:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    rel = str(Path(e.path).resolve().relative_to(root))
                    try:
                        is_dir = e.is_dir(follow_symlinks=False)
                    except OSError:
                        continue

                    try:
                        st = e.stat(follow_symlinks=False)
                        size = int(st.st_size)
                        mtime_ns = int(st.st_mtime_ns)
                    except OSError:
                        size = 0
                        mtime_ns = 0

                    sha = None
                    if use_hash and (not is_dir):
                        try:
                            sha = _sha256_file(Path(e.path))
                        except Exception:
                            sha = None

                    out[rel] = FileInfo(rel=rel, size=size, mtime_ns=mtime_ns, is_dir=is_dir, sha256=sha)

                    if is_dir:
                        stack.append(Path(e.path))
        except Exception:
            continue

    return out


def compare_dirs(left: Path, right: Path, use_hash: bool = False) -> CompareResult:
    left = left.expanduser().resolve()
    right = right.expanduser().resolve()

    L = index_tree(left, use_hash=use_hash)
    R = index_tree(right, use_hash=use_hash)

    only_left: List[FileInfo] = []
    only_right: List[FileInfo] = []
    different: List[Tuple[FileInfo, FileInfo]] = []
    same: List[Tuple[FileInfo, FileInfo]] = []

    keys = set(L.keys()) | set(R.keys())
    for k in sorted(keys):
        a = L.get(k)
        b = R.get(k)
        if a is None:
            only_right.append(b)  # type: ignore
            continue
        if b is None:
            only_left.append(a)
            continue

        # оба существуют
        if a.is_dir != b.is_dir:
            different.append((a, b))
            continue

        if a.is_dir and b.is_dir:
            same.append((a, b))
            continue

        # файлы: сравниваем по size+mtime, при use_hash — ещё и hash
        if use_hash:
            if a.size == b.size and a.sha256 and b.sha256 and a.sha256 == b.sha256:
                same.append((a, b))
            else:
                different.append((a, b))
        else:
            if a.size == b.size and a.mtime_ns == b.mtime_ns:
                same.append((a, b))
            else:
                different.append((a, b))

    return CompareResult(
        left_root=left,
        right_root=right,
        only_left=only_left,
        only_right=only_right,
        different=different,
        same=same,
    )
