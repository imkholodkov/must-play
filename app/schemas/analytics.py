"""Схемы ответов аналитических эндпоинтов."""

from pydantic import BaseModel, Field


class GenreStats(BaseModel):
    genre: str = Field(examples=["RPG"])
    games: int = Field(description="Допущенных в рейтинг игр", examples=[6866])
    avg_index: float = Field(examples=[76.0])
    avg_positive_share: float = Field(description="Средняя доля положительных отзывов, %", examples=[80.3])
    free_share: float = Field(description="Доля бесплатных игр, %", examples=[7.4])


class YearStats(BaseModel):
    year: int = Field(examples=[2018])
    releases: int
    free_share: float = Field(description="Доля бесплатных, %")
    avg_price: float | None = Field(description="Средняя цена платных игр")
    avg_index: float | None = Field(description="Средний индекс допущенных игр")


class DivergenceItem(BaseModel):
    app_id: int
    name: str
    critic_score: float = Field(description="Оценка прессы без поправки")
    positive_share: float = Field(description="Доля положительных отзывов игроков, %")
    gap: float = Field(description="Пресса минус игроки, пункты")


class OutletStats(BaseModel):
    outlet: str = Field(examples=["IGN"])
    reviews: int
    avg_score: float
    vs_average: float = Field(description="Отклонение от средней оценки всех изданий, пункты")
