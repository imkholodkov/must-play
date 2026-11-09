import pytest
from sqlalchemy import select

from app.models import CriticReview, GameScore, Genre, MustPlayEntry, RatingRun, ScoreHistory
from app.services import rating
from app.services.rating import RatingInProgressError, recalculate
from tests.helpers import count, make_game


@pytest.fixture(autouse=True)
def games(db_session):
    """Хит, его дубль, программа, игра со спорными оценками и игра с тремя голосами."""
    db_session.add_all(
        [
            make_game(1, "Hit", positive=980_000, negative=20_000),
            make_game(4, "HIT™"),  # дубль той же игры
            make_game(5, "Wallpaper", positive=90_000, negative=1_000, genres=[Genre(name="Utilities")]),
            make_game(2, "Mixed", positive=500, negative=500),
            make_game(3, "Tiny", positive=3, negative=0),
        ]
    )
    db_session.flush()  # сначала игры: у обзоров нет relationship, и порядок вставки SQLAlchemy не знает
    db_session.add_all([CriticReview(app_id=2, quote="a", score=95), CriticReview(app_id=2, quote="b", score=85)])
    db_session.flush()


class TestRecalculate:
    def test_scores_flags_and_must_play(self, db_session):
        run = recalculate(db_session)

        assert run.status == "success"
        assert run.games_scored == 5
        mixed = db_session.get(GameScore, 2)
        assert (mixed.critic_score, mixed.divergence) == (90.0, "overrated")
        assert db_session.get(GameScore, 3).is_eligible is False  # мало голосов
        assert db_session.get(GameScore, 4).is_eligible is False  # дубль
        assert db_session.get(GameScore, 5).is_eligible is False  # программа, а не игра
        assert db_session.get(MustPlayEntry, 1).status == "candidate"
        assert count(db_session, ScoreHistory) == 2  # в историю попадают только допущенные игры

    def test_second_run_promotes_candidate(self, db_session):
        recalculate(db_session)
        recalculate(db_session)

        assert db_session.get(MustPlayEntry, 1).status == "in_list"
        assert count(db_session, GameScore) == 5
        assert count(db_session, ScoreHistory) == 4


class TestRecalculateSafety:
    def test_failed_run_leaves_previous_rating(self, db_session, monkeypatch):
        recalculate(db_session)
        before = db_session.get(GameScore, 1).run_id

        def broken(*args, **kwargs):
            raise RuntimeError("сбой посреди пересчёта")

        monkeypatch.setattr(rating, "next_must_play_status", broken)
        with pytest.raises(RuntimeError):
            recalculate(db_session)

        db_session.expire_all()
        assert db_session.get(GameScore, 1).run_id == before
        assert db_session.scalar(select(RatingRun.status).order_by(RatingRun.id.desc()).limit(1)) == "failed"

    def test_parallel_run_rejected(self, db_session):
        db_session.add(RatingRun(status="running"))
        db_session.flush()

        with pytest.raises(RatingInProgressError):
            recalculate(db_session)
