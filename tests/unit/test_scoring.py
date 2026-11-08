import pytest

from app.services.scoring import (
    CANDIDATE,
    DROPPED,
    IN_LIST,
    MUST_PLAY_IN,
    MUST_PLAY_OUT,
    bayesian_score,
    is_game,
    next_must_play_status,
    primary_ids,
    score_game,
    wilson_lower_bound,
)

BETWEEN = (MUST_PLAY_IN + MUST_PLAY_OUT) / 2
PRIOR = 80.0


def test_wilson_few_votes_do_not_beat_many():
    assert wilson_lower_bound(3, 0) < wilson_lower_bound(9000, 1000)


def test_bayesian_pulls_niche_games_to_catalog_mean():
    niche = bayesian_score(990, 10, PRIOR)  # 99% у тысячи человек
    famous = bayesian_score(800_000, 35_000, PRIOR)  # 96% у 835 тысяч

    assert niche < famous
    assert bayesian_score(0, 0, PRIOR) is None


def test_bayesian_with_huge_audience_is_close_to_share():
    assert bayesian_score(9_900_000, 100_000, PRIOR) == pytest.approx(99, abs=0.1)


def test_index_combines_raw_press_and_players():
    score = score_game(900_000, 100_000, critic_avg=80.0, critic_count=3, prior_mean=PRIOR)

    assert score.is_eligible
    assert score.critic_score == 80.0
    assert score.index_score == round(0.4 * 80.0 + 0.6 * score.player_score, 2)


def test_praised_by_everyone_is_not_pulled_down_by_press():
    score = score_game(960_000, 40_000, critic_avg=97.0, critic_count=5, prior_mean=PRIOR)

    assert score.index_score >= score.player_score


def test_single_critic_review_is_ignored():
    score = score_game(900, 100, critic_avg=10.0, critic_count=1, prior_mean=PRIOR)

    assert score.critic_score is None
    assert score.index_score == score.player_score


def test_not_eligible_with_few_votes():
    assert not score_game(30, 5, None, 0, PRIOR).is_eligible


def test_not_eligible_when_not_a_game():
    assert not score_game(9000, 100, None, 0, PRIOR, counts_as_game=False).is_eligible


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
    assert score_game(positive, negative, critic, 3, PRIOR).divergence == expected


@pytest.mark.parametrize(
    ("genres", "expected"),
    [({"Action", "Indie"}, True), ({"Casual", "Utilities"}, False), ({"Animation & Modeling"}, False), (set(), True)],
)
def test_is_game(genres, expected):
    assert is_game(genres) is expected


def test_primary_ids_keep_most_voted_duplicate():
    games = [
        (620, "Portal 2", 433_510),
        (659, "Portal 2", 155_440),
        (1, "The Last of Us™ Part I", 10),
        (2, "Celeste", 5),
    ]

    assert primary_ids(games) == {620, 1, 2}


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
