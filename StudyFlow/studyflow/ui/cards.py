"""Görev kartları ve formları (mobil öncelikli).

İki kullanım biçimi:
- `task_card`  : BUGÜN / icra. Tamamla · Değiştir (swap) · Yarına aktar · Düzenle.
- `plan_block` : YARIN / planlama. Dersin bloğu: görevler + tek dokunuşla "sıradaki konu" + konu seç.
"""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from ..models import Subject, Task
from ..repository import Repository
from .common import (fmt_date, fmt_minutes, is_overdue, make_title, open_topics, postpone_badge,
                     subject_picker, topic_picker, type_picker)


# ============================================================ BUGÜN: icra kartı
def task_card(repo: Repository, task: Task, names: dict[str, str], active: list[Subject],
              ctx: str, today: date, *, show_date: bool = False, default_date: date | None = None) -> None:
    """Dikey akışlı görev kartı. ctx = benzersiz widget öneki."""
    k = f"{ctx}-{task.id}"
    overdue = is_overdue(task, today)
    in_pool = task.planned_date is None and not task.done
    with st.container(border=True):
        st.markdown(f"~~{task.title}~~ ✅" if task.done else f"**{task.title}**")
        meta = f"{names.get(task.subject_id, '?')} · {task.task_type}"
        if task.planned_minutes:
            meta += f" · {fmt_minutes(task.planned_minutes)}"
        if show_date and task.planned_date:
            meta += f" · 📅 {fmt_date(task.planned_date)}"
        elif show_date and in_pool:
            meta += " · 📥 havuzda"
        st.caption(meta)
        if task.original_subject_id:  # plan esnetildi: neyin yerine ne çalışıldığı görünsün
            st.markdown(f":blue-badge[🔄 {names.get(task.original_subject_id, '?')} yerine]")
        badge = None if task.done else postpone_badge(task.carry_count)
        if badge:
            st.markdown(badge)

        if in_pool or overdue:
            _schedule_row(repo, task, k, today, carried=overdue, default_date=default_date or today)

        with st.container(horizontal=True):
            if task.done:
                if st.button("↩ Geri al", key=f"{k}-undo", width="stretch"):
                    repo.reopen_task(task.id)
                    st.rerun()
            else:
                with st.popover("✅ Tamamla", width="stretch"):
                    _complete_form(repo, task, k, today)
                with st.popover("🔄 Değiştir", width="stretch"):
                    _swap_form(repo, task, active, k)
        with st.container(horizontal=True):
            if not task.done and task.planned_date == today:
                if st.button("➡ Yarına aktar", key=f"{k}-tomorrow", width="stretch"):
                    repo.schedule_task(task.id, today + timedelta(days=1), carried=True)
                    st.rerun()
            with st.popover("⋯ Düzenle", width="stretch"):
                task_menu(repo, task, k)


def _schedule_row(repo: Repository, task: Task, k: str, today: date, *, carried: bool,
                  default_date: date) -> None:
    tomorrow = today + timedelta(days=1)
    with st.container(horizontal=True):
        if st.button("📌 Bugün", key=f"{k}-q-today", width="stretch"):
            repo.schedule_task(task.id, today, carried=carried)
            st.rerun()
        if st.button("➡ Yarın", key=f"{k}-q-tom", width="stretch"):
            repo.schedule_task(task.id, tomorrow, carried=carried)
            st.rerun()
        with st.popover("📅 Tarih", width="stretch"):
            d = st.date_input("Hangi güne?", default_date, format="DD.MM.YYYY", key=f"{k}-q-date")
            if st.button(f"{fmt_date(d)} gününe ata", key=f"{k}-q-pick", type="primary", width="stretch"):
                repo.schedule_task(task.id, d, carried=carried)
                st.rerun()


def _complete_form(repo: Repository, task: Task, k: str, today: date) -> None:
    """Saniyeler içinde kayıt: süre (önceden dolu) + soru sayısı (+ konu bitti mi)."""
    mins = st.number_input("Süre (dk)", 0, 600, task.planned_minutes, step=5, key=f"{k}-mins",
                           help="0 yazarsan sadece görev tamamlanır, süre kaydı oluşmaz.")
    questions = st.number_input("Çözülen soru (varsa)", 0, 1000, 0, step=10, key=f"{k}-qs")
    topic_done = False
    if task.topic_id:
        topic_done = st.checkbox("Konuyu bitirdim (müfredatta işaretle)", key=f"{k}-tdone")
    if st.button("Kaydet", key=f"{k}-complete", type="primary", width="stretch"):
        repo.complete_task(task.id, int(mins), today, questions=int(questions), topic_done=topic_done)
        st.toast("Kaydedildi ✅")
        st.rerun()


def _swap_form(repo: Repository, task: Task, active: list[Subject], k: str) -> None:
    """Planı anında esnet: 'AYT Fizik' yazıyordu ama 'AYT Kimya' çalışıldı → tek adımda değiştir."""
    st.caption("Bugün başka bir şey çalışmak istersen görevi o derse çevir; kayıt gerçek derse yazılır.")
    sid = subject_picker("Ders", active, f"{k}-swsub", task.subject_id)
    topic_id = topic_picker("Konu", open_topics(repo, sid, keep=task.topic_id if sid == task.subject_id else None),
                            f"{k}-swtopic-{sid}", task.topic_id if sid == task.subject_id else None)
    if st.button("Değiştir", key=f"{k}-swap", type="primary", width="stretch"):
        repo.swap_task(task.id, sid, topic_id)
        st.toast("Plan güncellendi 🔄")
        st.rerun()


def task_menu(repo: Repository, task: Task, k: str) -> None:
    """Düzenle / taşı / sil menüsü (hem Bugün hem Yarın kartlarında)."""
    with st.form(f"{k}-edit"):
        title = st.text_input("Başlık", task.title, key=f"{k}-etitle")
        topic_id = topic_picker("Konu", open_topics(repo, task.subject_id, keep=task.topic_id),
                                f"{k}-etopic", task.topic_id)
        ttype = type_picker("Tür", f"{k}-etype", task.task_type)
        mins = st.number_input("Planlanan süre (dk)", 0, 600, task.planned_minutes, step=5, key=f"{k}-emins")
        if st.form_submit_button("Değişiklikleri kaydet", width="stretch"):
            try:
                repo.update_task(task.id, title=title, subject_id=task.subject_id, task_type=ttype,
                                 planned_minutes=int(mins), topic_id=topic_id)
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    if not task.done:
        st.divider()
        target = st.date_input("Başka güne taşı", task.planned_date or date.today(),
                               format="DD.MM.YYYY", key=f"{k}-mvdate")
        if st.button("Bu güne taşı", key=f"{k}-mv", width="stretch"):
            repo.schedule_task(task.id, target, carried=bool(task.planned_date) and target > task.planned_date)
            st.rerun()
    st.divider()
    if st.button("🗑 Görevi sil", key=f"{k}-del", width="stretch"):
        repo.delete_task(task.id)
        st.rerun()


# ============================================================ YARIN: planlama bloğu
def add_task_form(repo: Repository, day: date, subject: Subject, key: str, default_minutes: int = 45) -> None:
    """Bir derse konu seçerek / serbest görev ekleme formu (form: yazarken yeniden çalışmaz)."""
    with st.form(f"{key}-form", clear_on_submit=True):
        topic_id = topic_picker("Konu", open_topics(repo, subject.id), f"{key}-topic")
        detail = st.text_input("Ayrıntı (isteğe bağlı)", placeholder="Ör. 40 soru, test 3", key=f"{key}-detail")
        ttype = type_picker("Tür", f"{key}-type")
        mins = st.number_input("Süre (dk)", 5, 600, max(default_minutes, 5), step=5, key=f"{key}-mins")
        if st.form_submit_button("Plana ekle", type="primary", width="stretch"):
            topic = repo.get_topic(topic_id) if topic_id else None
            repo.add_task(subject_id=subject.id, title=make_title(subject.name, topic.name if topic else None, detail),
                          task_type=ttype, planned_minutes=int(mins), planned_date=day, topic_id=topic_id)
            st.rerun()


def plan_block(repo: Repository, day: date, subject: Subject, tasks: list[Task], default_minutes: int,
               planned_topics: set[str]) -> None:
    """Planlama modunda bir dersin kartı: görevleri + tek dokunuşla sıradaki konu + konu seç."""
    key = f"plan-{day.isoformat()}-{subject.id}"
    with st.container(border=True):
        total = sum(t.planned_minutes for t in tasks)
        st.markdown(f"**{subject.name}**")
        info = []
        if default_minutes:
            info.append(f"şablon: {fmt_minutes(default_minutes)}")
        else:
            info.append("şablon dışı")
        if total:
            info.append(f"planlanan: {fmt_minutes(total)}")
        st.caption(" · ".join(info))
        for t in tasks:
            with st.container(horizontal=True, vertical_alignment="center"):
                line = f"{'✅ ' if t.done else '• '}{t.title}"
                if t.planned_minutes:
                    line += f" · {fmt_minutes(t.planned_minutes)}"
                st.markdown(line)
                with st.popover("✏️"):
                    task_menu(repo, t, f"{key}-{t.id}")
        nxt = next((tp for tp in open_topics(repo, subject.id) if tp.id not in planned_topics), None)
        with st.container(horizontal=True):
            if nxt is not None and st.button(f"➕ {nxt.name}", key=f"{key}-next", type="primary", width="stretch",
                                             help="Müfredattaki sıradaki konuyu bu güne ekler"):
                repo.add_task(subject_id=subject.id, title=nxt.name, task_type="Konu çalışması",
                              planned_minutes=default_minutes or 45, planned_date=day, topic_id=nxt.id)
                st.rerun()
            with st.popover("Konu seç / serbest", width="stretch"):
                add_task_form(repo, day, subject, f"{key}-add", default_minutes or 45)
