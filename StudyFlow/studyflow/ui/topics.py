"""YKS müfredatı: konuları işaretle, ilerlemeyi gör, konu ekle / sil."""
from __future__ import annotations

import streamlit as st

from ..repository import Repository
from ..services import build_curriculum_progress
from .common import OK_COLOR, PALETTE, bar_row, show_html


def _toggle(repo: Repository, topic_id: str, key: str) -> None:
    repo.set_topic_done(topic_id, bool(st.session_state[key]))


def render(repo: Repository) -> None:
    st.subheader("📚 Konular")
    progress = build_curriculum_progress(repo)
    if not progress:
        st.info("Müfredat boş. Ayar sayfasından ders ekleyip konu ekleyebilirsin.")
        return

    by_id = {p.subject_id: p for p in progress}
    ids = list(by_id)
    if st.session_state.get("topics_subject") not in by_id:
        st.session_state["topics_subject"] = ids[0]
    sid = st.selectbox("Ders", ids, key="topics_subject",
                       format_func=lambda i: f"{by_id[i].name} · {by_id[i].done}/{by_id[i].total}")
    p = by_id[sid]
    show_html(bar_row(p.name, f"{p.done}/{p.total} konu · %{p.pct:.0f}", p.pct,
                      OK_COLOR if p.pct >= 100 else PALETTE[0]))

    topics = repo.list_topics(sid)
    only_open = st.toggle("Yalnızca bitmeyenler", key="topics_only_open")
    for t in topics:
        if only_open and t.done:
            continue
        key = f"topic-{t.id}"
        st.checkbox(t.name, value=t.done, key=key, on_change=_toggle, args=(repo, t.id, key))

    with st.expander("➕ Konu ekle / sil"):
        with st.form(f"add_topic-{sid}", clear_on_submit=True):
            name = st.text_input("Yeni konu adı", key=f"new_topic-{sid}")
            if st.form_submit_button("Konu ekle", width="stretch"):
                try:
                    repo.add_topic(sid, name)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        if topics:
            victim = st.selectbox("Silinecek konu", [t.id for t in topics], key=f"del_topic_pick-{sid}",
                                  format_func={t.id: t.name for t in topics}.get)
            with st.popover("🗑 Bu konuyu sil", width="stretch"):
                st.write("Konu müfredattan kalkar; geçmiş çalışma kayıtların korunur.")
                if st.button("Evet, sil", key=f"del_topic-{sid}", width="stretch"):
                    repo.delete_topic(victim)
                    st.rerun()
