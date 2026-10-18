"""3. Adım – Bugünün icrası: esnek plan, tamamlama, ekstra çalışma, kalanları yarına aktarma."""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from ..models import week_start
from ..repository import Repository
from ..services import build_coaching, build_week_report
from .cards import task_card
from .common import (PAGE_PLAN, PAGE_TEMPLATE, fmt_date, fmt_minutes, go_to, make_title, subject_names,
                     subject_picker, topic_picker, open_topics, type_picker)
from .plan import upcoming_preview


def _coach_box(repo: Repository, today: date, backlog_count: int) -> None:
    """Her çalıştırmada güncel veriyle yeniden hesaplanan kısa koçluk mesajı."""
    report = build_week_report(repo, week_start(today))
    studied_today = sum(l.minutes for l in repo.list_logs(today, today))
    c = build_coaching(report, today, backlog_count, studied_today)
    {"success": st.success, "warning": st.warning}.get(c.level, st.info)(c.text, icon=c.icon)


def _template_hint(repo: Repository, today: date) -> None:
    """Bugüne görev açılmamışsa şablondaki dersleri tek dokunuşla taslağa çevir."""
    entries = repo.template_for(today)
    if not entries:
        if not any(repo.get_template().values()):
            st.info("Henüz haftalık şablon yok. Hangi gün hangi dersleri çalışacağını bir kez belirle.")
            st.button("📅 Şablonu oluştur", key="goto_tpl", on_click=go_to, args=(PAGE_TEMPLATE,), width="stretch")
        else:
            st.info("Bugün için şablonda ders yok. Aşağıdan ekstra çalışma ekleyebilirsin.")
        return
    names = subject_names(repo)
    st.info("Bugünün şablonu: **" + ", ".join(names.get(e.subject_id, "?") for e in entries) + "**")
    if st.button("📋 Bugünün taslağını hazırla", key="draft_today", type="primary", width="stretch"):
        repo.create_draft_from_template(today)
        st.rerun()


def _extra_form(repo: Repository, today: date) -> None:
    """Plan dışı ekstra çalışma: ders → (konu) → tür/süre/soru → tek dokunuşla kayıt."""
    active = repo.list_subjects()
    if not active:
        st.warning("Önce Ayar sayfasından bir ders ekle.")
        return
    subj_id = subject_picker("Ders", active, "extra_subj")
    subject = next(s for s in active if s.id == subj_id)
    with st.form(f"extra-form-{subj_id}", clear_on_submit=True):
        topic_id = topic_picker("Konu (isteğe bağlı)", open_topics(repo, subj_id), f"extra-topic-{subj_id}")
        detail = st.text_input("Ayrıntı (isteğe bağlı)", placeholder="Ör. 3 deneme paragraf", key=f"extra-detail-{subj_id}")
        ttype = type_picker("Tür", f"extra-type-{subj_id}", "Soru çözümü")
        mins = st.number_input("Süre (dk)", 5, 600, 30, step=5, key=f"extra-mins-{subj_id}")
        questions = st.number_input("Çözülen soru (varsa)", 0, 1000, 0, step=10, key=f"extra-qs-{subj_id}")
        topic_done = st.checkbox("Konuyu bitirdim", key=f"extra-tdone-{subj_id}")
        if st.form_submit_button("✅ Yaptım, kaydet", type="primary", width="stretch"):
            topic = repo.get_topic(topic_id) if topic_id else None
            repo.add_done_task(subject_id=subj_id, title=make_title(subject.name, topic.name if topic else None, detail),
                               task_type=ttype, minutes=int(mins), day=today, topic_id=topic_id,
                               questions=int(questions), topic_done=topic_done and topic_id is not None)
            st.toast("Kaydedildi ✅")
            st.rerun()


def render(repo: Repository) -> None:
    today = date.today()
    backlog = repo.list_backlog(today)
    _coach_box(repo, today, len(backlog))

    names = subject_names(repo)
    active = repo.list_subjects()

    # ---- bekleyen (geçmişten kalan) görevler: asla kaybolmaz
    if backlog:
        with st.expander(f"⏳ Bekleyen görevler ({len(backlog)})", expanded=True):
            for t in backlog:
                task_card(repo, t, names, active, "backlog", today, show_date=True, default_date=today)

    # ---- bugünün planı
    tasks = repo.list_tasks_for_date(today)
    studied = sum(l.minutes for l in repo.list_logs(today, today))
    done = sum(t.done for t in tasks)
    st.subheader(f"☀️ Bugün · {fmt_date(today)}")
    if tasks:
        planned = sum(t.planned_minutes for t in tasks)
        st.progress(done / len(tasks), text=f"{done}/{len(tasks)} görev · planlanan {fmt_minutes(planned)}")
    st.caption(f"Bugün çalışılan: **{fmt_minutes(studied)}**")
    if not tasks:
        _template_hint(repo, today)
    for t in tasks:
        task_card(repo, t, names, active, "day", today)

    left = [t for t in tasks if not t.done]
    if left:
        if st.button(f"➡ Kalan {len(left)} görevi yarına aktar", key="carry_all", width="stretch"):
            repo.carry_unfinished(today, today + timedelta(days=1))
            st.toast("Yarına aktarıldı")
            st.rerun()

    # ---- eski sürümden kalan haftalık havuz (varsa)
    pool = repo.list_pool(week_start(today))
    if pool:
        with st.expander(f"📥 Güne atanmamış görevler ({len(pool)})"):
            for t in pool:
                task_card(repo, t, names, active, "pool", today, default_date=today)

    # ---- plan dışı ekstra
    with st.expander("➕ Plan dışı / ekstra çalışma"):
        _extra_form(repo, today)

    # ---- önü görme: yarın ve sonraki günler (kapalı, tek dokunuşla açılır)
    with st.expander("👀 Yarın ve sonraki günler"):
        upcoming_preview(repo, today, days=3)
        st.button("🌙 Yarının planını düzenle", key="goto_plan", on_click=go_to, args=(PAGE_PLAN,), width="stretch")
