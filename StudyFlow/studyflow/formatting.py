"""Saf biçimlendirme yardımcıları (UI ve servisler ortak kullanır)."""
from __future__ import annotations


def fmt_minutes(m: int) -> str:
    h, mm = divmod(int(m), 60)
    if h and mm:
        return f"{h} sa {mm} dk"
    return f"{h} sa" if h else f"{mm} dk"
