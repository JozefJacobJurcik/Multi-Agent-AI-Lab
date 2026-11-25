"""The Improviser: plays the Night Round (M1 §2.1). The Conductor asks it for every action.

It plans on the map in the shared store (archive_map.py). Until every volume has been seen, the first
of rules 1 to 3 that applies decides:

1. In a room, take as many volumes as fit.
2. With a full trolley, take the shortest known path to the reading hall.
3. Otherwise walk the cheapest untried exit: the known distance to it plus its own length.

4. Once every volume has been seen, or no exit is left to try, the remaining trips are planned
   (routing.py), and the plan decides every take. With no exit left to try, a volume not seen yet
   cannot be reached, and rule 3 would have nothing to walk.

The model is only a fallback. The Conductor asks once more, with the reason, when the arena refuses
an action or its own check does. The model is then shown the rules, the quest, the latest message
and the actions allowed now, and its reply is used only if it is one of them. Otherwise the
Conductor walks the nearest exit, and the rules take over again.
"""

from __future__ import annotations

import json
import logging

import llm
import routing
from store import SharedStore

log = logging.getLogger("improviser")

# The Night Round for the model, after README §3.1, §4 and §7.2.
RULES = """\
You play the Night Round of the Archive Games. A trolley starts in the reading hall of a dark \
archive. Bring every volume to the reading hall, walking as short a distance as you can.
- There is no map. An exit shows only the length of its corridor, not where it leads.
- {"action": "walk", "exit": 2} walks the whole corridor of exit 2. In the reply, "move" says how \
far the trolley walked and by which exit it arrived ("via"): that exit leads back.
- {"action": "take", "volumes": ["v-1306"]} takes volumes from the shelves of the room the trolley \
stands in, no more than it has room for. Nothing can be put back.
- Arriving in the reading hall, the trolley puts everything it carries on the hall's shelves.
- {"action": "end"} ends the run where it stands; only the volumes in the reading hall count.
- quest.total is the number of volumes, trolley.capacity how many the trolley holds."""


class Improviser:
    def __init__(self) -> None:
        self.plan: list[routing.Stop] = []
        self.walked = {"exploring": 0, "carrying": 0}  # by rule 3, and by rules 2 and 4 (M1 §2.1)

    def next_action(self, store: SharedStore, feedback: str | None) -> dict | None:
        if feedback is not None:
            return self._ask_model(store, feedback)
        if unseen(store) == 0 or not store.map.untried():
            return self._follow_plan(store)
        trolley = store.observation["trolley"]
        here, space = trolley["position"], free(trolley)
        if here.get("volumes") and space:
            return self._take(here["volumes"][:space], "rule 1: as many as fit")
        if not space:
            return self._walk_to(store, store.map.hall, "carrying", "rule 2: the trolley is full")
        return self._explore(store)

    def _explore(self, store: SharedStore) -> dict:
        """Rule 3: the untried exit with the least known distance to it plus its own length."""
        archive = store.map
        cost = {(place, number): archive.distance(archive.here, place) + length
                for place, number, length in archive.untried()}
        place, number = min(cost, key=cost.get)
        why = f"rule 3: the cheapest untried exit is {number} of {place}, {cost[place, number]} away"
        if place == archive.here:
            return self._walk(store, number, "exploring", why)
        return self._walk_to(store, place, "exploring", why)

    def _follow_plan(self, store: SharedStore) -> dict:
        """Rule 4: the next stop of the plan, made once every volume has been seen or no exit is left
        to try."""
        archive, trolley = store.map, store.observation["trolley"]
        if not self.plan:
            left = {room: len(volumes) for room, volumes in archive.volumes.items() if volumes}
            self.plan = routing.plan(archive.here, len(trolley["carrying"]), left,
                                     trolley["capacity"], archive.hall, archive.distance)
            log.info("rule 4: the plan is %s", self.plan)
        while self.plan:
            place, n = self.plan[0]
            if place != archive.here:
                return self._walk_to(store, place, "carrying", f"rule 4: on to {place}")
            self.plan.pop(0)
            volumes = trolley["position"].get("volumes", [])[:min(n, free(trolley))]
            if volumes:
                return self._take(volumes, "rule 4: as planned")
        # A take that fell short, one the arena refused or the model changed, leaves volumes behind
        # that the plan has passed: plan again. A new plan starts with a walk or a take.
        if any(archive.volumes.values()):
            return self._follow_plan(store)
        return self._home(store, f"rule 4: nothing left to fetch, {unseen(store)} not found")

    def _ask_model(self, store: SharedStore, feedback: str) -> dict | None:
        """The fallback: an action allowed now, as the model chooses it; None if its reply is none."""
        actions = allowed(store.observation["trolley"])
        prompt = (f"{RULES}\n\nThe quest: {json.dumps(store.quest)}\n"
                  f"The arena's latest message:\n{json.dumps(store.observation)}\n\n"
                  f"An action was refused: {feedback}\nThese actions are allowed now:\n"
                  + "\n".join(json.dumps(action) for action in actions)
                  + "\n\nReply with one of them, as JSON only.")
        reply = llm.chat([{"role": "user", "content": prompt}], temperature=0, seed=7, max_tokens=1000)
        action = parse_action(reply)
        if action in actions:
            log.info("the model chose %s", json.dumps(action))
            return action
        log.info("the model's reply is none of the allowed actions")
        return None

    def _home(self, store: SharedStore, why: str) -> dict:
        """Towards the reading hall, and the end of the run once there."""
        if store.map.here == store.map.hall:
            log.info("%s; end in the reading hall", why)
            return {"action": "end"}
        return self._walk_to(store, store.map.hall, "carrying", why)

    def _walk_to(self, store: SharedStore, place: str, purpose: str, why: str) -> dict:
        """The first exit of the shortest known path to the place."""
        return self._walk(store, store.map.first_exit(place), purpose, why)

    def _walk(self, store: SharedStore, number: int, purpose: str, why: str) -> dict:
        self.walked[purpose] += store.map.exits[store.map.here][number]
        log.info("%s; walk exit %d", why, number)
        return {"action": "walk", "exit": number}

    def _take(self, volumes: list[str], why: str) -> dict:
        log.info("%s; take %d", why, len(volumes))
        return {"action": "take", "volumes": volumes}


def free(trolley: dict) -> int:
    """How many more volumes the trolley holds."""
    return trolley["capacity"] - len(trolley["carrying"])


def unseen(store: SharedStore) -> int:
    """How many volumes are neither in the hall, on the trolley nor on a shelf seen so far."""
    trolley = store.observation["trolley"]
    seen = (len(store.observation["reading_hall"]["volumes"]) + len(trolley["carrying"])
            + sum(len(volumes) for volumes in store.map.volumes.values()))
    return store.quest["total"] - seen


def allowed(trolley: dict) -> list[dict]:
    """What the fallback may choose now: a walk by each exit, a take of what fits here, and the end
    only in the reading hall, since anywhere else what the trolley carries would be lost."""
    position = trolley["position"]
    actions = [{"action": "walk", "exit": e["exit"]} for e in position["exits"]]
    if position.get("volumes") and free(trolley):
        actions.append({"action": "take", "volumes": position["volumes"][:free(trolley)]})
    if position["kind"] == "reading_hall":
        actions.append({"action": "end"})
    return actions


def parse_action(reply) -> dict | None:
    """The first JSON object with an "action" in a model reply; None if the reply was cut off or holds
    none. Decoding is tried from each "{" in turn, so braces in the text around it do no harm."""
    choice = reply.choices[0]
    if choice.finish_reason != "stop":
        return None
    text, decoder = choice.message.content or "", json.JSONDecoder()
    for start in (i for i, char in enumerate(text) if char == "{"):
        try:
            found, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if isinstance(found, dict) and "action" in found:
            return found
    return None
