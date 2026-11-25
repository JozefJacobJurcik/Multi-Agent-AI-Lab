"""The Conductor: plain code at the top of the Ensemble (M1 §2.2).

It holds the one arena connection, runs the loop and hands each decision to one specialist: the
Improviser moves the trolley, the Musicologist answers questions, the Player solves puzzles. Every
action is checked in code before it is sent (checks.py). What fails goes back once, with the reason;
then the Conductor sends the last proposal in the store if it is well-formed, else a default that
uses no tokens: a skip, or the nearest exit. In the Night Round an action the arena refuses goes
back to the Improviser once as well. Each action is logged with who decided it, why, its tokens and
its change in spent. Interface: docs/conductor.md.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import llm
from arena_client import ArenaClient
from checks import doubt, refusal
from specialists import Improviser, Musicologist, Player
from store import Proposal, SharedStore

log = logging.getLogger("conductor")

ASKS = 2  # the first ask, and one more with the reason when a check fails
DEFAULT_WALKS = 3  # nearest-exit defaults in a row; after that the Night Round is ended


@dataclass
class Decision:
    action: dict
    by: str  # the part that decided
    why: str  # the check's result, or why the Conductor fell back


class Conductor:
    def __init__(self, arena: ArenaClient, improviser: Improviser | None = None,
                 musicologist: Musicologist | None = None, player: Player | None = None) -> None:
        self.arena = arena
        self.store = SharedStore()
        self.store.observe(arena.observation, sent=None)
        self.improviser = improviser
        self.answerers = {"question": musicologist, "gate": player}  # a team of three gets no claims
        self.default_walks = 0
        self.retried = False  # the last action was the Improviser's second try after an arena refusal

    def play(self) -> dict:
        """Play the run to its end and return the arena's last message."""
        while not self.arena.done:
            spent_before, tokens_before = self.store.spent, llm.tokens
            decision = self._decide()
            message = self.arena.step(decision.action)
            self.store.observe(message, sent=decision.action)
            spent = {meter: n - spent_before.get(meter, 0) for meter, n in self.store.spent.items()}
            log.info("decision %s", json.dumps({
                "by": decision.by, "why": decision.why, "action": decision.action,
                "outcome": message.get("outcome"), "tokens": llm.tokens - tokens_before,
                "spent": spent}))
        return self.arena.observation

    def query(self, name: str, **arguments) -> dict:
        """A specialist's query: sent to the arena, its reply filed in the store and returned."""
        reply = self.arena.query(name, **arguments)
        self.store.observe(reply, sent={"query": name, **arguments})
        return reply

    def _decide(self) -> Decision:
        if self.store.quest["id"] == "N":
            return self._move()
        items = self.store.open_items()
        if not items:
            return Decision({"action": "end"}, "Conductor", "no open item")
        return self._answer(items[0])

    def _answer(self, item_id: str) -> Decision:
        """A proposal that passes the checks, else the last proposal if well-formed, else a skip."""
        if self._was_refused() and self.store.last_action.get("to") == item_id:
            return Decision(skip_action(item_id), "Conductor", "the arena refused the answer")
        answerer = self.answerers.get(item_id.split("-")[0])
        item = self.store.item(item_id)
        feedback = None
        for _ in range(ASKS):
            proposal = self._ask(answerer, "propose", item, self.store, self.query, feedback)
            if proposal is None:
                break
            if not isinstance(proposal, Proposal):
                feedback = "propose returns a Proposal or None"
                continue
            action = answer_action(item_id, proposal)
            feedback = refusal(action, self.store)
            if feedback is not None:
                continue
            self.store.propose(item_id, proposal)  # well-formed: sent if no later proposal passes
            feedback = doubt(item_id, proposal, self.store)
            if feedback is None:
                return Decision(action, proposal.author, "passed the checks")
        best = self.store.best(item_id)
        if isinstance(best, Proposal) and refusal(answer_action(item_id, best), self.store) is None:
            why = f"best so far: {feedback or 'no new proposal'}"
            return Decision(answer_action(item_id, best), best.author, why)
        return Decision(skip_action(item_id), "Conductor", feedback or "no proposal")

    def _move(self) -> Decision:
        """The Improviser's checked action, else the nearest exit, else the end (DEFAULT_WALKS).

        After the arena refuses an action, the Improviser is asked once, with the arena's reason. If
        the arena refuses the action it gives then as well, the Conductor walks the nearest exit.
        """
        refused = self._was_refused()
        feedback, asks = None, ASKS
        if refused:
            code = self.store.observation["outcome"]["invalid"].get("code")
            feedback = f"the arena refused the last action: {code}"
            asks = 0 if self.retried else 1
        self.retried = False
        for _ in range(asks):
            action = self._ask(self.improviser, "next_action", self.store, feedback)
            if action is None:
                break
            feedback = refusal(action, self.store)
            if feedback is None:
                self.default_walks, self.retried = 0, refused
                return Decision(action, "Improviser", "passed the checks")
        self.default_walks += 1
        if self.default_walks > DEFAULT_WALKS:
            return Decision({"action": "end"}, "Conductor", "the Improviser keeps failing")
        exits = self.store.observation["trolley"]["position"]["exits"]
        nearest = min(exits, key=lambda e: e["length"])
        return Decision({"action": "walk", "exit": nearest["exit"]}, "Conductor",
                        f"nearest exit: {feedback or 'no action'}")

    def _ask(self, part: object, method: str, *args) -> Any:
        """Call a specialist's method; None if the specialist is missing or raises."""
        if part is None:
            return None
        try:
            return getattr(part, method)(*args)
        except Exception:
            log.exception("%s.%s failed", type(part).__name__, method)
            return None

    def _was_refused(self) -> bool:
        """Whether the arena refused the last action."""
        return "invalid" in self.store.observation.get("outcome", {})


def answer_action(item_id: str, proposal: Proposal) -> dict:
    action = {"action": "answer", "to": item_id, "answer": proposal.answer}
    if item_id.startswith("question"):
        action["supporting"] = proposal.supporting
    return action


def skip_action(item_id: str) -> dict:
    return {"action": "skip", "to": item_id}
