from datetime import date

import pytest

from app.models import CriticReview, Genre, Outlet
from app.services.rating import recalculate
from tests.helpers import make_game


@pytest.fixture(autouse=True)
def catalog(db_session):
    """Любимая игроками, раскрученная прессой и бесплатная игра; строгое и щедрое издание."""
    rpg, indie = Genre(name="RPG"), Genre(name="Indie")
    strict, generous = Outlet(name="Strict", normalized_name="strict"), Outlet(name="Kind", normalized_name="kind")
    db_session.add_all(
        [
            make_game(1, "Loved", positive=950, negative=50, release_date=date(2018, 5, 1), genres=[indie]),
            make_game(2, "Hyped", positive=400, negative=600, release_date=date(2018, 6, 1), genres=[rpg]),
            make_game(3, "Free", positive=700, negative=300, is_free=True, release_date=date(2019, 1, 1), genres=[rpg]),
            strict,
            generous,
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            CriticReview(app_id=2, outlet_id=strict.id, quote="", score=90),
            CriticReview(app_id=2, outlet_id=generous.id, quote="", score=100),
            CriticReview(app_id=1, outlet_id=strict.id, quote="", score=40),
            CriticReview(app_id=1, outlet_id=generous.id, quote="", score=50),
        ]
    )
    db_session.flush()
    recalculate(db_session)


class TestGenresAnalytics:
    def test_grouped(self, client):
        body = client.get("/analytics/genres", params={"min_games": 1}).json()

        assert {g["genre"]: g["games"] for g in body} == {"RPG": 2, "Indie": 1}
        assert next(g for g in body if g["genre"] == "RPG")["free_share"] == 50.0


class TestReleases:
    def test_by_year(self, client):
        body = client.get("/analytics/releases", params={"year_from": 2018, "year_to": 2019}).json()

        assert [(y["year"], y["releases"], y["free_share"]) for y in body] == [(2018, 2, 0.0), (2019, 1, 100.0)]

    def test_bad_range(self, client):
        response = client.get("/analytics/releases", params={"year_from": 2020, "year_to": 2010})

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "bad_request"


class TestDivergence:
    def test_top(self, client):
        over = client.get("/analytics/divergence", params={"kind": "overrated"}).json()
        under = client.get("/analytics/divergence", params={"kind": "underrated"}).json()

        assert [g["name"] for g in over] == ["Hyped"]
        assert over[0]["gap"] == 55.0  # пресса 95, игроки 40%
        assert [g["name"] for g in under] == ["Loved"]


class TestOutlets:
    def test_strictness(self, client):
        strict = client.get("/analytics/outlets", params={"min_reviews": 1}).json()

        assert [o["outlet"] for o in strict] == ["Strict", "Kind"]
        assert strict[0]["vs_average"] == -5.0
