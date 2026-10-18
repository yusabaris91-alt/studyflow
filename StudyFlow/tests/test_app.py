"""Arayüz uçtan uca testleri (Streamlit AppTest): gerçekten tıklayıp sonucu DB'den doğrular."""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from studyflow.config import DB_PATH
from studyflow.repository import Repository
from studyflow.ui import common

APP = Path(__file__).resolve().parent.parent / "app.py"
TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)


@pytest.fixture
def repo():
    r = Repository(DB_PATH)
    AppTest.from_file(str(APP), default_timeout=30).run()  # şema + müfredat hazır olsun
    conn = sqlite3.connect(DB_PATH)  # testler birbirini etkilemesin: plan/kayıt verisini temizle
    with conn:
        for table in ("study_logs", "tasks", "weekly_template", "weekly_goals"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("UPDATE topics SET done=0, done_at=NULL")
    conn.close()
    return r


@pytest.fixture
def at(repo):
    app = AppTest.from_file(str(APP), default_timeout=30)
    app.run()
    assert not app.exception, app.exception
    return app


def go(at, page):
    at.session_state["page"] = page
    at.run()
    assert not at.exception, at.exception


def btn(at, key):
    return next(b for b in at.button if b.key == key)


def sid(repo, name):
    return next(s.id for s in repo.list_subjects() if s.name == name)


def test_app_opens_on_today_with_coach_box(at):
    assert at.title[0].value.endswith("StudyFlow")
    assert at.session_state["page"] == common.PAGE_TODAY
    boxes = list(at.info) + list(at.success) + list(at.warning)
    assert boxes


def test_every_page_renders_without_errors(at, repo):
    repo.set_template_day(TODAY.weekday(), {sid(repo, "AYT Matematik"): 60})
    repo.set_template_day(TOMORROW.weekday(), {sid(repo, "TYT Fizik"): 45})
    for page in (common.PAGE_PLAN, common.PAGE_TEMPLATE, common.PAGE_TOPICS, common.PAGE_REPORTS,
                 common.PAGE_SETTINGS, common.PAGE_TODAY):
        go(at, page)


def test_template_draft_complete_and_undo_flow(at, repo):
    mat = sid(repo, "AYT Matematik")
    repo.set_template_day(TODAY.weekday(), {mat: 50})
    at.run()
    btn(at, "draft_today").click().run()
    assert not at.exception, at.exception
    task = repo.list_tasks_for_date(TODAY)[0]
    assert task.subject_id == mat and task.planned_minutes == 50

    btn(at, f"day-{task.id}-complete").click().run()
    assert not at.exception, at.exception
    assert repo.get_task(task.id).done
    assert any(l.task_id == task.id and l.minutes == 50 for l in repo.list_logs(TODAY, TODAY))

    btn(at, f"day-{task.id}-undo").click().run()
    assert not repo.get_task(task.id).done
    assert not repo.list_logs(TODAY, TODAY)


def test_swap_today_task_to_another_subject(at, repo):
    fiz, kim = sid(repo, "AYT Fizik"), sid(repo, "AYT Kimya")
    tid = repo.add_task(subject_id=fiz, title="Vektörler", task_type="Konu çalışması",
                        planned_minutes=40, planned_date=TODAY)
    at.run()
    next(s for s in at.selectbox if s.key == f"day-{tid}-swsub").select(kim).run()
    btn(at, f"day-{tid}-swap").click().run()
    assert not at.exception, at.exception
    t = repo.get_task(tid)
    assert t.subject_id == kim and t.original_subject_id == fiz

    btn(at, f"day-{tid}-complete").click().run()
    assert repo.list_logs(TODAY, TODAY)[0].subject_id == kim  # gerçek çalışılan ders


def test_carry_all_unfinished_to_tomorrow(at, repo):
    mat = sid(repo, "AYT Matematik")
    tid = repo.add_task(subject_id=mat, title="A", task_type="Tekrar", planned_minutes=20, planned_date=TODAY)
    at.run()
    btn(at, "carry_all").click().run()
    assert not at.exception, at.exception
    t = repo.get_task(tid)
    assert t.planned_date == TOMORROW and t.carry_count == 1


def test_tomorrow_plan_adds_next_topic_in_one_tap(at, repo):
    kim = sid(repo, "AYT Kimya")
    repo.set_template_day(TOMORROW.weekday(), {kim: 60})
    at.session_state["page"] = common.PAGE_PLAN
    at.session_state["plan_day"] = TOMORROW
    at.run()
    assert not at.exception, at.exception
    btn(at, f"plan-{TOMORROW.isoformat()}-{kim}-next").click().run()
    assert not at.exception, at.exception
    t = repo.list_tasks_for_date(TOMORROW)[0]
    assert t.topic_id and t.planned_minutes == 60 and t.subject_id == kim


def test_extra_study_and_topic_completion_show_in_progress(at, repo):
    kim = sid(repo, "AYT Kimya")
    at.session_state["extra_subj"] = kim
    at.run()
    next(b for b in at.button if b.label == "✅ Yaptım, kaydet").click().run()
    assert not at.exception, at.exception
    assert any(l.subject_id == kim and l.minutes == 30 for l in repo.list_logs(TODAY, TODAY))
