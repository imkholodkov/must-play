from sqlalchemy import CheckConstraint, UniqueConstraint

import app.models  # noqa: F401
from app.core.database import Base

tables = Base.metadata.tables


def constraint_names(table: str, kind: type) -> set[str]:
    return {c.name for c in tables[table].constraints if isinstance(c, kind)}


def test_all_tables_registered():
    assert {"games", "genres", "game_genres", "outlets", "critic_reviews", "game_scores", "etl_runs"} <= set(tables)


def test_many_to_many_link_has_composite_key():
    assert [c.name for c in tables["game_genres"].primary_key] == ["app_id", "genre_id"]


def test_game_integrity_checks():
    assert {"ck_games_price_non_negative", "ck_games_votes_non_negative", "ck_games_metacritic_range"} <= (
        constraint_names("games", CheckConstraint)
    )


def test_one_review_per_outlet():
    assert "uq_critic_reviews_app_id_outlet_id" in constraint_names("critic_reviews", UniqueConstraint)


def test_search_fields_indexed():
    indexed = {idx.columns.keys()[0] for idx in tables["games"].indexes}
    assert {"name", "release_date"} <= indexed
