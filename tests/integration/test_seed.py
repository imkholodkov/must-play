from sqlalchemy import func, select

from app.models import CriticReview, Game, GameScore, MustPlayEntry
from app.seed import seed


def count(session, model, *where):
    return session.scalar(select(func.count()).select_from(model).where(*where))


def test_seed_fills_every_layer(db_session):
    result = seed(db_session)

    assert result["games_loaded"] == count(db_session, Game) == 302
    assert count(db_session, CriticReview) > 0
    assert count(db_session, GameScore) == result["games_scored"]
    assert count(db_session, MustPlayEntry, MustPlayEntry.status == "candidate") == 0  # второй пересчёт уже прошёл
    assert result["similar_pairs"] > 0


def test_seed_is_idempotent(db_session):
    seed(db_session)
    games, reviews = count(db_session, Game), count(db_session, CriticReview)

    seed(db_session)

    assert count(db_session, Game) == games
    assert count(db_session, CriticReview) == reviews
