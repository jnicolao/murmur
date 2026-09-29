"""When Murmur is allowed to say something about a trend, and when it is not."""

from __future__ import annotations

from murmur.affect.trend import Window, describe

FULL = {"check_ins": 5, "utterances": 12}


def window(mood: float | None, valence: float | None, **over) -> Window:
    counts = FULL | over
    return Window(mood, valence, counts["check_ins"], counts["utterances"])


def test_says_nothing_before_there_are_enough_entries():
    trend = describe(window(4.0, 0.3, check_ins=1), window(2.0, -0.3))
    assert trend.text is None
    assert "enough" in trend.reason


def test_says_nothing_when_the_week_was_steady():
    assert describe(window(3.0, 0.0), window(3.05, 0.01)).text is None


def test_says_nothing_when_only_the_estimate_moved():
    trend = describe(window(3.0, 0.4), window(3.0, -0.4))
    assert trend.text is None
    assert "one of the two" in trend.reason


def test_says_nothing_when_the_person_and_the_estimate_disagree():
    # The check-ins went up, the voice went down. The person wins.
    trend = describe(window(4.2, -0.3), window(3.0, 0.3))
    assert trend.text is None
    assert "disagree" in trend.reason


def test_speaks_only_when_both_agree_it_got_harder():
    trend = describe(window(2.2, -0.35), window(3.4, 0.15))
    assert trend.text == "You have sounded flatter this week than last."


def test_speaks_only_when_both_agree_it_got_lighter():
    trend = describe(window(4.1, 0.4), window(2.8, -0.1))
    assert trend.text == "You have sounded lighter this week than last."


def test_never_claims_to_know_how_someone_feels():
    for recent, earlier in [
        (window(2.2, -0.35), window(3.4, 0.15)),
        (window(4.1, 0.4), window(2.8, -0.1)),
    ]:
        text = describe(recent, earlier).text
        assert "sounded" in text
        for claim in ("you are", "you feel", "you're", "depressed", "anxious"):
            assert claim not in text.lower()


def test_a_missing_estimate_is_not_treated_as_zero():
    assert describe(window(4.0, None), window(2.0, 0.2)).text is None
