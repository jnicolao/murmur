"""Whether Murmur has earned the right to say anything about a trend.

The product rule, from the design doc: never tell someone how they feel. Show
both lines, and say something in words only when the estimate and the person's
own check-in move the same way. When they disagree, the chart still shows
both and the text says nothing, because the person is the authority on their
own week and a confident sentence built on a disagreeing estimate is worse
than silence.

Everything here describes how someone *sounded*, never how they *are*.
"""

from __future__ import annotations

from dataclasses import dataclass

# Below this many readings a window is noise, not a week.
MIN_CHECK_INS = 3
MIN_UTTERANCES = 3

# Movement smaller than this is not worth a sentence. Self-report runs 1 to 5,
# estimated valence runs -1 to 1, so they need separate thresholds.
MOOD_THRESHOLD = 0.4
VALENCE_THRESHOLD = 0.12


@dataclass(frozen=True)
class Window:
    self_mood: float | None
    est_valence: float | None
    check_ins: int
    utterances: int

    @property
    def usable(self) -> bool:
        return (
            self.self_mood is not None
            and self.est_valence is not None
            and self.check_ins >= MIN_CHECK_INS
            and self.utterances >= MIN_UTTERANCES
        )


@dataclass(frozen=True)
class Trend:
    text: str | None
    reason: str  # why there is or is not a sentence, for the panel and tests


def describe(recent: Window, earlier: Window) -> Trend:
    """One sentence about the last stretch, or none."""
    if not recent.usable or not earlier.usable:
        return Trend(None, "not enough entries yet")

    mood_delta = recent.self_mood - earlier.self_mood
    valence_delta = recent.est_valence - earlier.est_valence

    mood_moved = abs(mood_delta) >= MOOD_THRESHOLD
    valence_moved = abs(valence_delta) >= VALENCE_THRESHOLD

    if not mood_moved and not valence_moved:
        return Trend(None, "steady")

    if not (mood_moved and valence_moved):
        return Trend(None, "only one of the two moved")

    if (mood_delta > 0) != (valence_delta > 0):
        # The person says one thing and the estimate says another. They win,
        # and Murmur keeps quiet.
        return Trend(None, "your check-ins and how you sounded disagree")

    if mood_delta > 0:
        return Trend("You have sounded lighter this week than last.", "agree, upward")
    return Trend("You have sounded flatter this week than last.", "agree, downward")
