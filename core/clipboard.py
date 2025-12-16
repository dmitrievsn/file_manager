from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Clipboard:
    src: Optional[Path] = None
    is_cut: bool = False  # False=copy, True=cut(move)
