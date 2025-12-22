from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
import re


@dataclass(frozen=True)
class RenamePlanItem:
    src: Path
    dst: Path


def _apply_template(idx: int, template: str) -> str:
    """
    Поддержка:
      {n}        -> 1,2,3
      {n:03}     -> 001,002,003
      {n:5}      -> 00001 (как padding)
    """
    def repl(m: re.Match) -> str:
        width = m.group(1)
        if width:
            w = int(width)
            return str(idx).zfill(w)
        return str(idx)

    return re.sub(r"\{n(?::([0-9]+))?\}", repl, template)


def build_plan(
    paths: List[Path],
    mode: str,
    a: str,
    b: str,
    template: str,
    start: int = 1,
    step: int = 1,
) -> List[RenamePlanItem]:
    """
    mode:
      - prefix: добавить префикс
      - suffix: добавить суффикс (до расширения)
      - replace: заменить подстроку A -> B
      - regex: regex A -> B
      - template: имя по шаблону (template или B) с {n}/{n:03}, расширение сохраняется
    """

    a = (a or "").strip()
    b = (b or "").strip()
    template = (template or "").strip()

    if mode in ("prefix", "suffix"):
        affix = b or a
        if not affix:
            raise ValueError("Для режима префикса/суффикса нужно заполнить поле B (или A).")

    if mode == "replace":
        if not a:
            raise ValueError("Для режима «Замена текста» нужно заполнить поле A (что искать).")

    if mode == "regex":
        if not a:
            raise ValueError("Для режима «Regex замена» нужно заполнить поле A (regex).")
        try:
            re.compile(a)
        except re.error as e:
            raise ValueError(f"Некорректное регулярное выражение: {e}")

    if mode == "template":
        tpl = template or b
        if not tpl:
            raise ValueError("Для режима «Шаблон» нужно заполнить поле «Шаблон» или поле B.")
        if "{n" not in tpl:
            raise ValueError("В шаблоне должен быть маркер {n} (например file_{n:03}).")

    out: List[RenamePlanItem] = []
    idx = start
    for p in paths:
        parent = p.parent
        stem = p.stem
        suffix = p.suffix
        if mode == "prefix":
            new_stem = (b or a) + stem
        elif mode == "suffix":
            new_stem = stem + (b or a)
        elif mode == "replace":
            new_stem = stem.replace(a, b)
        elif mode == "regex":
            new_stem = re.sub(a, b, stem)
        elif mode == "template":
            tpl = template or b
            new_stem = _apply_template(idx, tpl)
        else:
            raise ValueError("Unknown mode")
        new_name = f"{new_stem}{suffix}"
        dst = parent / new_name
        out.append(RenamePlanItem(src=p, dst=dst))
        idx += step

    dsts = [x.dst for x in out]
    if len(set(dsts)) != len(dsts):
        raise ValueError("Конфликт: в плане есть одинаковые целевые имена. Проверь шаблон/параметры.")

    for it in out:
        if it.dst.exists() and it.dst.resolve() != it.src.resolve():
            raise ValueError(f"Конфликт: файл уже существует: {it.dst.name}")

    return out
