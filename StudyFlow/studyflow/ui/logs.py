"""Çalışma günlüğü: haftanın kayıtlarını listele / sil (Rapor sayfasının altında)."""
from __future__ import annotations

from datetime import date

import streamlit as st

from ..repository import Repository
from .common import fmt_date, fmt_minutes, subject_names


def log_list(repo: Repository, ws: date) -> None:
    names = subject_names(repo)
    logs = repo.list_logs_for_week(ws)
    total_q = sum(l.question_count for l in logs)
    st.markdown(f"**Toplam: {fmt_minutes(sum(l.minutes for l in logs))}**"
                + (f" · {total_q} soru" if total_q else "") + f" · {len(logs)} kayıt")
    if not logs:
        st.caption("Bu hafta kayıt yok.")
    current = None
    for l in logs:
        if l.log_date != current:
            current = l.log_date
            st.caption(fmt_date(current))
        with st.container(border=True):
            q = f" · {l.question_count} soru" if l.question_count else ""
            st.markdown(f"**{names.get(l.subject_id, '?')}** · {fmt_minutes(l.minutes)}{q}")
            st.caption(l.study_type + (f" · {l.note}" if l.note else ""))
            with st.popover("🗑 Sil", width="stretch"):
                st.write("Bu kayıt silinsin mi?")
                if st.button("Evet, sil", key=f"dellog-{l.id}", width="stretch"):
                    repo.delete_log(l.id)
                    st.rerun()
