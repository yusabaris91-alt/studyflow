"""2. Adım – Akşamdan "Yarının Planı": şablondaki dersler listelenir, konular netleştirilir."""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from ..repository import Repository
from .cards import add_task_form, plan_block
from .common import DAYS, DAYS_FULL, fmt_date, fmt_minutes, subject_names, subject_picker


def _day_label(today: date, d: date) -> str:
    return "Yarın" if d == today + timedelta(days=1) else f"{DAYS[d.weekday()]} {d.day}"


def upcoming_preview(repo: Repository, today: date, days: int = 3) -> None:
    """Salt okunur önizleme: sonraki günlerin planı; planlanmamışsa şablondaki taslak dersler."""
    names = subject_names(repo)
    template = repo.get_template()
    tasks = repo.list_tasks_between(today + timedelta(days=1), today + timedelta(days=days))
    for i in range(1, days + 1):
        d = today + timedelta(days=i)
        day_tasks = [t for t in tasks if t.planned_date == d]
        st.markdown(f"**{'Yarın' if i == 1 else DAYS_FULL[d.weekday()]}** · {fmt_date(d)}")
        if day_tasks:
            for t in day_tasks:
                mins = f" · {fmt_minutes(t.planned_minutes)}" if t.planned_minutes else ""
                st.markdown(f"- {names.get(t.subject_id, '?')}: {t.title}{mins}")
        elif template[d.weekday()]:
            st.caption("Taslak (şablon): " + ", ".join(names.get(e.subject_id, "?") for e in template[d.weekday()]))
        else:
            st.caption("Plan yok")


def render(repo: Repository) -> None:
    today = date.today()
    options = [today + timedelta(days=i) for i in range(1, 8)]
    if st.session_state.get("plan_day") not in options:  # gece yarısı geçtiyse / ilk açılış
        st.session_state["plan_day"] = options[0]
    day: date = st.pills("Gün", options, required=True, key="plan_day",
                         format_func=lambda d: _day_label(today, d), label_visibility="collapsed")

    st.subheader(f"🌙 {DAYS_FULL[day.weekday()]} planı · {fmt_date(day)}")
    template = repo.template_for(day)
    names = subject_names(repo)
    active = repo.list_subjects()
    subjects = {s.id: s for s in active}
    tasks = repo.list_tasks_for_date(day)

    if not any(repo.get_template().values()):
        st.info("Henüz haftalık şablon yok; yine de aşağıdan ders ekleyerek plan yapabilirsin. "
                "Şablonu 📅 Şablon sayfasından bir kez oluştur.")
    elif not template:
        st.caption("Şablonda bu gün için ders yok.")

    # Dersler: önce şablondakiler, sonra şablon dışı (göreve sahip) olanlar.
    minutes = {e.subject_id: e.minutes for e in template}
    order = [e.subject_id for e in template]
    for t in tasks:
        if t.subject_id not in order:
            order.append(t.subject_id)

    missing = [sid for sid in minutes if not any(t.subject_id == sid or t.original_subject_id == sid for t in tasks)]
    if missing:
        if st.button(f"📋 {len(missing)} ders için taslak satır aç", key="plan_drafts", width="stretch",
                     help="Konu seçmeden, şablondaki dersleri güne ekler; konuyu sonra netleştirirsin."):
            repo.create_draft_from_template(day)
            st.rerun()

    planned_topics = repo.planned_topic_ids()
    for sid in order:
        subject = subjects.get(sid)
        if subject is None:  # arşivlenmiş ders: görevi varsa yine de göster
            continue
        plan_block(repo, day, subject, [t for t in tasks if t.subject_id == sid], minutes.get(sid, 0),
                   planned_topics)

    total = sum(t.planned_minutes for t in tasks)
    if tasks:
        st.caption(f"Toplam plan: **{fmt_minutes(total)}** · {len(tasks)} görev")

    with st.expander("➕ Şablon dışı ders ekle"):
        if not active:
            st.warning("Önce Ayar sayfasından bir ders ekle.")
        else:
            sid = subject_picker("Ders", active, "plan_extra_subj")
            add_task_form(repo, day, subjects[sid], f"plan-extra-{day.isoformat()}-{sid}")
