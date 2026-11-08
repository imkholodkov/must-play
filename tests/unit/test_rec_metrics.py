import pytest

from app.services.rec_metrics import catalog_coverage, informative_tags, intra_list_diversity, tag_precision


def test_informative_tags_drop_common():
    tokens = {i: ["g:RPG", "t:Indie", f"t:rare{i}"] for i in range(10)}

    tags = informative_tags(tokens)

    assert tags[0] == {"t:rare0"}  # Indie есть у всех — не считается


def test_tag_precision_counts_shared_tags():
    tags = {1: {"t:a"}, 2: {"t:a"}, 3: {"t:b"}}

    assert tag_precision(lambda a: {1: [2, 3], 2: [1], 3: [1]}[a], tags) == pytest.approx(0.5)


def test_tag_precision_empty():
    assert tag_precision(lambda a: [], {1: {"t:a"}}) == 0.0


def test_catalog_coverage():
    assert catalog_coverage({1: [2], 2: [1]}, {1, 2, 3, 4}) == 0.5


def test_diversity_identical_vs_different():
    same = {"a": ["g:RPG"], "b": ["g:RPG"], "c": ["g:Puzzle"], "d": ["g:Racing"]}

    assert intra_list_diversity({"x": ["a", "b"]}, {**same, "x": ["g:RPG"]}) == pytest.approx(0.0)
    assert intra_list_diversity({"x": ["c", "d"]}, {**same, "x": ["g:RPG"]}) == pytest.approx(1.0)
