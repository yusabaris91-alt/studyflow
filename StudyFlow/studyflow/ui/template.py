"""1. Adım – Haftalık şablon (taslak plan): hangi gün hangi dersler havuzda. Saatli program DEĞİL."""
from __future__ import annotations

from datetime import date

import streamlit as st

from ..models import Subject
from ..repository import Repository
from .common import DAYS, DAYS_FULL, short_name, subject_names, fmt_minutes

_GROUPS = [("TYT", "TYT dersleri"), ("AYT", "AYT dersleri"), ("", "Diğer dersler")]


def _overview(repo: Repository, names: dict[str, str]) -> None:
    template = repo.get_template()
    today_wd = date.today().weekday()
    with st.container(border=True):
        for wd in range(7):
            entries = template[wd]
            total = sum(e.minutes for e in entries)
            subjects = ", ".join(names.get(e.subject_id, "?") for e in entries) or "—"
            mark = "**" if wd == today_wd else ""
            st.markdown(f"{mark}{DAYS[wd]}{mark} · {subjects}" + (f"  \n:gray[{fmt_minutes(total)}]" if total else ""))


def _day_editor(repo: Repository, wd: int, active: list[Subject]) -> None:
    current = {e.subject_id: e.minutes for e in repo.get_template()[wd]}
    chosen: list[str] = []
    for exam, title in _GROUPS:
        group = [s for s in active if s.exam == exam]
        if not group:
            continue
        sel = st.pills(title, [s.id for s in group], selection_mode="multi",
                       default=[s.id for s in group if s.id in current], key=f"tpl-{wd}-{exam or 'x'}",
                       format_func={s.id: short_name(s) for s in group}.get)
        chosen += sel or []

    minutes: dict[str, int] = {}
    if chosen:
        st.caption("Her ders için o günkü hedef süre (dakika). Saat belirlemene gerek yok.")
    by_id = {s.id: s for s in active}
    for sid in chosen:
        minutes[sid] = st.number_input(f"{by_id[sid].name} — hedef süre (dk)", 5, 600, current.get(sid, 60),
                                       step=15, key=f"tpl-{wd}-min-{sid}")
    if st.button(f"💾 {DAYS_FULL[wd]} şablonunu kaydet", key=f"tpl-save-{wd}", type="primary", width="stretch"):
        repo.set_template_day(wd, {sid: int(m) for sid, m in minutes.items()})
        st.toast("Şablon kaydedildi ✅")
        st.rerun()

    others = [i for i in range(7) if i != wd]
    with st.expander("Bu günü başka günlere kopyala"):
        targets = st.pills("Hedef günler", others, selection_mode="multi", format_func=DAYS.__getitem__,
                           key=f"tpl-copy-{wd}")
        if st.button("Kopyala", key=f"tpl-copy-go-{wd}", width="stretch", disabled=not targets):
            saved = {e.subject_id: e.minutes for e in repo.get_template()[wd]}
            for t in targets:
                repo.set_template_day(t, saved)
            st.toast("Kopyalandı ✅ (kayıtlı şablondan)")
            st.rerun()


def render(repo: Repository) -> None:
    active = repo.list_subjects()
    names = subject_names(repo)
    st.subheader("📅 Haftalık şablon")
    st.caption("Hangi gün hangi dersler çalışılacak — bir kez belirle. Saatli program değil; "
               "o günün ders havuzu. Konuları akşamdan 🌙 Yarın sayfasında netleştirirsin.")

    _overview(repo, names)

    st.markdown("**Günü düzenle**")
    if "tpl_day" not in st.session_state:
        st.session_state["tpl_day"] = date.today().weekday()
    wd = st.pills("Gün", list(range(7)), required=True, key="tpl_day", format_func=DAYS.__getitem__,
                  label_visibility="collapsed")
    _day_editor(repo, wd, active)

    week = repo.template_week_minutes()
    if week:
        with st.expander("🎯 Haftalık hedefler (şablondan)"):
            st.caption("Rapor sayfasındaki hedef süreler bu toplamlardan gelir.")
            for sid, m in sorted(week.items(), key=lambda kv: names.get(kv[0], "")):
                st.markdown(f"- {names.get(sid, '?')}: **{fmt_minutes(m)}**")
