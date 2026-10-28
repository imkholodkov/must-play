import csv

from sqlalchemy import func, select

from app.etl.import_reviews import run_import
from app.models import CriticReview, Game, Outlet


def write_reviews(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["app_id", "name", "reviews"])
        writer.writerows(rows)
    return path


def test_reviews_loaded_with_outlets_merged(db_session, tmp_path):
    db_session.add_all([Game(app_id=1, name="One"), Game(app_id=2, name="Two")])
    db_session.flush()
    source = write_reviews(
        tmp_path / "reviews.csv",
        [
            ("1", "One", "“Great” 9/10 – Rock Paper Shotgun “Again” 2/10 – Rock, Paper, Shotgun “Nice” 4/5 – IGN"),
            ("2", "Two", "“Fine” Rock, Paper, Shotgun"),
            ("3", "Missing", "“Ghost” 5/5 – IGN"),
            ("1", "One", "“Dup” 1/10 – IGN"),
            ("4", "Empty", ""),
        ],
    )

    run = run_import(db_session, source)

    assert run.status == "success"
    assert run.rows_loaded == 2
    assert run.rejection_reasons == {"duplicate_app_id": 1, "no_quotes": 1, "unknown_game": 1}
    assert db_session.scalar(select(func.count()).select_from(Outlet)) == 2
    scores = db_session.scalars(select(CriticReview.score).where(CriticReview.app_id == 1)).all()
    assert sorted(scores) == [80, 90]  # второй обзор того же издания отброшен


def test_reimport_replaces_reviews(db_session, tmp_path):
    db_session.add(Game(app_id=1, name="One"))
    db_session.flush()
    run_import(db_session, write_reviews(tmp_path / "a.csv", [("1", "One", "“Old” 5/10 – IGN")]))

    second = run_import(db_session, write_reviews(tmp_path / "b.csv", [("1", "One", "“New” 9/10 – IGN")]))

    assert second.rows_updated == 1
    assert db_session.scalars(select(CriticReview.quote)).all() == ["New"]
