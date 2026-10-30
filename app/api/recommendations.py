"""Рекомендации: похожие игры и подбор по анкете."""

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.database import DbSession
from app.schemas.game import GameRead
from app.services import recommendations as service
from app.services.games import get_or_404

router = APIRouter(tags=["recommendations"])


class SimilarGame(GameRead):
    similarity: float = Field(description="Косинусная близость по жанрам, тегам и категориям, 0–1")


class PreferencesIn(BaseModel):
    genres: list[str] = Field(default_factory=list, max_length=5, examples=[["RPG"]])
    tags: list[str] = Field(default_factory=list, max_length=5, examples=[["Roguelike"]])
    mode: Literal["single", "coop", "multiplayer"] | None = Field(default=None, examples=["coop"])
    platform: Literal["windows", "mac", "linux"] | None = None
    language: str | None = Field(default=None, examples=["Russian"])
    max_price: Decimal | None = Field(default=None, ge=0, examples=["20"])
    exclude: list[int] = Field(default_factory=list, description="app_id игр, которые уже пройдены")
    limit: int = Field(default=10, ge=1, le=50)


@router.get("/games/{app_id}/similar", summary="Похожие игры: «если понравилась эта»")
def similar(app_id: int, db: DbSession, limit: Annotated[int, Query(ge=1, le=10)] = 10) -> list[SimilarGame]:
    get_or_404(db, app_id)
    return [
        SimilarGame.model_validate({**GameRead.model_validate(game).model_dump(), "similarity": score})
        for game, score in service.similar_games(db, app_id, limit)
    ]


@router.post("/recommendations", summary="Подбор «во что поиграть» по анкете")
def recommend(prefs: PreferencesIn, db: DbSession) -> list[GameRead]:
    data = prefs.model_dump(exclude={"limit"})
    return service.recommend(db, service.Preferences(**data), prefs.limit)
