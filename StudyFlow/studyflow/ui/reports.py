"""4. Adım – Sade ama eksiksiz rapor: süre dağılımı, hedef ↔ gerçekleşen, müfredat ilerlemesi."""
from __future__ import annotations

import streamlit as st

from ..formatting import fmt_minutes
from ..repository import Repository
from ..services import build_curriculum_progress, build_week_report
from .common import DAYS, OK_COLOR, PALETTE, bar_row, donut, show_html, stat_tiles, week_selector
from .logs import log_list


def _distribution(r) -> None:
    items = [(s.name, s.actual_minutes) for s in r.subjects if s.actual_minutes]
    view = st.pills("Görünüm", ["Pasta", "Çubuk"], default="Pasta", required=True, key="rp_view",
                    label_visibility="collapsed")
    if view == "Pasta":
        donut(items, fmt_minutes(r.total_minutes), "toplam")
    else:
        top = max(m for _, m in items)
        show_html("".join(
            bar_row(n, f"{fmt_minutes(m)} · %{m / r.total_minutes * 100:.0f}", m / top * 100,
                    PALETTE[i % len(PALETTE)]) for i, (n, m) in enumerate(items)))


def _goal_vs_actual(r) -> None:
    rows = [s for s in r.subjects if s.goal_minutes or s.actual_minutes]
    rows.sort(key=lambda s: (s.goal_minutes == 0, -(s.goal_pct or 0), s.name))
    html = []
    for s in rows:
        if s.goal_minutes:
            right = f"hedef {fmt_minutes(s.goal_minutes)} · yapılan {fmt_minutes(s.actual_minutes)} (%{s.goal_pct:.0f})"
            html.append(bar_row(s.name, right, s.goal_pct))
        else:
            html.append(bar_row(s.name, f"hedef yok · yapılan {fmt_minutes(s.actual_minutes)}", None))
    show_html("".join(html))


def _curriculum(repo: Repository) -> None:
    progress = build_curriculum_progress(repo)
    if not progress:
        st.caption("Müfredat boş.")
        return
    for exam, title in (("TYT", "TYT"), ("AYT", "AYT (Matematik + Fen)"), ("", "Diğer")):
        group = [p for p in progress if p.exam == exam]
        if not group:
            continue
        done, total = sum(p.done for p in group), sum(p.total for p in group)
        pct = done / total * 100 if total else 0
        st.markdown(f"**{title}** · %{pct:.0f}")
        show_html("".join(
            bar_row(p.name, f"{p.done}/{p.total} konu · %{p.pct:.0f}", p.pct,
                    OK_COLOR if p.pct >= 100 else None) for p in group))


def render(repo: Repository) -> None:
    ws = week_selector("rp")
    r = build_week_report(repo, ws)

    tiles = [(fmt_minutes(r.total_minutes), "toplam çalışma")]
    if r.goal_pct is not None:
        tiles.append((f"%{r.goal_pct:.0f}", f"hedef: {fmt_minutes(r.total_goal_minutes)}"))
    if r.total_questions:
        tiles.append((str(r.total_questions), "çözülen soru"))
    if r.tasks_total:
        tiles.append((f"{r.tasks_done}/{r.tasks_total}", "görev"))
    stat_tiles(tiles)

    if r.total_minutes:
        st.markdown("**Derslere göre dağılım**")
        _distribution(r)
    else:
        st.info("Bu hafta için henüz çalışma kaydı yok.")

    if any(s.goal_minutes for s in r.subjects):
        st.markdown("**Hedef ↔ Gerçekleşen**")
        _goal_vs_actual(r)
    elif r.total_minutes:
        st.caption("Hedef görmek için 📅 Şablon sayfasında derslere süre ver.")

    st.markdown("**Müfredat ilerlemesi**")
    _curriculum(repo)

    with st.expander("Detaylar: günler, türler, kayıtlar"):
        if r.total_minutes:
            top_day = max(r.by_day.values()) or 1
            st.markdown("**Günlere göre**")
            show_html("".join(bar_row(DAYS[d.weekday()], fmt_minutes(m) if m else "—", m / top_day * 100)
                              for d, m in r.by_day.items()))
            top_type = max(r.by_type.values()) or 1
            st.markdown("**Çalışma türüne göre**")
            show_html("".join(bar_row(t, fmt_minutes(m), m / top_type * 100)
                              for t, m in sorted(r.by_type.items(), key=lambda kv: -kv[1])))
        st.markdown("**Çalışma kayıtları**")
        log_list(repo, ws)
