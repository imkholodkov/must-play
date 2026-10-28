"""Бизнес-правила рейтинга: чистые функции без БД.

1. Индекс всех времён: оценка прессы и оценка игроков с весами.
2. Допуск в рейтинг: достаточно голосов игроков.
3. Флаг расхождения прессы и игроков.
4. Переходы статусов must play.
"""

import math
from dataclasses import dataclass

Z_95 = 1.96
MIN_VOTES = 50  # порог из лабы 6: при меньшем числе голосов доля положительных слишком шумная
MIN_CRITIC_REVIEWS = 2  # одна оценка прессы — ещё не мнение прессы
CRITIC_WEIGHT = 0.4
PLAYER_WEIGHT = 0.6
# Пресса в среднем на 7 пунктов щедрее игроков на тех же играх (85,4 против 78,3 на полном датасете):
# поправка убирает эту систематическую разницу перед смешиванием и сравнением
CRITIC_OFFSET = 7.0
DIVERGENCE_POINTS = 20
# Пороги по распределению индекса: 95 — около 97-го перцентиля, в must play попадают верхние ~4% игр
MUST_PLAY_IN = 95.0
MUST_PLAY_OUT = 93.0  # ниже порога входа, чтобы игра не прыгала туда-обратно при каждом пересчёте

CANDIDATE, IN_LIST, DROPPED = "candidate", "in_list", "dropped"


def wilson_lower_bound(positive: int, negative: int, z: float = Z_95) -> float | None:
    """Нижняя граница доверительного интервала Уилсона для доли положительных, 0–100.

    3 голоса «за» из 3 дают около 44, а 9 000 из 10 000 — около 89: мало голосов не выводит игру наверх.
    """
    n = positive + negative
    if n == 0:
        return None
    p = positive / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return round((centre - margin) / (1 + z * z / n) * 100, 2)


@dataclass(frozen=True)
class Score:
    player_score: float | None
    critic_score: float | None
    index_score: float | None
    is_eligible: bool
    divergence: str | None


def score_game(positive: int, negative: int, critic_avg: float | None, critic_count: int) -> Score:
    """Посчитать оценки одной игры по правилам 1–3.

    critic_score сохраняется как есть (средняя оценка прессы), а в индекс и сравнение
    с игроками идёт оценка с поправкой на щедрость прессы.
    """
    player = wilson_lower_bound(positive, negative)
    critic = round(critic_avg, 2) if critic_avg is not None and critic_count >= MIN_CRITIC_REVIEWS else None
    adjusted = max(critic - CRITIC_OFFSET, 0.0) if critic is not None else None
    eligible = positive + negative >= MIN_VOTES

    if player is None:
        index = None
    elif adjusted is None:
        index = player
    else:
        index = round(CRITIC_WEIGHT * adjusted + PLAYER_WEIGHT * player, 2)

    divergence = None
    share = positive / (positive + negative) * 100 if positive + negative else None
    if adjusted is not None and share is not None and eligible and abs(adjusted - share) > DIVERGENCE_POINTS:
        divergence = "overrated" if adjusted > share else "underrated"
    return Score(player, critic, index, eligible, divergence)


def next_must_play_status(current: str | None, index: float | None, eligible: bool) -> str | None:
    """Правило 4: candidate → in_list → dropped.

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
    if current == CANDIDATE:
        return IN_LIST if above_out else DROPPED
    return IN_LIST if above_out else DROPPED
