import pytest

from app.models import Category, GameSimilarity, Genre, Language, Tag
from app.services.rating import recalculate
from app.services.rec_metrics import evaluate
from app.services.recommendations import build_similarities
from tests.helpers import count, make_game


@pytest.fixture(autouse=True)
def catalog(db_session):
    """Три похожих рогалика и одна непохожая головоломка."""
    rpg, puzzle = Genre(name="RPG"), Genre(name="Puzzle")
    rogue, cozy = Tag(name="Roguelike"), Tag(name="Cozy")
    coop, single = Category(name="Co-op"), Category(name="Single-player")
    russian = Language(name="Russian")
    db_session.add_all(
        [
            make_game(
                1,
                "Rogue A",
                900,
                genres=[rpg],
                tags=[rogue],
                categories=[coop],
                mac=True,
                price=10,
                languages=[russian],
            ),
            make_game(2, "Rogue B", 500, genres=[rpg], tags=[rogue], categories=[coop], mac=False, price=30),
            make_game(3, "Rogue C", 300, genres=[rpg], tags=[rogue], categories=[single], mac=True, price=5),
            make_game(4, "Cozy Puzzle", 800, genres=[puzzle], tags=[cozy], categories=[single], mac=True, price=3),
        ]
    )
    db_session.flush()
    recalculate(db_session)


class TestSimilarGames:
    def test_build_similarities(self, db_session):
        stats = build_similarities(db_session, top_k=2)

        assert stats["games"] == 4
        assert count(db_session, GameSimilarity) == 8

    def test_prefers_same_genre(self, client, db_session):
        build_similarities(db_session, top_k=2)

        body = client.get("/games/1/similar").json()

        assert [g["app_id"] for g in body] == [2, 3]
        assert all(0 < g["similarity"] <= 1 for g in body)

    def test_unknown_game_404(self, client):
        assert client.get("/games/999/similar").status_code == 404


class TestRecommendByPreferences:
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
    def test_filters(self, client, prefs, expected):
        response = client.post("/recommendations", json=prefs)

        assert response.status_code == 200
        assert [g["app_id"] for g in response.json()] == expected

    def test_rejects_unknown_mode(self, client):
        response = client.post("/recommendations", json={"mode": "pvp"})

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


class TestRecommendationMetrics:
    def test_evaluate(self, db_session):
        metrics = evaluate(db_session)

        assert set(metrics["tag_precision_at_10"]) == {"model_without_tags", "random", "popular"}
        assert 0 <= metrics["catalog_coverage"] <= 1
        assert metrics["avg_index_catalog"] is not None
