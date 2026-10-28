import csv

from sqlalchemy import func, select

from app.etl.import_data import run_import
from app.models import EtlRun, Game, Genre
from app.models.catalog import game_genres
from tests.conftest import SAMPLE_CSV

FIELDS = ["app_id", "name", "genres", "positive", "negative"]


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def count(session, entity):
    return session.scalar(select(func.count()).select_from(entity))


def test_import_sample_writes_report(db_session):
    run = run_import(db_session, SAMPLE_CSV, batch_size=50)

    assert run.status == "success"
    assert run.rows_read == 305
    assert run.rows_loaded + run.rows_rejected == run.rows_read
    assert count(db_session, Game) == run.rows_loaded
    assert db_session.get(EtlRun, run.id).finished_at is not None


def test_repeated_import_creates_no_duplicates(db_session):
    first = run_import(db_session, SAMPLE_CSV)
    games, links = count(db_session, Game), count(db_session, game_genres)

    second = run_import(db_session, SAMPLE_CSV)

    assert second.rows_loaded == 0
    assert second.rows_updated == first.rows_loaded
    assert count(db_session, Game) == games
    assert count(db_session, game_genres) == links


def test_bad_and_duplicate_rows_are_reported(db_session, tmp_path):
    source = write_csv(
        tmp_path / "games.csv",
        [
            {"app_id": "1", "name": "Game", "genres": '["Action", "Indie"]', "positive": "5", "negative": "1"},
            {"app_id": "1", "name": "Game again", "genres": "[]", "positive": "0", "negative": "0"},
            {"app_id": "2", "name": "", "genres": "[]", "positive": "0", "negative": "0"},
            {"app_id": "x", "name": "No id", "genres": "[]", "positive": "0", "negative": "0"},
        ],
    )

    run = run_import(db_session, source)

    assert run.rows_loaded == 1
    assert run.rejection_reasons == {"duplicate_app_id": 1, "empty_name": 1, "bad_app_id": 1}
    assert sorted(g.name for g in db_session.get(Game, 1).genres) == ["Action", "Indie"]
    assert count(db_session, Genre) == 2


def test_reimport_replaces_game_links(db_session, tmp_path):
    row = {"app_id": "1", "name": "Game", "positive": "1", "negative": "0"}
    run_import(db_session, write_csv(tmp_path / "a.csv", [{**row, "genres": '["Action"]'}]))
    run_import(db_session, write_csv(tmp_path / "b.csv", [{**row, "genres": '["RPG"]'}]))

    db_session.expire_all()
    assert [g.name for g in db_session.get(Game, 1).genres] == ["RPG"]
