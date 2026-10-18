"""Ekranlar arası ortak yardımcılar: stil, tarih/biçim, seçiciler ve sade HTML bileşenleri."""
from __future__ import annotations

from datetime import date, timedelta
from html import escape

import streamlit as st

from ..config import STUDY_TYPES
from ..formatting import fmt_minutes  # noqa: F401  (ui modülleri buradan da alabilir)
from ..models import Subject, Task, Topic, week_start
from ..repository import Repository

# Sayfa adları (gezinme çubuğu + sayfalar arası "git" düğmeleri ortak kullanır).
PAGE_TODAY = "☀️ Bugün"
PAGE_PLAN = "🌙 Yarın"
PAGE_TEMPLATE = "📅 Şablon"
PAGE_TOPICS = "📚 Konular"
PAGE_REPORTS = "📊 Rapor"
PAGE_SETTINGS = "⚙️ Ayar"

DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
DAYS_FULL = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
PALETTE = ["#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#14b8a6",
           "#f97316", "#ec4899", "#64748b"]
OK_COLOR = "#16a34a"

# Mobil: taşmayı engelle, dokunma hedeflerini büyüt, iOS'un girişte yakınlaştırmasını önle (>=16px).
_CSS = """<style>
html, body, [data-testid="stAppViewContainer"] { overflow-x: hidden; }
.block-container { padding: .6rem .8rem 5rem; max-width: 720px; }
h1 { font-size: 1.45rem !important; padding: 0 0 .3rem !important; }
h2, h3 { font-size: 1.15rem !important; }
.stButton > button, .stDownloadButton > button,
[data-testid="stPopover"] > button { min-height: 3rem; font-size: 1rem; border-radius: 12px; }
input, textarea, [data-baseweb="select"] div { font-size: 16px !important; }
.stMarkdown, .stCaption, [data-testid="stExpander"] summary { overflow-wrap: anywhere; }
[data-testid="stExpander"] { border-radius: 12px; }
/* sade rapor bileşenleri */
.sf-stats { display: flex; flex-wrap: wrap; gap: .5rem; margin: .2rem 0 .6rem; }
.sf-stat { flex: 1 1 8rem; border: 1px solid rgba(128,128,128,.28); border-radius: 14px;
           padding: .6rem .8rem; }
.sf-stat b { display: block; font-size: 1.35rem; line-height: 1.3; }
.sf-stat span { font-size: .8rem; opacity: .65; }
.sf-row { margin: .55rem 0; }
.sf-top { display: flex; justify-content: space-between; gap: .6rem; font-size: .95rem; }
.sf-top .sf-r { opacity: .7; text-align: right; white-space: nowrap; font-size: .85rem; }
.sf-track { height: .55rem; border-radius: 99px; background: rgba(128,128,128,.2); margin-top: .3rem;
            overflow: hidden; }
.sf-fill { height: 100%; border-radius: 99px; }
.sf-donut-wrap { display: flex; flex-wrap: wrap; align-items: center; gap: 1rem; margin: .3rem 0; }
.sf-donut { position: relative; width: 150px; height: 150px; border-radius: 50%; flex: 0 0 auto;
            -webkit-mask: radial-gradient(farthest-side, transparent 58%, #000 60%);
            mask: radial-gradient(farthest-side, transparent 58%, #000 60%); }
.sf-donut-c { position: absolute; width: 150px; height: 150px; display: flex; flex-direction: column;
              align-items: center; justify-content: center; margin: 0; pointer-events: none; }
.sf-legend { flex: 1 1 10rem; font-size: .92rem; }
.sf-legend div { display: flex; justify-content: space-between; gap: .5rem; margin: .22rem 0; }
.sf-dot { display: inline-block; width: .7rem; height: .7rem; border-radius: 50%; margin-right: .45rem; }
.sf-muted { opacity: .6; font-size: .88rem; }
</style>"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ tarih / biçim
def fmt_date(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {DAYS[d.weekday()]}"


def fmt_week(ws: date) -> str:
    we = ws + timedelta(days=6)
    return f"{ws.day} {MONTHS[ws.month - 1]} – {we.day} {MONTHS[we.month - 1]} {we.year}"


def week_selector(key: str) -> date:
    """Rapor sayfasının hafta seçicisi. Pazartesi tarihini döndürür."""
    st.session_state.setdefault("sel_week", week_start(date.today()))

    def shift(days: int) -> None:
        st.session_state["sel_week"] += timedelta(days=days)

    def to_current() -> None:
        st.session_state["sel_week"] = week_start(date.today())

    with st.container(horizontal=True, vertical_alignment="center"):
        st.button("◀", key=f"{key}_prev", on_click=shift, args=(-7,), width="stretch")
        st.button("Bu hafta", key=f"{key}_now", on_click=to_current, width="stretch")
        st.button("▶", key=f"{key}_next", on_click=shift, args=(7,), width="stretch")
    ws = st.session_state["sel_week"]
    st.markdown(f"**{fmt_week(ws)}**")
    return ws


def go_to(page: str) -> None:
    """on_click callback'i: başka sayfaya geç (widget oluşturulduktan sonra güvenle çalışır)."""
    st.session_state["page"] = page


# ------------------------------------------------------------------ seçiciler
def subject_names(repo: Repository) -> dict[str, str]:
    """Arşivdekiler dahil id -> ad (eski kayıtlar gösterilebilsin diye)."""
    return {s.id: s.name for s in repo.list_subjects(include_archived=True)}


def short_name(s: Subject) -> str:
    """Sınav önekini atar ('AYT Matematik' -> 'Matematik'); grup başlığı zaten sınavı söyler."""
    return s.name.removeprefix(f"{s.exam} ") if s.exam else s.name


def subject_picker(label: str, subjects: list[Subject], key: str, current: str | None = None) -> str:
    ids = [s.id for s in subjects]
    names = {s.id: s.name for s in subjects}
    index = ids.index(current) if current in ids else 0
    return st.selectbox(label, ids, index=index, format_func=names.get, key=key)


def topic_picker(label: str, topics: list[Topic], key: str, current: str | None = None) -> str | None:
    """Konu seçici; ilk seçenek 'konu belirtme' (None)."""
    ids: list[str | None] = [None] + [t.id for t in topics]
    names = {t.id: t.name for t in topics}
    index = ids.index(current) if current in ids else 0
    return st.selectbox(label, ids, index=index, key=key,
                        format_func=lambda i: "— konu belirtmeden —" if i is None else names[i])


def open_topics(repo: Repository, subject_id: str, keep: str | None = None) -> list[Topic]:
    """Dersin bitmemiş konuları (müfredat sırasıyla); `keep` verilen konu bitmiş olsa da listede kalır."""
    return [t for t in repo.list_topics(subject_id) if not t.done or t.id == keep]


def type_picker(label: str, key: str, current: str | None = None) -> str:
    index = STUDY_TYPES.index(current) if current in STUDY_TYPES else 0
    return st.selectbox(label, STUDY_TYPES, index=index, key=key)


def make_title(subject_name: str, topic_name: str | None, detail: str = "") -> str:
    detail = detail.strip()
    if topic_name and detail:
        return f"{topic_name} – {detail}"
    return topic_name or detail or f"{subject_name} çalışması"


def postpone_badge(count: int) -> str | None:
    """Sade rozet: 1 kez = nötr gri, 2+ = turuncu uyarı. Hiç ertelenmediyse rozet yok."""
    if count <= 0:
        return None
    if count == 1:
        return ":gray-badge[↪ 1 kez ertelendi]"
    return f":orange-badge[⚠️ {count} kez ertelendi]"


def is_overdue(task: Task, today: date) -> bool:
    if task.done:
        return False
    if task.planned_date is not None:
        return task.planned_date < today
    return task.week_start < week_start(today)


# ------------------------------------------------------------------ sade HTML bileşenleri
def esc(text: object) -> str:
    return escape(str(text), quote=True)


def stat_tiles(items: list[tuple[str, str]]) -> None:
    """(değer, etiket) çiftlerinden sarılabilen özet kutucukları."""
    html = "".join(f'<div class="sf-stat"><b>{esc(v)}</b><span>{esc(lbl)}</span></div>' for v, lbl in items)
    st.markdown(f'<div class="sf-stats">{html}</div>', unsafe_allow_html=True)


def bar_row(label: str, right: str, pct: float | None, color: str | None = None) -> str:
    """Etiket + sağ metin + ince ilerleme çubuğu (HTML). pct=None: çubuk boş."""
    p = 0 if pct is None else max(0.0, min(pct, 100.0))
    if color is None:
        color = OK_COLOR if pct is not None and pct >= 100 else PALETTE[0]
    return (f'<div class="sf-row"><div class="sf-top"><span>{esc(label)}</span>'
            f'<span class="sf-r">{esc(right)}</span></div>'
            f'<div class="sf-track"><div class="sf-fill" style="width:{p:.1f}%;background:{color}"></div></div></div>')


def show_html(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def donut(items: list[tuple[str, int]], center_top: str, center_bottom: str) -> None:
    """Pasta (halka) grafiği + açıklama listesi. items: (ad, dakika), sıfırlar atlanır."""
    items = [(n, m) for n, m in items if m > 0]
    total = sum(m for _, m in items)
    if not total:
        return
    stops, acc, legend = [], 0.0, []
    for i, (name, m) in enumerate(items):
        color = PALETTE[i % len(PALETTE)]
        share = m / total * 100
        stops.append(f"{color} {acc:.2f}% {acc + share:.2f}%")
        acc += share
        legend.append(f'<div><span><i class="sf-dot" style="background:{color}"></i>{esc(name)}</span>'
                      f'<span class="sf-muted">{esc(fmt_minutes(m))} · %{share:.0f}</span></div>')
    show_html(
        '<div class="sf-donut-wrap"><div style="position:relative;width:150px;height:150px">'
        f'<div class="sf-donut" style="background:conic-gradient({", ".join(stops)})"></div>'
        f'<div class="sf-donut-c"><b style="font-size:1.15rem">{esc(center_top)}</b>'
        f'<span class="sf-muted">{esc(center_bottom)}</span></div></div>'
        f'<div class="sf-legend">{"".join(legend)}</div></div>')
