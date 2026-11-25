"""The two baselines of M1 §2.1, played on the same practice instances as the Improviser (measure.py).

DepthFirstWalker is the simplest version and the alternative: rules 1 and 2 as in the Improviser,
then the untried exits of the place found last, and no routing phase.
PromptImproviser is the plain-prompt baseline (S4 slide 30): the course model plays alone, given the
rules and the messages so far.
"""

from __future__ import annotations

import json

import llm
from improviser import RULES, Improviser, free, parse_action, unseen
from store import SharedStore

TEMPERATURE = 0.7  # sampled, so that seeds differ (M1 §2.1: mean and standard deviation over seeds)


class DepthFirstWalker(Improviser):
    def next_action(self, store: SharedStore, feedback: str | None) -> dict | None:
        if feedback is not None:
            return None  # no model to fall back on: the Conductor walks the nearest exit
        archive, trolley = store.map, store.observation["trolley"]
        here, space = trolley["position"], free(trolley)
        if here.get("volumes") and space:
            return self._take(here["volumes"][:space], "rule 1: as many as fit")
        if not space:
            return self._walk_to(store, archive.hall, "carrying", "rule 2: the trolley is full")
        exploring = unseen(store) > 0
        # Back to the place found last that still has work: volumes on its shelves, or an exit
        # to try while volumes are missing. Volumes here were taken by rule 1 already.
        for place in reversed(archive.exits):
            if archive.volumes.get(place):
                return self._walk_to(store, place, "carrying", f"depth-first: the volumes in {place}")
            untried = [number for number in archive.exits[place] if (place, number) not in archive.leads]
            if exploring and untried:
                why = f"depth-first: exit {untried[0]} of {place}"
                if place == archive.here:
                    return self._walk(store, untried[0], "exploring", why)
                return self._walk_to(store, place, "exploring", why)
        return self._home(store, "depth-first: nothing left to fetch")


class PromptImproviser:
    def __init__(self, seed: int = 7) -> None:
        self.seed = seed
        self.turns: list[str] = []  # each turn as JSON: the action sent and the arena's reply
        self.seen: dict | None = None  # the arena's message in the last turn recorded
        self.action: dict | None = None  # the model's last proposal

    def next_action(self, store: SharedStore, feedback: str | None) -> dict:
        if store.observation is not self.seen:  # a new message, a refusal by the arena included
            self.turns.append(json.dumps({"sent": store.last_action, "received": store.observation}))
            self.seen = store.observation
        prompt = f"{RULES}\n\nThe run so far, one turn a line:\n" + "\n".join(self.turns)
        if feedback is not None:
            prompt += f"\n\nYour action {json.dumps(self.action)} was not accepted: {feedback}"
        prompt += "\n\nReply with your next action, as JSON only."
        reply = llm.chat([{"role": "user", "content": prompt}], temperature=TEMPERATURE,
                         seed=self.seed, max_tokens=1000)
        self.action = parse_action(reply)
        # An unreadable reply goes to the Conductor's check like any action: it is refused there and
        # comes back once with the reason.
        return self.action if self.action is not None else {}
