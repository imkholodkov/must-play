import pytest

from app.models import CriticReview, Genre, Outlet, RatingRun
from app.services.rating import recalculate
from tests.helpers import make_game


@pytest.fixture
def catalog(db_session):
    """Три игры: известный хит, RPG с оценками прессы и игра с тремя голосами."""
    rpg, indie = Genre(name="RPG"), Genre(name="Indie")
    outlet = Outlet(name="IGN", normalized_name="ign")
    db_session.add_all(
        [
            make_game(1, "Hollow Knight", positive=990_000, negative=10_000, genres=[indie]),
            make_game(2, "Big RPG", positive=800, negative=200, price=59.99, genres=[rpg], mac=True),
            make_game(3, "Tiny", positive=3, negative=0, is_free=True),
            outlet,
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            CriticReview(app_id=2, outlet_id=outlet.id, quote="Epic", raw_score="9/10", score=90),
            CriticReview(app_id=2, quote="Fine", score=80),
        ]
    )
    db_session.flush()
    recalculate(db_session)


@pytest.mark.usefixtures("catalog")
class TestGamesList:
    def test_paginated_and_sorted_by_index(self, client):
        body = client.get("/games", params={"limit": 2}).json()

        assert body["total"] == 3
        # у Tiny три голоса, её оценка почти равна средней по каталогу и оказывается выше Big RPG с 80%
        assert [g["app_id"] for g in body["items"]] == [1, 3]
        assert body["items"][0]["score"]["is_eligible"] is True

    @pytest.mark.parametrize(
        ("params", "expected"),
        [
            ({"genre": "rpg"}, [2]),
            ({"q": "hollow"}, [1]),
            ({"platform": "mac"}, [2]),
            ({"free": True}, [3]),
            ({"eligible": True, "sort": "name", "desc": False}, [2, 1]),
            ({"max_price": 10}, []),
        ],
    )
    def test_filters(self, client, params, expected):
        assert [g["app_id"] for g in client.get("/games", params=params).json()["items"]] == expected


@pytest.mark.usefixtures("catalog")
class TestGameCard:
    def test_detail_with_reviews(self, client):
        body = client.get("/games/2").json()

        assert body["score"]["critic_score"] == 85.0
        assert body["reviews"][0] == {"outlet": "IGN", "quote": "Epic", "raw_score": "9/10", "score": 90}

    def test_unknown_game_returns_unified_404(self, client):
        response = client.get("/games/999")

        assert response.status_code == 404
        assert response.json() == {"error": {"code": "not_found", "message": "Игра 999 не найдена", "details": None}}


@pytest.mark.usefixtures("catalog")
class TestGamesCrud:
    def test_create_update_delete(self, client):
        created = client.post(
            "/games", json={"app_id": 10, "name": "New", "price": "5.00", "genres": ["RPG", "Puzzle"]}
        )
        assert created.status_code == 201
        assert sorted(g["name"] for g in created.json()["genres"]) == ["Puzzle", "RPG"]

        updated = client.patch("/games/10", json={"price": "1.50", "genres": ["Indie"]})
        assert updated.status_code == 200
        assert updated.json()["price"] == "1.50"
        assert [g["name"] for g in updated.json()["genres"]] == ["Indie"]

        assert client.delete("/games/10").status_code == 204
        assert client.get("/games/10").status_code == 404

    def test_duplicate_is_conflict(self, client):
        response = client.post("/games", json={"app_id": 1, "name": "Copy"})

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"

    @pytest.mark.parametrize(
        ("method", "url", "payload"),
        [
            ("post", "/games", {"app_id": -1, "name": "Bad"}),
            ("post", "/games", {"app_id": 5, "name": "", "price": "-3"}),
            ("patch", "/games/1", {}),
            ("get", "/games?limit=500", None),
        ],
    )
    def test_validation_errors_are_unified_422(self, client, method, url, payload):
        response = getattr(client, method)(url, **({"json": payload} if payload is not None else {}))

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.usefixtures("catalog")
class TestGenres:
    def test_list_and_duplicate(self, client):
        assert [g["name"] for g in client.get("/genres").json()] == ["Indie", "RPG"]
        assert client.post("/genres", json={"name": "Roguelike"}).status_code == 201
        assert client.post("/genres", json={"name": "rpg"}).status_code == 409


@pytest.mark.usefixtures("catalog")
class TestRatingApi:
    def test_rating_and_must_play(self, client):
        rating = client.get("/rating").json()
        assert [g["app_id"] for g in rating["items"]] == [1, 2]

        client.post("/rating/recalculate")  # второй пересчёт переводит кандидата в список
        must_play = client.get("/must-play").json()
        assert [g["app_id"] for g in must_play["items"]] == [1]

    def test_recalculate_conflict_while_running(self, client, db_session):
        db_session.add(RatingRun(status="running"))
        db_session.flush()

        response = client.post("/rating/recalculate")

        assert response.status_code == 409
        assert "уже выполняется" in response.json()["error"]["message"]
