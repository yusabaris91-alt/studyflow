"""Veri modelleri (dataclass). Tarihler uygulama içinde `date`, DB'de ISO metin."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta


def week_start(d: date) -> date:
    """Verilen günün haftasının Pazartesi'sini döndürür."""
    return d - timedelta(days=d.weekday())


@dataclass(frozen=True)
class Subject:
    id: str
    name: str
    sort_order: int
    archived: bool
    exam: str = ""  # 'TYT' | 'AYT' | '' (kullanıcının eklediği ders)

    @classmethod
    def from_row(cls, r: sqlite3.Row) -> "Subject":
        return cls(r["id"], r["name"], r["sort_order"], bool(r["archived"]), r["exam"])


@dataclass(frozen=True)
class Topic:
    id: str
    subject_id: str
    name: str
    sort_order: int
    done: bool

    @classmethod
    def from_row(cls, r: sqlite3.Row) -> "Topic":
        return cls(r["id"], r["subject_id"], r["name"], r["sort_order"], bool(r["done"]))


@dataclass(frozen=True)
class TemplateEntry:
    """Haftalık şablonda bir günün havuzundaki ders (saat değil, sadece o gün çalışılacak ders)."""
    id: str
    weekday: int  # 0 = Pazartesi ... 6 = Pazar
    subject_id: str
    minutes: int  # o gün için hedef süre

    @classmethod
    def from_row(cls, r: sqlite3.Row) -> "TemplateEntry":
        return cls(r["id"], r["weekday"], r["subject_id"], r["minutes"])


@dataclass(frozen=True)
class Task:
    id: str
    week_start: date
    planned_date: date | None  # None => haftalık görev havuzunda
    subject_id: str
    title: str
    task_type: str
    planned_minutes: int
    status: str  # 'todo' | 'done'
    carry_count: int
    topic_id: str | None = None
    original_subject_id: str | None = None  # ders değiştirildiyse başlangıçta planlanan ders

    @property
    def done(self) -> bool:
        return self.status == "done"

    @classmethod
    def from_row(cls, r: sqlite3.Row) -> "Task":
        pd = r["planned_date"]
        return cls(
            r["id"], date.fromisoformat(r["week_start"]),
            date.fromisoformat(pd) if pd else None,
            r["subject_id"], r["title"], r["task_type"],
            r["planned_minutes"], r["status"], r["carry_count"],
            r["topic_id"], r["original_subject_id"],
        )


@dataclass(frozen=True)
class StudyLog:
    id: str
    log_date: date
    subject_id: str
    minutes: int
    study_type: str
    note: str
    task_id: str | None
    question_count: int = 0

    @classmethod
    def from_row(cls, r: sqlite3.Row) -> "StudyLog":
        return cls(
            r["id"], date.fromisoformat(r["log_date"]), r["subject_id"],
            r["minutes"], r["study_type"], r["note"] or "", r["task_id"],
            r["question_count"],
        )
