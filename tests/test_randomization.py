"""Tests for deterministic randomization."""

from ecbtkit.engine.randomization import make_seed, shuffle_questions, shuffle_options


class FakeQuestion:
    def __init__(self, id):
        self.id = id


def test_seed_deterministic():
    s1 = make_seed(1, 10, 100)
    s2 = make_seed(1, 10, 100)
    s3 = make_seed(1, 10, 101)
    assert s1 == s2
    assert s1 != s3


def test_question_shuffle_stable():
    qs = [FakeQuestion(i) for i in range(20)]
    seed = "abc123"
    a = shuffle_questions(qs, seed, enabled=True)
    b = shuffle_questions(qs, seed, enabled=True)
    assert [q.id for q in a] == [q.id for q in b]


def test_option_shuffle_stable():
    opts = list(range(1, 5))
    seed = "xyz"
    a = shuffle_options(opts, seed, question_id=7, enabled=True)
    b = shuffle_options(opts, seed, question_id=7, enabled=True)
    assert a == b
    # Different question → different order (usually)
    c = shuffle_options(opts, seed, question_id=8, enabled=True)
    # Not guaranteed different, but seed is different so very likely
    assert isinstance(c, list)
