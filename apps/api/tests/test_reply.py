"""Splitting the reply from its affect block. No model needed, so this runs in CI."""

from __future__ import annotations

from murmur.llm.reply import Affect, ReplyStream, parse

BLOCK = '<affect>{"valence": -0.4, "arousal": 0.2, "labels": ["tired"]}'


def spoken_of(tokens: list[str]) -> tuple[str, Affect | None]:
    stream = ReplyStream(tokens)
    return "".join(stream.spoken()), stream.affect


def test_the_block_never_reaches_the_spoken_text():
    text, affect = spoken_of(["That sounds heavy. ", BLOCK])
    assert text.strip() == "That sounds heavy."
    assert "affect" not in text and "{" not in text
    assert affect.valence == -0.4


def test_a_sentinel_split_across_tokens_still_holds():
    # The case that would otherwise leak JSON into the speech synthesiser.
    text, affect = spoken_of(["Good. ", "<aff", "ect>", '{"valence": 0.5, "arousal": 0.1}'])
    assert text.strip() == "Good."
    assert affect.valence == 0.5


def test_a_reply_with_no_block_is_passed_through_whole():
    text, affect = spoken_of(["Just words. ", "Nothing else."])
    assert text == "Just words. Nothing else."
    assert affect is None


def test_text_that_merely_starts_like_the_sentinel_is_not_swallowed():
    text, affect = spoken_of(["I felt <", "underwhelmed", " by it."])
    assert text == "I felt <underwhelmed by it."
    assert affect is None


def test_malformed_json_costs_the_reading_not_the_reply():
    text, affect = spoken_of(["Fine. ", "<affect>{not json at all"])
    assert text.strip() == "Fine."
    assert affect is None


def test_labels_are_lowercased_and_capped_at_two():
    affect = parse('{"valence": 0, "arousal": 0, "labels": ["Tired", "WORN OUT", "third"]}')
    assert affect.labels == ("tired", "worn out")


def test_junk_labels_are_dropped_without_losing_the_reading():
    affect = parse('{"valence": 0.1, "arousal": 0.2, "labels": [42, "ok", "!!!"]}')
    assert affect.labels == ("ok",)
    assert affect.valence == 0.1


def test_values_outside_the_scale_are_clamped_to_it():
    affect = parse('{"valence": 1.9, "arousal": -3.0, "labels": []}')
    assert affect.valence == 1.0
    assert affect.arousal == -1.0


def test_a_reading_without_numbers_is_no_reading():
    assert parse('{"labels": ["tired"]}') is None
    assert parse('{"valence": "very bad", "arousal": 0}') is None


def test_booleans_are_not_numbers():
    assert parse('{"valence": true, "arousal": 0.2}') is None


def test_the_row_shape_matches_the_columns():
    row = Affect(-0.4, 0.2, ("tired",)).as_row()
    assert set(row) == {"valence_text", "arousal_text", "labels_text"}
    assert row["labels_text"] == ["tired"]
