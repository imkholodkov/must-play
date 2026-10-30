"""Схемы игр: раздельные для создания, обновления и ответа."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import NamedRef


class GameBase(BaseModel):
    name: str = Field(min_length=1, max_length=500, examples=["Celeste"])
    release_date: date | None = Field(default=None, examples=["2018-01-25"])
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2, examples=["19.99"])
    is_free: bool = False
    windows: bool | None = True
    mac: bool | None = None
    linux: bool | None = None
    short_description: str | None = Field(default=None, examples=["Help Madeline survive her inner demons."])


class GameCreate(GameBase):
    app_id: int = Field(gt=0, examples=[504230])
    genres: list[str] = Field(default_factory=list, examples=[["Action", "Indie"]])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "app_id": 504230,
                "name": "Celeste",
                "release_date": "2018-01-25",
                "price": "19.99",
                "genres": ["Action", "Indie"],
            }
        }
    )


class GameUpdate(BaseModel):
    """Частичное обновление: передаются только меняемые поля."""

    name: str | None = Field(default=None, min_length=1, max_length=500)
    release_date: date | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    is_free: bool | None = None
    windows: bool | None = None
    mac: bool | None = None
    linux: bool | None = None
    short_description: str | None = None
    genres: list[str] | None = None

    model_config = ConfigDict(json_schema_extra={"example": {"price": "9.99", "genres": ["Platformer"]}})

    @model_validator(mode="after")
    def not_empty(self) -> "GameUpdate":
        if not self.model_fields_set:
            raise ValueError("нужно передать хотя бы одно поле")
        return self


class ScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    index_score: float | None
    player_score: float | None
    critic_score: float | None
    critic_reviews_count: int
    is_eligible: bool
    divergence: str | None


class GameRead(GameBase):
    model_config = ConfigDict(from_attributes=True)

    app_id: int
    positive: int
    negative: int
    owners_min: int | None
    owners_max: int | None
    metacritic_score: int | None
    header_image: str | None
    genres: list[NamedRef]
    score: ScoreRead | None = None


class CriticReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    outlet: str | None
    quote: str
    raw_score: str | None
    score: int | None


class GameDetail(GameRead):
    tags: list[NamedRef]
    categories: list[NamedRef]
    languages: list[NamedRef]
    developers: list[NamedRef]
    reviews: list[CriticReviewRead] = []
    must_play_status: str | None = None
