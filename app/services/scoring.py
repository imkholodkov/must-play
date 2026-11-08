"""Бизнес-правила рейтинга: чистые функции без БД.

1. Индекс всех времён: байесовская оценка игроков и оценка прессы с весами.
2. Допуск в рейтинг: достаточно голосов, это игра, а не программа, и это не дубль другой записи.
3. Флаг расхождения прессы и игроков.
4. Переходы статусов must play.
"""

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass

Z_95 = 1.96
MIN_VOTES = 50  # при меньшем числе голосов доля положительных слишком шумная
# Байесовская оценка, как в IMDb Top 250: пока голосов меньше ~20 000, оценка игры тянется к средней по каталогу.
# Так наверх поднимаются игры, которые и любят, и знают, а не нишевые 99% от пары сотен фанатов
PRIOR_VOTES = 20_000
MIN_CRITIC_REVIEWS = 2  # одна оценка прессы — ещё не мнение прессы
CRITIC_WEIGHT = 0.4
PLAYER_WEIGHT = 0.6
# Пресса в среднем на 7 пунктов щедрее игроков (85,4 против 78,3 на полном датасете).
# Поправка нужна только для флага расхождения: в индексе она наказывала бы игры, которые хвалят все
CRITIC_OFFSET = 7.0
DIVERGENCE_POINTS = 20
# В must play — только игры, которые знают многие
MUST_PLAY_MIN_VOTES = 10_000
MUST_PLAY_IN = 93.0  # около сотни игр: короткий список, который реально пройти
MUST_PLAY_OUT = 92.0  # ниже порога входа, чтобы игра не прыгала туда-обратно при каждом пересчёте

# Жанры Steam для программ и видео: Wallpaper Engine или Aseprite — не игры, им не место в рейтинге
NON_GAME_GENRES = {
    "360 Video",
    "Accounting",
    "Animation & Modeling",
    "Audio Production",
    "Design & Illustration",
    "Documentary",
    "Education",
    "Game Development",
    "Movie",
    "Photo Editing",
    "Short",
    "Software Training",
    "Tutorial",
    "Utilities",
    "Video Production",
    "Web Publishing",
}

CANDIDATE, IN_LIST, DROPPED = "candidate", "in_list", "dropped"


def wilson_lower_bound(positive: int, negative: int, z: float = Z_95) -> float | None:
    """Нижняя граница доверительного интервала Уилсона для доли положительных, 0–100.

    В рейтинге больше не используется, но по ней ML-модель hit определяет «хит».
    """
    n = positive + negative
    if n == 0:
        return None
    p = positive / n
    # формула Уилсона: чем меньше голосов, тем сильнее занижаем долю положительных
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return round((centre - margin) / (1 + z * z / n) * 100, 2)


def positive_share(positive: int, negative: int) -> float | None:
    total = positive + negative
    return positive / total * 100 if total else None


def bayesian_score(positive: int, negative: int, prior_mean: float, prior_votes: int = PRIOR_VOTES) -> float | None:
    """Доля положительных, взвешенная с средней по каталогу: v/(v+m)·доля + m/(v+m)·средняя, 0–100."""
    votes = positive + negative
    if votes == 0:
        return None
    share = positive / votes * 100
    return round((votes * share + prior_votes * prior_mean) / (votes + prior_votes), 2)


def is_game(genres: Iterable[str]) -> bool:
    return not NON_GAME_GENRES.intersection(genres)


def title_key(name: str) -> str:
    """Ключ названия для поиска дублей: регистр, ™, ® и пунктуация не важны."""
    return re.sub(r"[^\w]+", "", name.casefold())


def primary_ids(games: Iterable[tuple[int, str, int]]) -> set[int]:
    """Из записей (app_id, название, голосов) с одинаковым названием оставить ту, где больше голосов.

    В Steam одна игра бывает под несколькими app_id (например, у Portal 2 их два), в рейтинге она нужна один раз.
    """
    best: dict[str, tuple[int, int]] = {}
    for app_id, name, votes in games:
        key = title_key(name)
        if key not in best or votes > best[key][1]:
            best[key] = (app_id, votes)
    return {app_id for app_id, _ in best.values()}


@dataclass(frozen=True)
class Score:
    player_score: float | None
    critic_score: float | None
    index_score: float | None
    is_eligible: bool
    divergence: str | None


def score_game(
    positive: int,
    negative: int,
    critic_avg: float | None,
    critic_count: int,
    prior_mean: float,
    counts_as_game: bool = True,
) -> Score:
    """Посчитать оценки одной игры по правилам 1–3.

    counts_as_game — это игра, а не программа, и не дубль другой записи; иначе в рейтинг не допускается.
    """
    player = bayesian_score(positive, negative, prior_mean)
    critic = round(critic_avg, 2) if critic_avg is not None and critic_count >= MIN_CRITIC_REVIEWS else None
    eligible = counts_as_game and positive + negative >= MIN_VOTES

    if player is None:
        index = None
    elif critic is None:
        index = player
    else:
        index = round(CRITIC_WEIGHT * critic + PLAYER_WEIGHT * player, 2)

    # для флага сравниваем прессу с поправкой и простую долю положительных: так расхождение проще объяснить
    divergence = None
    share = positive_share(positive, negative)
    if critic is not None and share is not None and eligible:
        adjusted = critic - CRITIC_OFFSET
        if abs(adjusted - share) > DIVERGENCE_POINTS:
            divergence = "overrated" if adjusted > share else "underrated"
    return Score(player, critic, index, eligible, divergence)


def next_must_play_status(current: str | None, index: float | None, eligible: bool) -> str | None:
    """Правило 4: candidate → in_list → dropped.

    eligible — игра допущена в рейтинг и набрала MUST_PLAY_MIN_VOTES голосов.
    - игра впервые выше порога входа — кандидат;
    - кандидат, удержавшийся выше порога выхода в следующем пересчёте, — в списке;
    - игра из списка (или кандидат) ниже порога выхода — выбыла;
    - выбывшая игра снова выше порога входа — снова кандидат.
    Возвращает None, если игра в must play не участвует.
    """
    above_in = eligible and index is not None and index >= MUST_PLAY_IN
    above_out = eligible and index is not None and index >= MUST_PLAY_OUT
    if current in (None, DROPPED):
        return CANDIDATE if above_in else current
    # кандидату нужен второй пересчёт подряд выше порога выхода, только тогда он попадает в список
    if current == CANDIDATE:
        return IN_LIST if above_out else DROPPED
    return IN_LIST if above_out else DROPPED
