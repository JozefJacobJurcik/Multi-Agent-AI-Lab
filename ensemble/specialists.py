"""What the Conductor asks of each specialist. Write a class with your role's method and hand an
instance to the Conductor in main.py; no base class is needed. How it is called: docs/conductor.md.

- feedback is None on the first ask. If what you return fails the Conductor's check, you are asked
  once more, with the reason as feedback. In the Night Round the Improviser is also asked once after
  the arena refuses its action, with the arena's reason.
- Return None when you have nothing to offer. If your method raises, the Conductor logs the
  traceback and falls back on a default that uses no tokens.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from store import Proposal, SharedStore

# Conductor.query: query("read", volume="v-4326", section=3) sends a query, files the reply in the
# store and returns it. Look in the store first: every examine and read is charged again.
Query = Callable[..., dict]


class Improviser(Protocol):
    def next_action(self, store: SharedStore, feedback: str | None) -> dict | None:
        """The Night Round's next walk, take or end, such as {"action": "walk", "exit": 2}."""


class Musicologist(Protocol):
    def propose(self, item: dict, store: SharedStore, query: Query,
                feedback: str | None) -> Proposal | None:
        """An answer to the question item, with the volumes it rests on as supporting."""


class Player(Protocol):
    def propose(self, item: dict, store: SharedStore, query: Query,
                feedback: str | None) -> Proposal | None:
        """The completed grid of the puzzle item as answer, checked against its rule; None skips it."""
