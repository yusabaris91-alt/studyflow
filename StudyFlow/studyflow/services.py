"""İş mantığı: UI'dan bağımsız, test edilebilir hesaplamalar."""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from .formatting import fmt_minutes
from .repository import Repository


@dataclass
class SubjectProgress:
    subject_id: str
    name: str
    goal_minutes: int
    actual_minutes: int
    questions: int = 0

    @property
    def goal_pct(self) -> float | None:
        return self.actual_minutes / self.goal_minutes * 100 if self.goal_minutes else None


@dataclass
class WeekReport:
    week_start: date
    total_minutes: int = 0
    total_goal_minutes: int = 0
    total_questions: int = 0
    tasks_total: int = 0
    tasks_done: int = 0
    subjects: list[SubjectProgress] = field(default_factory=list)
    by_type: dict[str, int] = field(default_factory=dict)
    by_day: dict[date, int] = field(default_factory=dict)

    @property
    def goal_pct(self) -> float | None:
        return self.total_minutes / self.total_goal_minutes * 100 if self.total_goal_minutes else None

    @property
    def task_pct(self) -> float | None:
        return self.tasks_done / self.tasks_total * 100 if self.tasks_total else None


def weekly_targets(repo: Repository, ws: date) -> dict[str, int]:
    """Haftanın ders bazlı hedef süresi: şablondaki günlük süreler toplamı; haftaya özel elle
    girilmiş hedef (varsa) şablonu ezer."""
    targets = dict(repo.template_week_minutes())
    targets.update(repo.get_goals(ws))
    return targets


def build_week_report(repo: Repository, ws: date) -> WeekReport:
    names = {s.id: s.name for s in repo.list_subjects(include_archived=True)}
    goals = weekly_targets(repo, ws)
    logs = repo.list_logs_for_week(ws)
    tasks = repo.list_tasks_for_week(ws)

    actual: dict[str, int] = defaultdict(int)
    questions: dict[str, int] = defaultdict(int)
    by_type: dict[str, int] = defaultdict(int)
    by_day = {ws + timedelta(days=i): 0 for i in range(7)}
    for lg in logs:
        actual[lg.subject_id] += lg.minutes
        questions[lg.subject_id] += lg.question_count
        by_type[lg.study_type] += lg.minutes
        by_day[lg.log_date] += lg.minutes

    rows = [
        SubjectProgress(sid, names.get(sid, "?"), goals.get(sid, 0), actual.get(sid, 0),
                        questions.get(sid, 0))
        for sid in set(goals) | set(actual)
    ]
    rows.sort(key=lambda r: (-r.actual_minutes, r.name))
    return WeekReport(
        week_start=ws,
        total_minutes=sum(actual.values()),
        total_goal_minutes=sum(goals.values()),
        total_questions=sum(questions.values()),
        tasks_total=len(tasks),
        tasks_done=sum(t.done for t in tasks),
        subjects=rows,
        by_type=dict(by_type),
        by_day=by_day,
    )


# ------------------------------------------------------- müfredat ilerlemesi
@dataclass(frozen=True)
class CurriculumProgress:
    subject_id: str
    name: str
    exam: str
    done: int
    total: int

    @property
    def pct(self) -> float:
        return self.done / self.total * 100 if self.total else 0.0


def build_curriculum_progress(repo: Repository) -> list[CurriculumProgress]:
    """Her aktif dersin biten/toplam konu oranı (müfredatı olmayan dersler listelenmez)."""
    counts = repo.topic_counts()
    return [
        CurriculumProgress(s.id, s.name, s.exam, *counts[s.id])
        for s in repo.list_subjects() if counts.get(s.id, (0, 0))[1]
    ]


# ------------------------------------------------------------ koçluk önerisi
@dataclass(frozen=True)
class Coaching:
    level: str  # 'success' | 'info' | 'warning'
    icon: str
    text: str  # markdown, en fazla 3 kısa satır


def build_coaching(report: WeekReport, today: date, backlog_count: int = 0,
                   studied_today: int = 0) -> Coaching:
    """Haftalık hedef ile gerçekleşeni, haftanın ilerleyişine göre yorumlayan kısa mesaj.

    Saf fonksiyondur (DB'ye dokunmaz); her açılışta güncel veriyle yeniden hesaplanır.
    """
    total, goal = report.total_minutes, report.total_goal_minutes
    day_no = min(max((today - report.week_start).days + 1, 1), 7)
    days_left = 8 - day_no  # bugün dahil

    extras: list[str] = []
    if studied_today == 0 and total < goal:
        extras.append("Bugün henüz kayıt yok. 25 dakikalık küçük bir başlangıç ivme verir.")
    elif studied_today > 0:
        extras.append(f"Bugün **{fmt_minutes(studied_today)}** çalıştın, böyle devam.")
    if backlog_count:
        extras.append(f"Seni bekleyen **{backlog_count}** görev var; birini bugüne alabilirsin.")

    if goal == 0:
        if total:
            head = (f"Bu hafta şimdiye kadar **{fmt_minutes(total)}** çalıştın. "
                    "Şablon sekmesinde derslere süre verirsen hedefe göre ilerlemeni burada izlerim.")
        else:
            head = "Yeni bir hafta başlıyor. Şablon sekmesinde hangi gün hangi dersi çalışacağını belirle; hedeflerin otomatik oluşur."
        return Coaching("info", "🗓️", "\n\n".join([head] + extras[-1:]))

    pct = round(total / goal * 100)
    if total >= goal:
        head = (f"🎉 **Haftalık hedefini tamamladın!** ({fmt_minutes(total)} / {fmt_minutes(goal)}) "
                "Kalan zamanı tekrar ve yanlış analizine ayırabilirsin.")
        return Coaching("success", "🏆", "\n\n".join([head] + extras[:2]))

    remaining = goal - total
    per_day = math.ceil(remaining / days_left / 5) * 5  # 5 dk'ya yuvarla
    pace_to_today = goal * day_no / 7
    pace_to_yesterday = goal * (day_no - 1) / 7
    summary = f"**{fmt_minutes(total)} / {fmt_minutes(goal)}** (%{pct}) · haftanın {day_no}. günü."

    if total >= pace_to_today:
        level, icon = "success", "💪"
        head = f"{summary} Tempodasın, hedefin önündesin. Bu ritmi koru."
    elif total >= pace_to_yesterday:
        level, icon = "info", "🎯"
        gap = math.ceil((pace_to_today - total) / 5) * 5
        head = f"{summary} Hedefe yürüyorsun; bugünkü payını tamamlamak için yaklaşık **{gap} dk** yeter."
    else:
        level, icon = "warning", "⏳"
        head = (f"{summary} Biraz geridesin ama hafta bitmedi: kalan {days_left} günde "
                f"günde ~**{per_day} dk** ile yetişirsin.")

    lagging = [s for s in report.subjects if s.goal_minutes and s.actual_minutes < s.goal_minutes]
    if len(lagging) > 1 and day_no >= 3 and total > 0:  # erken günlerde gürültü olmasın
        worst = min(lagging, key=lambda s: s.actual_minutes / s.goal_minutes)
        if worst.actual_minutes / worst.goal_minutes < total / goal:
            head += f" En çok destek bekleyen ders: **{worst.name}** (%{worst.goal_pct:.0f})."
    return Coaching(level, icon, "\n\n".join([head] + extras[:2]))
