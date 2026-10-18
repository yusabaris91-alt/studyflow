"""StudyFlow – YKS çalışma planlayıcı. Çalıştır: streamlit run app.py"""
from __future__ import annotations

from datetime import date

import streamlit as st

from studyflow import db
from studyflow.config import BACKUP_DIR, DB_PATH, KEEP_AUTO_BACKUPS
from studyflow.repository import Repository
from studyflow.ui import common, plan, reports, settings, template, today, topics

st.set_page_config(page_title="StudyFlow", page_icon="📚", layout="centered",
                   initial_sidebar_state="collapsed")


@st.cache_resource
def get_repo() -> Repository:
    db.initialize(DB_PATH)  # şema yoksa oluşturur, eskiyse göç ettirir
    return Repository(DB_PATH)


@st.cache_resource
def ensure_daily_backup(day: str) -> None:
    """Gün başına bir kez (sunucu açık kalsa bile) otomatik yedek."""
    db.daily_backup(DB_PATH, BACKUP_DIR, KEEP_AUTO_BACKUPS)


# Akış: Şablon (bir kez) → Yarın (akşamdan) → Bugün (icra) → Rapor.
PAGES = {
    common.PAGE_TODAY: today.render,
    common.PAGE_PLAN: plan.render,
    common.PAGE_TEMPLATE: template.render,
    common.PAGE_TOPICS: topics.render,
    common.PAGE_REPORTS: reports.render,
    common.PAGE_SETTINGS: settings.render,
}

repo = get_repo()
ensure_daily_backup(date.today().isoformat())
common.inject_css()

st.title("📚 StudyFlow")
# Sekme yerine gezinme çubuğu: dar ekranda satıra sarar, seçim rerun'larda korunur ve
# yalnızca seçili sayfa çizilir (telefonda daha hızlı).
st.session_state.setdefault("page", common.PAGE_TODAY)
page = st.pills("Sayfa", list(PAGES), required=True, key="page", label_visibility="collapsed")
PAGES[page](repo)
