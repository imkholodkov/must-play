"""Общие схемы: ссылка на справочник и страница списка."""

from pydantic import BaseModel, ConfigDict, Field


class NamedRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class NamedCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Roguelike"])


class Page[T](BaseModel):
    items: list[T]
    total: int = Field(examples=[30690])
    limit: int = Field(examples=[20])
    offset: int = Field(examples=[0])
