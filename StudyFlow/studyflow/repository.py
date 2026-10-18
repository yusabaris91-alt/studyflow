"""Veri erişim katmanı. Tüm SQL burada; UI hiçbir zaman SQL görmez.

İleride veritabanı değiştiğinde (ör. Supabase/Postgres) sadece bu sınıfın
aynı metotları sunan yeni bir uygulaması yazılır.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

from . import db
from .models import StudyLog, Subject, Task, TemplateEntry, Topic, week_start


class Repository:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    @contextmanager
    def _s(self) -> Iterator:
        with db.session(self.db_path) as conn:
            yield conn

    # ------------------------------------------------------------- dersler
    def list_subjects(self, include_archived: bool = False) -> list[Subject]:
        q = "SELECT * FROM subjects"
        if not include_archived:
            q += " WHERE archived = 0"
        with self._s() as c:
            return [Subject.from_row(r) for r in c.execute(q + " ORDER BY sort_order, name")]

    def add_subject(self, name: str, exam: str = "") -> None:
        name = name.strip()
        if not name:
            raise ValueError("Ders adı boş olamaz.")
        with self._s() as c:
            # SQLite lower() yalnız ASCII'yi küçültür (Ö, Ç, Ş...); karşılaştırmayı Python'da yap.
            row = next((r for r in c.execute("SELECT id, name FROM subjects")
                        if r["name"].casefold() == name.casefold()), None)
            if row:  # arşivdeki dersi geri getir
                c.execute("UPDATE subjects SET archived=0, updated_at=? WHERE id=?", (db.now_iso(), row["id"]))
                return
            order = c.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM subjects").fetchone()[0]
            c.execute(
                "INSERT INTO subjects (id,name,sort_order,exam,updated_at) VALUES (?,?,?,?,?)",
                (db.new_id(), name, order, exam, db.now_iso()),
            )

    def set_subject_archived(self, subject_id: str, archived: bool) -> None:
        # Ders silinmez, arşivlenir: geçmiş kayıtlar bozulmasın.
        with self._s() as c:
            c.execute("UPDATE subjects SET archived=?, updated_at=? WHERE id=?",
                      (int(archived), db.now_iso(), subject_id))

    # ------------------------------------------------------------- konular
    def list_topics(self, subject_id: str | None = None) -> list[Topic]:
        q, params = "SELECT * FROM topics", ()
        if subject_id:
            q, params = q + " WHERE subject_id=?", (subject_id,)
        with self._s() as c:
            return [Topic.from_row(r) for r in c.execute(q + " ORDER BY sort_order, name", params)]

    def get_topic(self, topic_id: str) -> Topic | None:
        with self._s() as c:
            r = c.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
            return Topic.from_row(r) if r else None

    def add_topic(self, subject_id: str, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("Konu adı boş olamaz.")
        with self._s() as c:
            if any(r["name"].casefold() == name.casefold() for r in
                   c.execute("SELECT name FROM topics WHERE subject_id=?", (subject_id,))):
                raise ValueError("Bu konu zaten listede.")
            order = c.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM topics WHERE subject_id=?",
                              (subject_id,)).fetchone()[0]
            c.execute("INSERT INTO topics (id,subject_id,name,sort_order,updated_at) VALUES (?,?,?,?,?)",
                      (db.new_id(), subject_id, name, order, db.now_iso()))

    def delete_topic(self, topic_id: str) -> None:
        with self._s() as c:  # görevlerdeki topic_id NULL olur, kayıtlar korunur
            c.execute("DELETE FROM topics WHERE id=?", (topic_id,))

    def set_topic_done(self, topic_id: str, done: bool) -> None:
        now = db.now_iso()
        with self._s() as c:
            c.execute("UPDATE topics SET done=?, done_at=?, updated_at=? WHERE id=?",
                      (int(done), now if done else None, now, topic_id))

    def topic_counts(self) -> dict[str, tuple[int, int]]:
        """subject_id -> (biten konu, toplam konu)."""
        with self._s() as c:
            rows = c.execute("SELECT subject_id, SUM(done) d, COUNT(*) n FROM topics GROUP BY subject_id")
            return {r["subject_id"]: (int(r["d"] or 0), r["n"]) for r in rows}

    def planned_topic_ids(self) -> set[str]:
        """Şu an bir görevde bekleyen (yapılmamış) konular; 'sıradaki konu' önerisinde tekrar çıkmasın."""
        with self._s() as c:
            rows = c.execute("SELECT DISTINCT topic_id FROM tasks WHERE status='todo' AND topic_id IS NOT NULL")
            return {r["topic_id"] for r in rows}

    # ------------------------------------------------------ haftalık şablon
    def get_template(self) -> dict[int, list[TemplateEntry]]:
        """Gün (0=Pzt) -> o günün ders havuzu. Arşivdeki dersler gösterilmez."""
        out: dict[int, list[TemplateEntry]] = {i: [] for i in range(7)}
        with self._s() as c:
            rows = c.execute(
                """SELECT t.* FROM weekly_template t JOIN subjects s ON s.id=t.subject_id
                   WHERE s.archived=0 ORDER BY t.weekday, s.sort_order, s.name""")
            for r in rows:
                out[r["weekday"]].append(TemplateEntry.from_row(r))
        return out

    def template_for(self, d: date) -> list[TemplateEntry]:
        return self.get_template()[d.weekday()]

    def set_template_day(self, weekday: int, entries: dict[str, int]) -> None:
        """Bir günün şablonunu tümüyle değiştirir. entries: subject_id -> dakika."""
        if not 0 <= weekday <= 6:
            raise ValueError("Geçersiz gün.")
        now = db.now_iso()
        with self._s() as c:  # tek transaction: ya hep ya hiç
            c.execute("DELETE FROM weekly_template WHERE weekday=?", (weekday,))
            for sid, minutes in entries.items():
                c.execute(
                    "INSERT INTO weekly_template (id,weekday,subject_id,minutes,updated_at) VALUES (?,?,?,?,?)",
                    (db.new_id(), weekday, sid, max(int(minutes), 1), now))

    def template_week_minutes(self) -> dict[str, int]:
        """Şablondan türeyen haftalık hedef: subject_id -> haftalık toplam dakika."""
        with self._s() as c:
            rows = c.execute(
                """SELECT t.subject_id, SUM(t.minutes) m FROM weekly_template t
                   JOIN subjects s ON s.id=t.subject_id WHERE s.archived=0 GROUP BY t.subject_id""")
            return {r["subject_id"]: r["m"] for r in rows}

    # ------------------------------------------------------ haftalık hedefler
    # Şablondan bağımsız, haftaya özel elle hedef (geri uyumluluk). Varsa şablonu ezer.
    def get_goals(self, ws: date) -> dict[str, int]:
        with self._s() as c:
            rows = c.execute("SELECT subject_id, target_minutes FROM weekly_goals WHERE week_start=?",
                             (ws.isoformat(),))
            return {r["subject_id"]: r["target_minutes"] for r in rows}

    def set_goal(self, ws: date, subject_id: str, minutes: int) -> None:
        with self._s() as c:
            if minutes <= 0:
                c.execute("DELETE FROM weekly_goals WHERE week_start=? AND subject_id=?",
                          (ws.isoformat(), subject_id))
                return
            c.execute(
                """INSERT INTO weekly_goals (id,week_start,subject_id,target_minutes,updated_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(week_start,subject_id)
                   DO UPDATE SET target_minutes=excluded.target_minutes, updated_at=excluded.updated_at""",
                (db.new_id(), ws.isoformat(), subject_id, minutes, db.now_iso()),
            )

    # --------------------------------------------------------------- görevler
    @staticmethod
    def _insert_task(c: sqlite3.Connection, *, subject_id: str, title: str, task_type: str,
                     planned_minutes: int, week: date | None, planned_date: date | None,
                     topic_id: str | None) -> str:
        title = title.strip()
        if not title:
            raise ValueError("Görev başlığı boş olamaz.")
        if planned_date is not None:
            week = week_start(planned_date)
        if week is None:
            raise ValueError("Hafta veya tarih verilmeli.")
        tid, now = db.new_id(), db.now_iso()
        c.execute(
            """INSERT INTO tasks (id,week_start,planned_date,subject_id,title,task_type,
               planned_minutes,topic_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (tid, week.isoformat(), planned_date.isoformat() if planned_date else None,
             subject_id, title, task_type, planned_minutes, topic_id, now, now),
        )
        return tid

    @staticmethod
    def _complete(c: sqlite3.Connection, task_id: str, minutes: int, log_date: date, note: str,
                  questions: int, topic_done: bool) -> None:
        t = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if t is None:
            raise KeyError(task_id)
        now = db.now_iso()
        marked = 0
        if topic_done and t["topic_id"]:
            was = c.execute("SELECT done FROM topics WHERE id=?", (t["topic_id"],)).fetchone()
            if was is not None and not was["done"]:
                c.execute("UPDATE topics SET done=1, done_at=?, updated_at=? WHERE id=?",
                          (now, now, t["topic_id"]))
                marked = 1  # geri alınırsa konu da açılsın (daha önce bitmişse dokunma)
        c.execute("UPDATE tasks SET status='done', completed_at=?, topic_marked=?, updated_at=? WHERE id=?",
                  (now, marked, now, task_id))
        if minutes > 0:
            c.execute(
                """INSERT INTO study_logs (id,log_date,subject_id,minutes,study_type,note,task_id,
                   question_count,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (db.new_id(), log_date.isoformat(), t["subject_id"], minutes,
                 t["task_type"], note or t["title"], task_id, max(questions, 0), now, now),
            )

    def add_task(self, *, subject_id: str, title: str, task_type: str, planned_minutes: int,
                 week: date | None = None, planned_date: date | None = None,
                 topic_id: str | None = None) -> str:
        with self._s() as c:
            return self._insert_task(c, subject_id=subject_id, title=title, task_type=task_type,
                                     planned_minutes=planned_minutes, week=week,
                                     planned_date=planned_date, topic_id=topic_id)

    def add_done_task(self, *, subject_id: str, title: str, task_type: str, minutes: int,
                      day: date, topic_id: str | None = None, questions: int = 0,
                      topic_done: bool = False) -> str:
        """Plan dışı (ekstra) çalışma: görev + çalışma kaydı tek transaction'da, tamamlanmış olarak."""
        with self._s() as c:
            tid = self._insert_task(c, subject_id=subject_id, title=title, task_type=task_type,
                                    planned_minutes=minutes, week=None, planned_date=day,
                                    topic_id=topic_id)
            self._complete(c, tid, minutes, day, "", questions, topic_done)
            return tid

    def update_task(self, task_id: str, *, title: str, subject_id: str, task_type: str,
                    planned_minutes: int, topic_id: str | None = None) -> None:
        if not title.strip():
            raise ValueError("Görev başlığı boş olamaz.")
        with self._s() as c:
            c.execute(
                """UPDATE tasks SET title=?, subject_id=?, task_type=?, planned_minutes=?, topic_id=?,
                   updated_at=? WHERE id=?""",
                (title.strip(), subject_id, task_type, planned_minutes, topic_id, db.now_iso(), task_id),
            )

    def swap_task(self, task_id: str, subject_id: str, topic_id: str | None = None,
                  title: str | None = None) -> None:
        """Bugünün planını anlık esnetir: görevi başka bir derse (ve konuya) çevirir.

        Başlangıçta planlanan ders `original_subject_id` olarak saklanır (rapor/rozet için);
        eski derse geri dönülürse iz silinir. Çalışma kaydı yeni dersin adına yazılır.
        """
        with self._s() as c:
            t = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if t is None:
                raise KeyError(task_id)
            if t["status"] == "done":
                raise ValueError("Tamamlanmış görev değiştirilemez; önce geri al.")
            origin = t["original_subject_id"] or t["subject_id"]
            if not title or not title.strip():
                if topic_id:
                    title = c.execute("SELECT name FROM topics WHERE id=?", (topic_id,)).fetchone()["name"]
                else:
                    title = c.execute("SELECT name FROM subjects WHERE id=?", (subject_id,)).fetchone()["name"]
            c.execute(
                """UPDATE tasks SET subject_id=?, topic_id=?, title=?, original_subject_id=?, updated_at=?
                   WHERE id=?""",
                (subject_id, topic_id, title.strip(), None if subject_id == origin else origin,
                 db.now_iso(), task_id))

    def delete_task(self, task_id: str) -> None:
        with self._s() as c:  # bağlı çalışma kayıtları korunur (task_id NULL olur)
            c.execute("DELETE FROM tasks WHERE id=?", (task_id,))

    def get_task(self, task_id: str) -> Task | None:
        with self._s() as c:
            r = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            return Task.from_row(r) if r else None

    def _tasks(self, where: str, params: tuple) -> list[Task]:
        with self._s() as c:
            rows = c.execute(
                f"SELECT * FROM tasks WHERE {where} ORDER BY (status='done'), created_at", params)
            return [Task.from_row(r) for r in rows]

    def list_tasks_for_date(self, d: date) -> list[Task]:
        return self._tasks("planned_date=?", (d.isoformat(),))

    def list_tasks_between(self, start: date, end: date) -> list[Task]:
        return self._tasks("planned_date BETWEEN ? AND ?", (start.isoformat(), end.isoformat()))

    def list_tasks_for_week(self, ws: date) -> list[Task]:
        return self._tasks("week_start=?", (ws.isoformat(),))

    def list_pool(self, ws: date) -> list[Task]:
        """Güne atanmamış, tamamlanmamış görevler (eski sürümden kalan haftalık havuz)."""
        return self._tasks("week_start=? AND planned_date IS NULL AND status='todo'", (ws.isoformat(),))

    def list_backlog(self, today: date) -> list[Task]:
        """Geçmişte kalmış tamamlanmamış görevler: geçmiş günlerdekiler + geçmiş haftaların havuzu."""
        return self._tasks(
            """status='todo' AND ((planned_date IS NOT NULL AND planned_date < ?)
               OR (planned_date IS NULL AND week_start < ?))""",
            (today.isoformat(), week_start(today).isoformat()),
        )

    def create_draft_from_template(self, d: date) -> int:
        """Günün şablon derslerinden, henüz görevi olmayanlar için konusuz taslak görev açar.

        Dersi daha önce açılmış (ya da başka derse çevrilmiş) olanlar atlanır; tekrar çalıştırılabilir.
        """
        created = 0
        with self._s() as c:
            have: set[str] = set()
            for r in c.execute("SELECT subject_id, original_subject_id FROM tasks WHERE planned_date=?",
                               (d.isoformat(),)):
                have.add(r["subject_id"])
                if r["original_subject_id"]:
                    have.add(r["original_subject_id"])
            rows = c.execute(
                """SELECT t.subject_id, t.minutes, s.name FROM weekly_template t
                   JOIN subjects s ON s.id=t.subject_id
                   WHERE t.weekday=? AND s.archived=0 ORDER BY s.sort_order, s.name""", (d.weekday(),)).fetchall()
            for r in rows:
                if r["subject_id"] in have:
                    continue
                self._insert_task(c, subject_id=r["subject_id"], title=r["name"], task_type="Konu çalışması",
                                  planned_minutes=r["minutes"], week=None, planned_date=d, topic_id=None)
                created += 1
        return created

    def schedule_task(self, task_id: str, d: date | None, *, carried: bool = False) -> None:
        """Görevi bir güne ata (d=None: havuza geri koy). carried=True: aktarma sayacını artırır."""
        with self._s() as c:
            cur = c.execute("SELECT week_start FROM tasks WHERE id=?", (task_id,)).fetchone()
            if cur is None:
                raise KeyError(task_id)
            ws = week_start(d).isoformat() if d else cur["week_start"]
            c.execute(
                """UPDATE tasks SET planned_date=?, week_start=?, carry_count=carry_count+?, updated_at=?
                   WHERE id=?""",
                (d.isoformat() if d else None, ws, int(carried), db.now_iso(), task_id),
            )

    def carry_unfinished(self, from_day: date, to_day: date) -> int:
        """Günün bitmeyen görevlerinin hepsini tek dokunuşla başka güne aktarır (ertelenme sayacı +1)."""
        with self._s() as c:
            cur = c.execute(
                """UPDATE tasks SET planned_date=?, week_start=?, carry_count=carry_count+1, updated_at=?
                   WHERE planned_date=? AND status='todo'""",
                (to_day.isoformat(), week_start(to_day).isoformat(), db.now_iso(), from_day.isoformat()))
            return cur.rowcount

    def move_to_next_week(self, task_id: str) -> None:
        with self._s() as c:
            c.execute(
                """UPDATE tasks SET planned_date=NULL, week_start=date(week_start,'+7 days'),
                   carry_count=carry_count+1, updated_at=? WHERE id=?""",
                (db.now_iso(), task_id),
            )

    def complete_task(self, task_id: str, minutes: int, log_date: date, note: str = "",
                      questions: int = 0, topic_done: bool = False) -> None:
        """Görevi tamamlar; minutes>0 ise aynı transaction'da çalışma kaydı oluşturur.

        topic_done=True ve görevin konusu varsa konu 'bitti' işaretlenir (müfredat ilerlemesi).
        """
        with self._s() as c:
            self._complete(c, task_id, minutes, log_date, note, questions, topic_done)

    def reopen_task(self, task_id: str) -> None:
        with self._s() as c:
            t = c.execute("SELECT topic_id, topic_marked FROM tasks WHERE id=?", (task_id,)).fetchone()
            if t is None:
                raise KeyError(task_id)
            c.execute("DELETE FROM study_logs WHERE task_id=?", (task_id,))
            if t["topic_marked"] and t["topic_id"]:  # konuyu bu görev bitirdiyse geri aç
                c.execute("UPDATE topics SET done=0, done_at=NULL, updated_at=? WHERE id=?",
                          (db.now_iso(), t["topic_id"]))
            c.execute("UPDATE tasks SET status='todo', completed_at=NULL, topic_marked=0, updated_at=? WHERE id=?",
                      (db.now_iso(), task_id))

    # ------------------------------------------------------ çalışma kayıtları
    def add_log(self, *, log_date: date, subject_id: str, minutes: int, study_type: str,
                note: str = "", question_count: int = 0) -> str:
        if minutes <= 0:
            raise ValueError("Süre 0'dan büyük olmalı.")
        lid, now = db.new_id(), db.now_iso()
        with self._s() as c:
            c.execute(
                """INSERT INTO study_logs (id,log_date,subject_id,minutes,study_type,note,question_count,
                   created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                (lid, log_date.isoformat(), subject_id, minutes, study_type, note.strip(),
                 max(question_count, 0), now, now),
            )
        return lid

    def delete_log(self, log_id: str) -> None:
        with self._s() as c:
            c.execute("DELETE FROM study_logs WHERE id=?", (log_id,))

    def list_logs(self, start: date, end: date) -> list[StudyLog]:
        with self._s() as c:
            rows = c.execute(
                "SELECT * FROM study_logs WHERE log_date BETWEEN ? AND ? ORDER BY log_date DESC, created_at DESC",
                (start.isoformat(), end.isoformat()),
            )
            return [StudyLog.from_row(r) for r in rows]

    def list_logs_for_week(self, ws: date) -> list[StudyLog]:
        return self.list_logs(ws, ws + timedelta(days=6))
