"""SQLite bağlantısı, şema göçleri (migrations) ve yedekleme.

Güvenilirlik için: WAL + synchronous=FULL, foreign key zorunlu, yedekleme
SQLite'ın online backup API'siyle (dosya kopyalamaya göre tutarlı) yapılır
ve her yedek integrity_check ile doğrulanır.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .config import DEFAULT_SUBJECTS
from .curriculum import CURRICULUM


def new_id() -> str:
    # UUID: ileride birden fazla cihaz senkronize edilirken ID çakışmaz.
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    return conn


@contextmanager
def session(path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# --------------------------------------------------------------- şema göçleri
def _v1(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE subjects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            archived INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE weekly_goals (
            id TEXT PRIMARY KEY,
            week_start TEXT NOT NULL,
            subject_id TEXT NOT NULL REFERENCES subjects(id),
            target_minutes INTEGER NOT NULL CHECK (target_minutes > 0),
            updated_at TEXT NOT NULL,
            UNIQUE (week_start, subject_id)
        );
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            week_start TEXT NOT NULL,
            planned_date TEXT,
            subject_id TEXT NOT NULL REFERENCES subjects(id),
            title TEXT NOT NULL,
            task_type TEXT NOT NULL,
            planned_minutes INTEGER NOT NULL DEFAULT 0 CHECK (planned_minutes >= 0),
            status TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo','done')),
            carry_count INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_tasks_date ON tasks(planned_date);
        CREATE INDEX idx_tasks_week ON tasks(week_start);
        CREATE TABLE study_logs (
            id TEXT PRIMARY KEY,
            log_date TEXT NOT NULL,
            subject_id TEXT NOT NULL REFERENCES subjects(id),
            minutes INTEGER NOT NULL CHECK (minutes > 0),
            study_type TEXT NOT NULL,
            note TEXT,
            task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_logs_date ON study_logs(log_date);
        """
    )
    conn.executemany(
        "INSERT INTO subjects (id, name, sort_order, updated_at) VALUES (?,?,?,?)",
        [(new_id(), n, i, now_iso()) for i, n in enumerate(DEFAULT_SUBJECTS)],
    )


def _v2(conn: sqlite3.Connection) -> None:
    # Hızlı kayıt: çözülen soru sayısı (mevcut kayıtlar 0 olarak kalır).
    conn.execute("ALTER TABLE study_logs ADD COLUMN question_count INTEGER NOT NULL DEFAULT 0")


def _v3(conn: sqlite3.Connection) -> None:
    """Esnek akış: haftalık şablon, YKS konu listesi, görevde konu / ders değişimi izi.

    Mevcut veriye dokunmaz. Eski varsayılan dersler (Matematik, Fizik...) kullanılmışsa arşive
    alınır (geçmiş kayıtlar bozulmaz), kullanılmamışsa silinir; yerine TYT/AYT dersleri gelir.
    """
    conn.execute("ALTER TABLE subjects ADD COLUMN exam TEXT NOT NULL DEFAULT ''")
    conn.execute(
        """CREATE TABLE topics (
            id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL REFERENCES subjects(id),
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            done INTEGER NOT NULL DEFAULT 0,
            done_at TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE (subject_id, name)
        )""")
    conn.execute("CREATE INDEX idx_topics_subject ON topics(subject_id)")
    conn.execute(
        """CREATE TABLE weekly_template (
            id TEXT PRIMARY KEY,
            weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
            subject_id TEXT NOT NULL REFERENCES subjects(id),
            minutes INTEGER NOT NULL DEFAULT 60 CHECK (minutes > 0),
            updated_at TEXT NOT NULL,
            UNIQUE (weekday, subject_id)
        )""")
    conn.execute("ALTER TABLE tasks ADD COLUMN topic_id TEXT REFERENCES topics(id) ON DELETE SET NULL")
    conn.execute("ALTER TABLE tasks ADD COLUMN original_subject_id TEXT REFERENCES subjects(id)")
    conn.execute("ALTER TABLE tasks ADD COLUMN topic_marked INTEGER NOT NULL DEFAULT 0")

    for (sid,) in conn.execute("SELECT id FROM subjects WHERE exam=''").fetchall():
        used = conn.execute(
            """SELECT (SELECT COUNT(*) FROM tasks WHERE subject_id=:s)
                    + (SELECT COUNT(*) FROM study_logs WHERE subject_id=:s)
                    + (SELECT COUNT(*) FROM weekly_goals WHERE subject_id=:s)""", {"s": sid}).fetchone()[0]
        if used:
            conn.execute("UPDATE subjects SET archived=1, updated_at=? WHERE id=?", (now_iso(), sid))
        else:
            conn.execute("DELETE FROM subjects WHERE id=?", (sid,))
    seed_curriculum(conn)


def seed_curriculum(conn: sqlite3.Connection) -> None:
    """Eksik YKS derslerini ve konularını ekler (var olanlara dokunmaz, tekrar çalıştırılabilir)."""
    for si, (exam, name, topics) in enumerate(CURRICULUM):
        row = conn.execute("SELECT id FROM subjects WHERE name=?", (name,)).fetchone()
        if row:
            sid = row["id"]
            conn.execute("UPDATE subjects SET exam=? WHERE id=? AND exam=''", (exam, sid))
        else:
            sid = new_id()
            conn.execute("INSERT INTO subjects (id,name,sort_order,exam,updated_at) VALUES (?,?,?,?,?)",
                         (sid, name, 100 + si, exam, now_iso()))
        for ti, topic in enumerate(topics):
            conn.execute("INSERT OR IGNORE INTO topics (id,subject_id,name,sort_order,updated_at) "
                         "VALUES (?,?,?,?,?)", (new_id(), sid, topic, ti, now_iso()))


MIGRATIONS = [_v1, _v2, _v3]  # Yeni şema değişikliği = listeye yeni fonksiyon ekle.


def initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for i, migrate in enumerate(MIGRATIONS[version:], start=version + 1):
            with conn:  # tek transaction: ya hep ya hiç
                migrate(conn)
                conn.execute(f"PRAGMA user_version={i}")
    finally:
        conn.close()


# ------------------------------------------------------------------ yedekleme
def _integrity_ok(path: Path) -> bool:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def create_backup(db_path: Path, backup_dir: Path, label: str = "manual") -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backup_dir / f"studyflow-{stamp}-{label}.db"
    src, dst = connect(db_path), sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    if not _integrity_ok(dest):
        dest.unlink(missing_ok=True)
        raise RuntimeError("Yedek doğrulanamadı; dosya silindi.")
    return dest


def list_backups(backup_dir: Path) -> list[Path]:
    if not backup_dir.exists():
        return []
    return sorted(backup_dir.glob("studyflow-*.db"), reverse=True)


def daily_backup(db_path: Path, backup_dir: Path, keep: int) -> Path | None:
    """Bugün için otomatik yedek yoksa alır; eski otomatik yedekleri temizler."""
    today = datetime.now().strftime("%Y%m%d")
    autos = [p for p in list_backups(backup_dir) if p.stem.endswith("-auto")]
    created = None
    if not any(p.name.startswith(f"studyflow-{today}") for p in autos):
        created = create_backup(db_path, backup_dir, "auto")
        autos = [created] + autos
    for old in autos[keep:]:  # manuel ve geri-yükleme yedekleri asla silinmez
        old.unlink(missing_ok=True)
    return created


def restore_backup(backup: Path, db_path: Path, backup_dir: Path) -> Path:
    """Yedeği geri yükler. Önce mevcut veriyi 'pre-restore' olarak yedekler."""
    if not _integrity_ok(backup):
        raise RuntimeError("Seçilen yedek bozuk, geri yükleme yapılmadı.")
    safety = create_backup(db_path, backup_dir, "pre-restore")
    tmp = db_path.with_suffix(".restore.tmp")
    shutil.copy2(backup, tmp)
    for suffix in ("-wal", "-shm"):
        Path(str(db_path) + suffix).unlink(missing_ok=True)
    os.replace(tmp, db_path)  # atomik değiştirme
    initialize(db_path)  # eski sürümden alınmış yedek de güncel şemaya yükseltilir
    return safety
