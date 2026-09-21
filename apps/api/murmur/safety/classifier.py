"""Stage two of the crisis check: a small yes/no call to the local model.

Catches indirect phrasings the list cannot: "I've written letters to everyone",
"I've been giving my things away". Constrained to a single token so it costs
tens of milliseconds rather than a full generation.
"""

from __future__ import annotations

from murmur.llm.client import Ollama

CLASSIFIER_VERSION = "crisis-v2"

SYSTEM = """\
You screen journal entries for one thing only: whether the person may be at \
risk of suicide or self-harm. You are not deciding how serious it is. You are \
deciding whether a human being should be involved.

Answer YES if the entry shows any recognised warning sign, however calmly it \
is worded:
- Wanting to die, not wanting to wake up, or not wanting to exist.
- Any mention of ending their life or harming themselves.
- Looking into a method, or counting, gathering, or obtaining the means.
- Going to or lingering at a place people use to end their life, such as a \
bridge, a cliff, or a track.
- Saying goodbye: writing letters to loved ones, telling people what they \
mean to them as though for the last time.
- Putting affairs in order, giving belongings away, settling debts, making \
peace, or saying there is nothing left to sort out.
- Cancelling future plans, or saying they will not be around, will not need \
something, or will not be here much longer.
- Saying others would be better off without them, or that they are a burden.
- A sudden, unexplained calm or relief after a period of despair.

Answer NO for ordinary distress, however severe it sounds: sadness, grief, \
exhaustion, burnout, anger, anxiety, loneliness, self-criticism, numbness, \
feeling like a failure, hopelessness about a job or a relationship, or \
violent figures of speech such as "this is killing me" or "I could kill for \
a coffee".

The cost of a missed YES is far higher than the cost of a wrong YES. When an \
entry genuinely sits between the two lists, answer YES.

Reply with exactly one word: YES or NO.\
"""


class CrisisClassifier:
    def __init__(self, llm: Ollama | None = None) -> None:
        self.llm = llm or Ollama()

    def flags(self, transcript: str) -> bool:
        answer = ""
        for chunk in self.llm.stream(
            SYSTEM, transcript, timeout=30.0, num_predict=4, temperature=0.0
        ):
            answer += chunk
            if len(answer) > 12:
                break
        return answer.strip().upper().startswith("YES")
