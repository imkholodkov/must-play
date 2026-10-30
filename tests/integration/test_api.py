import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models import CriticReview, Game, Genre, Outlet, RatingRun
from app.services.rating import recalculate


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def catalog(db_session):
    rpg, indie = Genre(name="RPG"), Genre(name="Indie")
    outlet = Outlet(name="IGN", normalized_name="ign")
    db_session.add_all(
        [
            Game(app_id=1, name="Hollow Knight", positive=9900, negative=100, release_date=None, genres=[indie]),
            Game(app_id=2, name="Big RPG", positive=800, negative=200, price=59.99, genres=[rpg], mac=True),
            Game(app_id=3, name="Tiny", positive=3, negative=0, is_free=True),
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


def test_list_paginated_and_sorted_by_index(client, catalog):
    body = client.get("/games", params={"limit": 2}).json()

    assert body["total"] == 3
    assert [g["app_id"] for g in body["items"]] == [1, 2]
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
def test_list_filters(client, catalog, params, expected):
    assert [g["app_id"] for g in client.get("/games", params=params).json()["items"]] == expected


def test_game_detail_with_reviews(client, catalog):
    body = client.get("/games/2").json()

    assert body["score"]["critic_score"] == 85.0
    assert body["reviews"][0] == {"outlet": "IGN", "quote": "Epic", "raw_score": "9/10", "score": 90}


def test_unknown_game_returns_unified_404(client, catalog):
    response = client.get("/games/999")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Игра 999 не найдена", "details": None}}


def test_create_update_delete_game(client, catalog):
    created = client.post("/games", json={"app_id": 10, "name": "New", "price": "5.00", "genres": ["RPG", "Puzzle"]})
    assert created.status_code == 201
    assert sorted(g["name"] for g in created.json()["genres"]) == ["Puzzle", "RPG"]

    updated = client.patch("/games/10", json={"price": "1.50", "genres": ["Indie"]})
    assert updated.status_code == 200
    assert updated.json()["price"] == "1.50"
    assert [g["name"] for g in updated.json()["genres"]] == ["Indie"]

    assert client.delete("/games/10").status_code == 204
    assert client.get("/games/10").status_code == 404


def test_create_duplicate_game_conflict(client, catalog):
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
def test_validation_errors_are_unified_422(client, catalog, method, url, payload):
    response = getattr(client, method)(url, **({"json": payload} if payload is not None else {}))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_genres_list_and_duplicate(client, catalog):
    assert [g["name"] for g in client.get("/genres").json()] == ["Indie", "RPG"]
    assert client.post("/genres", json={"name": "Roguelike"}).status_code == 201
    assert client.post("/genres", json={"name": "rpg"}).status_code == 409


def test_rating_and_must_play(client, catalog):
    rating = client.get("/rating").json()
    assert [g["app_id"] for g in rating["items"]] == [1, 2]

    client.post("/rating/recalculate")  # второй пересчёт переводит кандидата в список
    must_play = client.get("/must-play").json()
    assert [g["app_id"] for g in must_play["items"]] == [1]


def test_recalculate_conflict_while_running(client, catalog, db_session):
    db_session.add(RatingRun(status="running"))
    db_session.flush()

    response = client.post("/rating/recalculate")

    assert response.status_code == 409
    assert "уже выполняется" in response.json()["error"]["message"]
