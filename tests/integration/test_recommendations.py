import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.database import get_db
from app.main import app
from app.models import Category, Game, GameSimilarity, Genre, Language, Tag
from app.services.rating import recalculate
from app.services.recommendations import build_similarities


@pytest.fixture
def client(db_session):
    rpg, puzzle = Genre(name="RPG"), Genre(name="Puzzle")
    rogue, cozy = Tag(name="Roguelike"), Tag(name="Cozy")
    coop, single = Category(name="Co-op"), Category(name="Single-player")
    russian = Language(name="Russian")

    def game(app_id, name, genres, tags, cats, positive, **kw):
        return Game(
            app_id=app_id,
            name=name,
            positive=positive,
            negative=100,
            genres=genres,
            tags=tags,
            categories=cats,
            **kw,
        )

    db_session.add_all(
        [
            game(1, "Rogue A", [rpg], [rogue], [coop], 900, mac=True, price=10, languages=[russian]),
            game(2, "Rogue B", [rpg], [rogue], [coop], 500, mac=False, price=30),
            game(3, "Rogue C", [rpg], [rogue], [single], 300, mac=True, price=5),
            game(4, "Cozy Puzzle", [puzzle], [cozy], [single], 800, mac=True, price=3),
        ]
    )
    db_session.flush()
    recalculate(db_session)
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_build_similarities(client, db_session):
    stats = build_similarities(db_session, top_k=2)

    assert stats["games"] == 4
    assert db_session.scalar(select(func.count()).select_from(GameSimilarity)) == 8
    assert stats["genre_precision"] > 0.5


def test_similar_games_prefers_same_genre(client, db_session):
    build_similarities(db_session, top_k=2)

    body = client.get("/games/1/similar").json()

    assert [g["app_id"] for g in body] == [2, 3]
    assert all(0 < g["similarity"] <= 1 for g in body)


def test_similar_unknown_game_404(client):
    assert client.get("/games/999/similar").status_code == 404


@pytest.mark.parametrize(
    ("prefs", "expected"),
    [
        ({"genres": ["rpg"]}, [1, 2, 3]),
        ({"genres": ["RPG"], "mode": "coop"}, [1, 2]),
        ({"tags": ["roguelike"], "platform": "mac"}, [1, 3]),
        ({"max_price": "8"}, [4, 3]),
        ({"language": "russian"}, [1]),
        ({"genres": ["RPG"], "exclude": [1]}, [2, 3]),
    ],
)
def test_recommend_by_preferences(client, prefs, expected):
    response = client.post("/recommendations", json=prefs)

    assert response.status_code == 200
    assert [g["app_id"] for g in response.json()] == expected


def test_recommend_rejects_unknown_mode(client):
    response = client.post("/recommendations", json={"mode": "pvp"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
