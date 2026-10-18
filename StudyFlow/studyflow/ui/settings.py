"""Ayarlar: dersler, yedekleme, geri yükleme."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from .. import db
from ..config import BACKUP_DIR, DB_PATH
from ..repository import Repository


def render(repo: Repository) -> None:
    st.subheader("Dersler")
    subjects = repo.list_subjects(include_archived=True)
    for exam, title in (("TYT", "TYT"), ("AYT", "AYT"), ("", "Diğer / eski dersler")):
        group = [s for s in subjects if s.exam == exam]
        if not group:
            continue
        with st.expander(f"{title} ({sum(not s.archived for s in group)}/{len(group)} aktif)"):
            for s in group:
                with st.container(horizontal=True, vertical_alignment="center"):
                    st.markdown(s.name if not s.archived else f"~~{s.name}~~")
                    label = "Geri getir" if s.archived else "Arşivle"
                    if st.button(label, key=f"arch-{s.id}"):
                        repo.set_subject_archived(s.id, not s.archived)
                        st.rerun()
    with st.form("add_subject", clear_on_submit=True):
        name = st.text_input("Yeni ders adı")
        exam = st.pills("Sınav", ["TYT", "AYT", "Diğer"], default="Diğer", required=True, key="new_subject_exam")
        if st.form_submit_button("Ders ekle"):
            try:
                repo.add_subject(name, "" if exam == "Diğer" else exam)
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    st.caption("Dersler silinmez, arşivlenir; geçmiş kayıtların bozulmaz.")

    st.subheader("Yedekleme")
    st.caption(f"Veri: `{DB_PATH}`  \nYedekler: `{BACKUP_DIR}`  \nGünde bir otomatik yedek alınır "
               "(son 14 tutulur). Manuel ve geri-yükleme yedekleri silinmez.")
    if st.button("💾 Şimdi yedek al"):
        try:
            st.session_state["last_backup"] = str(db.create_backup(DB_PATH, BACKUP_DIR, "manual"))
            st.success("Yedek alındı ve doğrulandı.")
        except Exception as e:  # noqa: BLE001 - kullanıcıya göster
            st.error(f"Yedekleme başarısız: {e}")
    last = st.session_state.get("last_backup")
    if last:
        try:
            with open(last, "rb") as f:
                st.download_button("⬇ Bu yedeği cihazına indir", f.read(), file_name=last.split("/")[-1],
                                   mime="application/octet-stream")
        except OSError:
            pass

    backups = db.list_backups(BACKUP_DIR)
    st.markdown(f"**Mevcut yedekler ({len(backups)})**")
    if backups:
        pick = st.selectbox(
            "Geri yüklenecek yedek", backups, label_visibility="collapsed",
            format_func=lambda p: f"{p.stem.removeprefix('studyflow-')} · {p.stat().st_size // 1024} KB")
        with st.popover("♻ Bu yedeği geri yükle"):
            st.warning("Mevcut verilerin yerine bu yedek gelecek. Mevcut hâl önce otomatik olarak "
                       "'pre-restore' yedeği olarak saklanır.")
            if st.button("Evet, geri yükle", key="restore_go", type="primary"):
                try:
                    safety = db.restore_backup(pick, DB_PATH, BACKUP_DIR)
                    st.success(f"Geri yüklendi. Önceki durum: {safety.name}")
                except Exception as e:  # noqa: BLE001
                    st.error(f"Geri yükleme başarısız: {e}")
