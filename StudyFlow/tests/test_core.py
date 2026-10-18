from datetime import date, timedelta

import pytest

from studyflow import db
from studyflow.models import week_start
from studyflow.repository import Repository
from studyflow.services import build_week_report

MON = date(2026, 10, 12)  # Pazartesi
TUE = MON + timedelta(days=1)


def test_initialize_is_idempotent_and_seeds_subjects(tmp_path):
    p = tmp_path / "a.db"
    db.initialize(p)
    db.initialize(p)  # ikinci çağrı ders eklememeli
    assert len(Repository(p).list_subjects()) == 14  # TYT (10 ders) + AYT Matematik/Fizik/Kimya/Biyoloji


def test_week_start_is_monday():
    assert week_start(date(2026, 10, 18)) == MON  # Pazar -> aynı haftanın Pazartesi'si


def test_pool_then_schedule_then_unschedule(repo, math_id):
    tid = repo.add_task(subject_id=math_id, title="Limit", task_type="Soru çözümü",
                        planned_minutes=60, week=MON)
    assert [t.id for t in repo.list_pool(MON)] == [tid]
    repo.schedule_task(tid, TUE)
    assert repo.list_pool(MON) == []
    assert repo.list_tasks_for_date(TUE)[0].id == tid
    repo.schedule_task(tid, None)
    assert repo.list_pool(MON)[0].planned_date is None


def test_unfinished_tasks_never_disappear_and_carry_over(repo, math_id):
    t_day = repo.add_task(subject_id=math_id, title="A", task_type="Tekrar",
                          planned_minutes=30, planned_date=MON)
    t_pool = repo.add_task(subject_id=math_id, title="B", task_type="Tekrar",
                           planned_minutes=30, week=MON)
    t_done = repo.add_task(subject_id=math_id, title="C", task_type="Tekrar",
                           planned_minutes=30, planned_date=MON)
    repo.complete_task(t_done, 30, MON)

    next_week_wed = MON + timedelta(days=9)
    backlog = {t.id for t in repo.list_backlog(next_week_wed)}
    assert backlog == {t_day, t_pool}  # tamamlanan hariç hepsi duruyor

    repo.schedule_task(t_day, next_week_wed, carried=True)
    moved = repo.get_task(t_day)
    assert moved.planned_date == next_week_wed
    assert moved.week_start == MON + timedelta(days=7)  # hafta da güncellendi
    assert moved.carry_count == 1
    assert t_day not in {t.id for t in repo.list_backlog(next_week_wed)}

    repo.move_to_next_week(t_pool)
    p = repo.get_task(t_pool)
    assert p.week_start == MON + timedelta(days=7) and p.planned_date is None and p.carry_count == 1


def test_complete_creates_log_and_reopen_removes_it(repo, math_id):
    tid = repo.add_task(subject_id=math_id, title="Türev", task_type="Konu çalışması",
                        planned_minutes=45, planned_date=TUE)
    repo.complete_task(tid, 50, TUE)
    logs = repo.list_logs_for_week(MON)
    assert len(logs) == 1 and logs[0].minutes == 50 and logs[0].study_type == "Konu çalışması"
    assert repo.get_task(tid).done
    repo.reopen_task(tid)
    assert repo.list_logs_for_week(MON) == [] and not repo.get_task(tid).done


def test_deleting_task_keeps_study_log(repo, math_id):
    tid = repo.add_task(subject_id=math_id, title="X", task_type="Tekrar",
                        planned_minutes=20, planned_date=MON)
    repo.complete_task(tid, 20, MON)
    repo.delete_task(tid)
    logs = repo.list_logs_for_week(MON)
    assert len(logs) == 1 and logs[0].task_id is None


def test_validation(repo, math_id):
    with pytest.raises(ValueError):
        repo.add_task(subject_id=math_id, title="  ", task_type="Tekrar", planned_minutes=10, week=MON)
    with pytest.raises(ValueError):
        repo.add_log(log_date=MON, subject_id=math_id, minutes=0, study_type="Tekrar")


def test_goals_upsert_and_delete(repo, math_id):
    repo.set_goal(MON, math_id, 300)
    repo.set_goal(MON, math_id, 420)
    assert repo.get_goals(MON) == {math_id: 420}
    repo.set_goal(MON, math_id, 0)
    assert repo.get_goals(MON) == {}


def test_archived_subject_keeps_history(repo, math_id):
    repo.add_log(log_date=MON, subject_id=math_id, minutes=40, study_type="Tekrar")
    repo.set_subject_archived(math_id, True)
    assert math_id not in {s.id for s in repo.list_subjects()}
    assert build_week_report(repo, MON).subjects[0].name == "AYT Matematik"
    repo.add_subject("ayt matematik")  # aynı isim = arşivden geri getirir
    assert math_id in {s.id for s in repo.list_subjects()}


def test_week_report(repo):
    subj = {s.name: s.id for s in repo.list_subjects()}
    repo.set_goal(MON, subj["AYT Matematik"], 200)
    repo.set_goal(MON, subj["AYT Fizik"], 100)
    repo.add_log(log_date=MON, subject_id=subj["AYT Matematik"], minutes=100, study_type="Soru çözümü")
    repo.add_log(log_date=TUE, subject_id=subj["AYT Matematik"], minutes=50, study_type="Tekrar")
    repo.add_log(log_date=TUE, subject_id=subj["AYT Kimya"], minutes=30, study_type="Tekrar")
    repo.add_log(log_date=MON + timedelta(days=7), subject_id=subj["AYT Fizik"], minutes=99,
                 study_type="Tekrar")  # başka hafta, sayılmamalı
    a = repo.add_task(subject_id=subj["AYT Fizik"], title="a", task_type="Tekrar",
                      planned_minutes=10, week=MON)
    repo.add_task(subject_id=subj["AYT Fizik"], title="b", task_type="Tekrar", planned_minutes=10, week=MON)
    repo.complete_task(a, 0, MON)

    r = build_week_report(repo, MON)
    assert r.total_minutes == 180 and r.total_goal_minutes == 300
    assert r.goal_pct == pytest.approx(60)
    assert (r.tasks_done, r.tasks_total) == (1, 2)
    by_name = {s.name: s for s in r.subjects}
    assert by_name["AYT Matematik"].goal_pct == pytest.approx(75)
    assert by_name["AYT Fizik"].actual_minutes == 0 and by_name["AYT Kimya"].goal_pct is None
    assert r.by_type == {"Soru çözümü": 100, "Tekrar": 80}
    assert r.by_day[MON] == 100 and r.by_day[TUE] == 80


def test_backup_restore_roundtrip(tmp_path, repo, math_id):
    bdir = tmp_path / "backups"
    repo.add_log(log_date=MON, subject_id=math_id, minutes=60, study_type="Tekrar")
    backup = db.create_backup(repo.db_path, bdir, "manual")
    repo.add_log(log_date=TUE, subject_id=math_id, minutes=15, study_type="Tekrar")
    assert len(repo.list_logs_for_week(MON)) == 2

    safety = db.restore_backup(backup, repo.db_path, bdir)
    assert len(repo.list_logs_for_week(MON)) == 1  # yedeğe dönüldü
    assert safety.exists() and safety.stem.endswith("pre-restore")  # eski hal de saklandı


def test_daily_backup_once_per_day_and_prunes(tmp_path, repo):
    bdir = tmp_path / "b"
    assert db.daily_backup(repo.db_path, bdir, keep=3) is not None
    assert db.daily_backup(repo.db_path, bdir, keep=3) is None  # aynı gün tekrar yok
    for d in ("20200101", "20200102", "20200103"):  # eski otomatik yedekler
        db.create_backup(repo.db_path, bdir, "auto").rename(bdir / f"studyflow-{d}-000000-auto.db")
    manual = db.create_backup(repo.db_path, bdir, "manual")
    db.daily_backup(repo.db_path, bdir, keep=3)
    names = [p.name for p in db.list_backups(bdir)]
    assert sum(n.endswith("-auto.db") for n in names) == 3
    assert manual.name in names  # manuel yedek asla silinmez


def test_corrupt_backup_is_rejected(tmp_path, repo):
    bad = tmp_path / "studyflow-bad.db"
    bad.write_bytes(b"this is not a database" * 100)
    with pytest.raises(Exception):
        db.restore_backup(bad, repo.db_path, tmp_path / "b")
    assert repo.list_subjects()  # mevcut veri bozulmadı


# ------------------------------------------------------------------ v2 / soru sayısı
def _make_v1_db(path):
    conn = db.connect(path)
    with conn:
        db.MIGRATIONS[0](conn)
        conn.execute("PRAGMA user_version=1")
    subj = conn.execute("SELECT id FROM subjects LIMIT 1").fetchone()[0]
    with conn:
        conn.execute("INSERT INTO study_logs (id,log_date,subject_id,minutes,study_type,note,task_id,"
                     "created_at,updated_at) VALUES ('x','2026-10-12',?,30,'Tekrar','',NULL,'t','t')", (subj,))
    conn.close()


def test_v1_database_upgrades_in_place_without_data_loss(tmp_path):
    p = tmp_path / "old.db"
    _make_v1_db(p)
    db.initialize(p)
    logs = Repository(p).list_logs(MON, MON)
    assert logs[0].minutes == 30 and logs[0].question_count == 0


def test_restoring_old_v1_backup_upgrades_schema(tmp_path, repo):
    old = tmp_path / "studyflow-20200101-000000-manual.db"
    _make_v1_db(old)
    db.restore_backup(old, repo.db_path, tmp_path / "b")
    logs = repo.list_logs(MON, MON)  # question_count sütunu yoksa burada patlardı
    assert logs and logs[0].question_count == 0
    restored_subject = repo.list_subjects()[0].id  # yedekteki dersler geçerli (kimlikler yedekten gelir)
    repo.add_log(log_date=MON, subject_id=restored_subject, minutes=10, study_type="Tekrar", question_count=5)
    assert {l.question_count for l in repo.list_logs(MON, MON)} == {0, 5}


def test_question_counts_flow_into_logs_and_report(repo, math_id):
    tid = repo.add_task(subject_id=math_id, title="Q", task_type="Soru çözümü",
                        planned_minutes=30, planned_date=MON)
    repo.complete_task(tid, 30, MON, questions=40)
    repo.add_log(log_date=TUE, subject_id=math_id, minutes=20, study_type="Soru çözümü", question_count=25)
    repo.add_log(log_date=TUE, subject_id=math_id, minutes=20, study_type="Tekrar", question_count=-5)
    r = build_week_report(repo, MON)
    assert r.total_questions == 65  # negatif değer 0'a çekilir
    assert r.subjects[0].questions == 65


# ------------------------------------------------------------------ koçluk
from studyflow.services import build_coaching  # noqa: E402
from studyflow.ui.common import is_overdue, postpone_badge  # noqa: E402


def _report(repo, goals=None, logs=None):
    subj = {s.name: s.id for s in repo.list_subjects()}
    for name, m in (goals or {}).items():
        repo.set_goal(MON, subj[name], m)
    for name, m in (logs or {}).items():
        repo.add_log(log_date=MON, subject_id=subj[name], minutes=m, study_type="Tekrar")
    return build_week_report(repo, MON)


def test_coach_without_goal(repo):
    c = build_coaching(_report(repo), MON)
    assert c.level == "info" and "hedef" in c.text.lower()


def test_coach_goal_completed(repo):
    c = build_coaching(_report(repo, {"AYT Matematik": 600}, {"AYT Matematik": 650}), MON + timedelta(days=4))
    assert c.level == "success" and "tamamladın" in c.text


def test_coach_on_pace(repo):
    # Çarşamba (3. gün): hedefin 3/7'si = 300 dk; 400 dk yapıldı
    c = build_coaching(_report(repo, {"AYT Matematik": 700}, {"AYT Matematik": 400}), MON + timedelta(days=2))
    assert c.level == "success" and "Tempodasın" in c.text


def test_coach_slightly_behind_gives_small_gap(repo):
    # Perşembe: bugüne kadar 400 gerekir, yapılan 350 -> 50 dk
    c = build_coaching(_report(repo, {"AYT Matematik": 700}, {"AYT Matematik": 350}), MON + timedelta(days=3))
    assert c.level == "info" and "50 dk" in c.text


def test_coach_far_behind_gives_daily_target(repo):
    # Cuma: 3 gün kaldı (Cuma-Cmt-Paz), kalan 600 dk -> günde ~200 dk
    c = build_coaching(_report(repo, {"AYT Matematik": 700}, {"AYT Matematik": 100}), MON + timedelta(days=4))
    assert c.level == "warning" and "200 dk" in c.text and "3 gün" in c.text


def test_coach_names_lagging_subject_and_backlog(repo):
    rep = _report(repo, {"AYT Matematik": 300, "AYT Fizik": 300}, {"AYT Matematik": 250})
    c = build_coaching(rep, MON + timedelta(days=4), backlog_count=3, studied_today=0)
    assert "AYT Fizik" in c.text and "3" in c.text and "bekleyen" in c.text.lower()
    assert c.text.count("\n\n") <= 2  # en fazla 3 kısa satır


def test_postpone_badge_is_subtle():
    assert postpone_badge(0) is None
    assert "1 kez" in postpone_badge(1) and "⚠️" not in postpone_badge(1)
    assert "⚠️ 2 kez ertelendi" in postpone_badge(2)


def test_is_overdue(repo, math_id):
    t_past = repo.get_task(repo.add_task(subject_id=math_id, title="a", task_type="Tekrar",
                                         planned_minutes=0, planned_date=MON))
    t_pool = repo.get_task(repo.add_task(subject_id=math_id, title="b", task_type="Tekrar",
                                         planned_minutes=0, week=MON))
    assert is_overdue(t_past, TUE) and not is_overdue(t_past, MON)
    assert is_overdue(t_pool, MON + timedelta(days=7)) and not is_overdue(t_pool, TUE)


def test_coach_does_not_nag_about_subjects_on_monday(repo):
    rep = _report(repo, {"AYT Matematik": 300, "AYT Fizik": 300})
    assert "En çok destek" not in build_coaching(rep, MON).text


# ------------------------------------------------------------------ v3: müfredat, şablon, esnek akış
from studyflow.services import build_curriculum_progress, weekly_targets  # noqa: E402


def _sid(repo, name):
    return next(s.id for s in repo.list_subjects() if s.name == name)


def test_curriculum_tyt_all_subjects_ayt_only_math_and_science(repo):
    subs = {s.name: s for s in repo.list_subjects()}
    tyt = [n for n, s in subs.items() if s.exam == "TYT"]
    ayt = [n for n, s in subs.items() if s.exam == "AYT"]
    assert len(tyt) == 10 and "TYT Türkçe" in tyt and "TYT Din Kültürü" in tyt
    assert sorted(ayt) == ["AYT Biyoloji", "AYT Fizik", "AYT Kimya", "AYT Matematik"]  # sosyal/edebiyat yok
    counts = repo.topic_counts()
    assert all(counts[s.id][1] >= 8 and counts[s.id][0] == 0 for s in subs.values())


def test_legacy_subjects_removed_when_unused_archived_when_used(tmp_path):
    p = tmp_path / "old.db"
    _make_v1_db(p)  # v1'de bir derse log yazılmış
    db.initialize(p)
    r = Repository(p)
    used = [s for s in r.list_subjects(include_archived=True) if s.exam == ""]
    assert len(used) == 1 and used[0].archived  # kullanılan eski ders silinmedi, arşive alındı
    assert len(r.list_subjects()) == 14
    assert r.list_logs(MON, MON)[0].minutes == 30  # geçmiş kayıt duruyor


def test_template_roundtrip_replaces_day_and_sums_week(repo):
    mat, fiz = _sid(repo, "AYT Matematik"), _sid(repo, "TYT Fizik")
    repo.set_template_day(0, {mat: 90, fiz: 45})
    repo.set_template_day(2, {mat: 60})
    assert {e.subject_id: e.minutes for e in repo.template_for(MON)} == {mat: 90, fiz: 45}
    assert repo.template_week_minutes() == {mat: 150, fiz: 45}
    repo.set_template_day(0, {fiz: 30})  # tümüyle değiştirir
    assert {e.subject_id for e in repo.template_for(MON)} == {fiz}
    with pytest.raises(ValueError):
        repo.set_template_day(7, {})


def test_week_target_comes_from_template_and_manual_goal_overrides(repo):
    mat, fiz = _sid(repo, "AYT Matematik"), _sid(repo, "TYT Fizik")
    repo.set_template_day(0, {mat: 120})
    repo.set_template_day(3, {mat: 120, fiz: 60})
    assert weekly_targets(repo, MON) == {mat: 240, fiz: 60}
    repo.set_goal(MON, mat, 400)
    assert weekly_targets(repo, MON)[mat] == 400
    repo.add_log(log_date=MON, subject_id=mat, minutes=300, study_type="Tekrar")
    r = build_week_report(repo, MON)
    assert r.total_goal_minutes == 460 and r.total_minutes == 300
    assert {s.name: s.goal_minutes for s in r.subjects} == {"AYT Matematik": 400, "TYT Fizik": 60}


def test_draft_from_template_is_idempotent_and_swap_aware(repo):
    mat, fiz, kim = _sid(repo, "AYT Matematik"), _sid(repo, "AYT Fizik"), _sid(repo, "AYT Kimya")
    repo.set_template_day(0, {mat: 90, fiz: 45})
    assert repo.create_draft_from_template(MON) == 2
    assert repo.create_draft_from_template(MON) == 0
    fiz_task = next(t for t in repo.list_tasks_for_date(MON) if t.subject_id == fiz)
    repo.swap_task(fiz_task.id, kim)  # Fizik yerine Kimya çalışıldı
    assert repo.create_draft_from_template(MON) == 0  # Fizik için yeni taslak açılmaz


def test_swap_task_keeps_origin_logs_to_new_subject_and_can_revert(repo):
    fiz, kim = _sid(repo, "AYT Fizik"), _sid(repo, "AYT Kimya")
    topic = repo.list_topics(kim)[0]
    tid = repo.add_task(subject_id=fiz, title="Vektörler", task_type="Konu çalışması",
                        planned_minutes=45, planned_date=MON)
    repo.swap_task(tid, kim, topic.id)
    t = repo.get_task(tid)
    assert (t.subject_id, t.original_subject_id, t.topic_id, t.title) == (kim, fiz, topic.id, topic.name)
    repo.swap_task(tid, fiz)  # eski derse dönüş: iz silinir
    assert repo.get_task(tid).original_subject_id is None
    repo.swap_task(tid, kim)
    repo.complete_task(tid, 40, MON)
    assert repo.list_logs(MON, MON)[0].subject_id == kim  # kayıt gerçek çalışılan derse yazıldı
    with pytest.raises(ValueError):
        repo.swap_task(tid, fiz)  # tamamlanmış görev değiştirilemez


def test_completing_task_can_finish_topic_and_undo_restores(repo):
    kim = _sid(repo, "AYT Kimya")
    topic = repo.list_topics(kim)[0]
    tid = repo.add_task(subject_id=kim, title=topic.name, task_type="Konu çalışması",
                        planned_minutes=40, planned_date=MON, topic_id=topic.id)
    assert topic.id in repo.planned_topic_ids()
    repo.complete_task(tid, 40, MON, topic_done=True)
    assert repo.topic_counts()[kim][0] == 1 and topic.id not in repo.planned_topic_ids()
    repo.reopen_task(tid)
    assert repo.topic_counts()[kim][0] == 0


def test_reopen_does_not_undo_a_topic_that_was_already_done(repo):
    kim = _sid(repo, "AYT Kimya")
    topic = repo.list_topics(kim)[0]
    repo.set_topic_done(topic.id, True)
    tid = repo.add_task(subject_id=kim, title="Tekrar", task_type="Tekrar", planned_minutes=20,
                        planned_date=MON, topic_id=topic.id)
    repo.complete_task(tid, 20, MON, topic_done=True)
    repo.reopen_task(tid)
    assert repo.topic_counts()[kim][0] == 1  # konuyu bu görev bitirmemişti


def test_carry_unfinished_moves_only_todo_tasks_and_counts(repo, math_id):
    a = repo.add_task(subject_id=math_id, title="a", task_type="Tekrar", planned_minutes=10, planned_date=MON)
    b = repo.add_task(subject_id=math_id, title="b", task_type="Tekrar", planned_minutes=10, planned_date=MON)
    repo.complete_task(b, 10, MON)
    assert repo.carry_unfinished(MON, TUE) == 1
    assert repo.get_task(a).planned_date == TUE and repo.get_task(a).carry_count == 1
    assert repo.get_task(b).planned_date == MON  # bitenler yerinde kalır


def test_extra_study_is_one_transaction_with_log_and_topic(repo):
    kim = _sid(repo, "AYT Kimya")
    topic = repo.list_topics(kim)[1]
    repo.add_done_task(subject_id=kim, title="Ekstra", task_type="Soru çözümü", minutes=35, day=TUE,
                       topic_id=topic.id, questions=50, topic_done=True)
    log = repo.list_logs(TUE, TUE)[0]
    assert (log.minutes, log.question_count, log.subject_id) == (35, 50, kim)
    assert repo.topic_counts()[kim][0] == 1
    with pytest.raises(ValueError):  # başlık boşsa hiçbir şey yazılmaz
        repo.add_done_task(subject_id=kim, title=" ", task_type="Tekrar", minutes=5, day=TUE)
    assert len(repo.list_logs(TUE, TUE)) == 1


def test_curriculum_progress_and_topic_crud(repo):
    fiz = _sid(repo, "TYT Fizik")
    topics = repo.list_topics(fiz)
    for t in topics[:3]:
        repo.set_topic_done(t.id, True)
    p = next(x for x in build_curriculum_progress(repo) if x.subject_id == fiz)
    assert (p.done, p.total) == (3, len(topics)) and p.pct == pytest.approx(3 / len(topics) * 100)
    repo.add_topic(fiz, "Özel konu")
    with pytest.raises(ValueError):
        repo.add_topic(fiz, "özel konu")  # aynı ad iki kez eklenmez
    repo.delete_topic(next(t.id for t in repo.list_topics(fiz) if t.name == "Özel konu"))
    assert len(repo.list_topics(fiz)) == len(topics)


def test_deleting_topic_keeps_task_and_clears_link(repo):
    fiz = _sid(repo, "TYT Fizik")
    topic = repo.list_topics(fiz)[0]
    tid = repo.add_task(subject_id=fiz, title="X", task_type="Tekrar", planned_minutes=10,
                        planned_date=MON, topic_id=topic.id)
    repo.delete_topic(topic.id)
    assert repo.get_task(tid).topic_id is None


def test_seeding_is_idempotent(tmp_path):
    p = tmp_path / "s.db"
    db.initialize(p)
    r = Repository(p)
    before = sum(n for _, n in r.topic_counts().values())
    with db.session(p) as conn:
        db.seed_curriculum(conn)
    assert sum(n for _, n in r.topic_counts().values()) == before and len(r.list_subjects()) == 14
