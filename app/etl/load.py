"""Загрузка очищенных записей в PostgreSQL пачками, без дублей при повторном запуске."""

from sqlalchemy import Table, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.etl.transform import GameRecord
from app.models import Category, Developer, Game, Genre, Language, Tag
from app.models.catalog import game_categories, game_developers, game_genres, game_languages, game_tags

# Справочник → (модель, таблица связи, имя колонки справочника в таблице связи)
DICTIONARIES = {
    "genres": (Genre, game_genres, "genre_id"),
    "tags": (Tag, game_tags, "tag_id"),
    "categories": (Category, game_categories, "category_id"),
    "languages": (Language, game_languages, "language_id"),
    "developers": (Developer, game_developers, "developer_id"),
}
NAME_LIMITS = {"genres": 100, "tags": 100, "categories": 150, "languages": 100, "developers": 300}


class Loader:
    """Держит кэш справочников, чтобы не искать одно и то же имя в БД на каждой пачке."""

    def __init__(self, session: Session):
        self.session = session
        self.ids: dict[str, dict[str, int]] = {key: {} for key in DICTIONARIES}

    def load_batch(self, records: list[GameRecord]) -> tuple[int, int]:
        """Записать пачку игр со связями. Возвращает (новых, обновлённых)."""
        app_ids = [r.game["app_id"] for r in records]
        existing = set(self.session.scalars(select(Game.app_id).where(Game.app_id.in_(app_ids))))

        stmt = insert(Game).values([r.game for r in records])
        update_cols = {c: stmt.excluded[c] for c in records[0].game if c != "app_id"}
        self.session.execute(stmt.on_conflict_do_update(index_elements=["app_id"], set_=update_cols))

        for key, (model, link, column) in DICTIONARIES.items():
            self._replace_links(key, model, link, column, records, app_ids)
        return len(app_ids) - len(existing), len(existing)

    def _replace_links(self, key, model, link: Table, column: str, records, app_ids) -> None:
        limit = NAME_LIMITS[key]
        names = {name[:limit] for r in records for name in r.lists[key]}
        ids = self._ensure_names(key, model, names)
        # Связи игры перезаписываются целиком: повторный импорт не плодит дубли и убирает устаревшие
        self.session.execute(delete(link).where(link.c.app_id.in_(app_ids)))
        rows = {(r.game["app_id"], ids[name[:limit]]) for r in records for name in r.lists[key]}
        if rows:
            self.session.execute(link.insert(), [{"app_id": a, column: i} for a, i in rows])

    def _ensure_names(self, key, model, names: set[str]) -> dict[str, int]:
        cache = self.ids[key]
        missing = names - cache.keys()
        if missing:
            self.session.execute(
                insert(model).values([{"name": n} for n in missing]).on_conflict_do_nothing(index_elements=["name"])
            )
            for name, id_ in self.session.execute(select(model.name, model.id).where(model.name.in_(missing))):
                cache[name] = id_
        return cache
