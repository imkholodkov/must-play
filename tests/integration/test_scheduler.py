from contextlib import nullcontext

import pytest

from app import scheduler
from app.models import Game, RatingRun


@pytest.fixture
def use_session(db_session, monkeypatch):
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: nullcontext(db_session))
    return db_session


def test_refresh_recalculates_rating_and_similar(use_session):
    use_session.add_all([Game(app_id=i, name=f"G{i}", positive=900, negative=100) for i in (1, 2)])
    use_session.flush()

    result = scheduler.refresh()

    assert result["games_scored"] == 2
    assert use_session.get(RatingRun, result["rating_run"]).status == "success"


def test_refresh_skips_when_run_in_progress(use_session):
    use_session.add(RatingRun(status="running"))
    use_session.flush()

    assert scheduler.refresh() is None


def test_scheduler_uses_cron_from_settings():
    job = scheduler.build_scheduler("0 3 * * 1").get_job("refresh")

    assert str(job.trigger) == "cron[month='*', day='*', day_of_week='1', hour='3', minute='0']"
