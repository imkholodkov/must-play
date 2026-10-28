import pytest

from app.services.scoring import (
    CANDIDATE,
    CRITIC_OFFSET,
    DROPPED,
    IN_LIST,
    MUST_PLAY_IN,
    MUST_PLAY_OUT,
    next_must_play_status,
    score_game,
    wilson_lower_bound,
)

BETWEEN = (MUST_PLAY_IN + MUST_PLAY_OUT) / 2


def test_few_votes_do_not_beat_many():
    assert wilson_lower_bound(3, 0) < wilson_lower_bound(9000, 1000)


def test_wilson_without_votes():
    assert wilson_lower_bound(0, 0) is None


def test_index_combines_adjusted_press_and_players():
    score = score_game(positive=900, negative=100, critic_avg=80.0, critic_count=3)

    assert score.is_eligible
    assert score.critic_score == 80.0  # хранится без поправки
    assert score.index_score == round(0.4 * (80.0 - CRITIC_OFFSET) + 0.6 * score.player_score, 2)


def test_single_critic_review_is_ignored():
    score = score_game(positive=900, negative=100, critic_avg=10.0, critic_count=1)

    assert score.critic_score is None
    assert score.index_score == score.player_score


def test_not_eligible_with_few_votes():
    assert not score_game(positive=30, negative=5, critic_avg=None, critic_count=0).is_eligible


@pytest.mark.parametrize(
    ("positive", "negative", "critic", "expected"),
    [
        (500, 500, 90.0, "overrated"),  # игроки 50%, пресса 90 → 83 с поправкой
        (950, 50, 70.0, "underrated"),  # игроки 95%, пресса 70 → 63
        (800, 200, 85.0, None),  # 80% против 78 с поправкой
        (700, 300, 95.0, None),  # 70% против 88: без поправки было бы «переоценена»
    ],
)
def test_divergence_flag(positive, negative, critic, expected):
    assert score_game(positive, negative, critic, critic_count=3).divergence == expected


@pytest.mark.parametrize(
    ("current", "index", "eligible", "expected"),
    [
        (None, MUST_PLAY_IN, True, CANDIDATE),  # впервые на пороге входа
        (None, BETWEEN, True, None),  # между порогами — не участвует
        (None, 99.0, False, None),  # мало голосов
        (CANDIDATE, BETWEEN, True, IN_LIST),  # удержалась выше порога выхода
        (CANDIDATE, MUST_PLAY_OUT - 1, True, DROPPED),
        (IN_LIST, BETWEEN, True, IN_LIST),  # между порогами остаётся в списке
        (IN_LIST, MUST_PLAY_OUT - 0.01, True, DROPPED),
        (DROPPED, BETWEEN, True, DROPPED),  # для возврата нужен порог входа
        (DROPPED, MUST_PLAY_IN + 1, True, CANDIDATE),
    ],
)
def test_must_play_transitions(current, index, eligible, expected):
    assert next_must_play_status(current, index, eligible) == expected
