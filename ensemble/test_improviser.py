"""The Improviser and its two baselines, in whole runs through the Conductor on small archives."""

import json
from types import SimpleNamespace

import llm
from baselines import DepthFirstWalker, PromptImproviser
from conductor import Conductor
from improviser import RULES, Improviser
from store import SharedStore

MAX_STEPS = 200  # as the arena's --max-steps: a run that goes round in circles stops, not the tests


class NightRound:
    """A small archive that plays the Night Round as README §4 and §7.2 describe. H is the hall.

    corridors: (place, exit, place, exit, length); shelves: the volumes in each room.
    """

    def __init__(self, corridors: list[tuple], shelves: dict[str, list[str]]) -> None:
        self.ends = {}
        for a, exit_a, b, exit_b, length in corridors:
            self.ends[a, exit_a] = (b, exit_b, length)
            self.ends[b, exit_b] = (a, exit_a, length)
        self.shelves = shelves
        self.total = sum(len(volumes) for volumes in shelves.values())
        self.here, self.carrying, self.hall = "H", [], []
        self.spent = {"steps": 0, "distance": 0, "characters": 0}
        self.observation = self._message(quest={"id": "N", "goal": "...", "total": self.total})

    @property
    def done(self) -> bool:
        return self.observation["done"]

    def step(self, action: dict) -> dict:
        self.spent["steps"] += 1
        outcome = {}
        if action["action"] == "walk":
            self.here, via, length = self.ends[self.here, action["exit"]]
            self.spent["distance"] += length
            outcome["move"] = {"walked": length, "via": via}
            if self.here == "H" and self.carrying:
                outcome["deposited"] = {"volumes": self.carrying}
                self.hall, self.carrying = self.hall + self.carrying, []
        if action["action"] == "take":
            for volume in action["volumes"]:
                self.shelves[self.here].remove(volume)
            self.carrying = self.carrying + action["volumes"]
            outcome["took"] = {"volumes": action["volumes"]}
        self.observation = self._message(end=action["action"] == "end", outcome=outcome)
        return self.observation

    def _message(self, end: bool = False, **first) -> dict:
        kind = ("reading_hall" if self.here == "H" else
                "room" if self.here in self.shelves else "junction")
        exits = sorted((number, length) for (place, number), (_, _, length) in self.ends.items()
                       if place == self.here)
        position = {"kind": kind, "id": self.here,
                    "exits": [{"exit": number, "length": length} for number, length in exits]}
        if kind == "room":
            position["volumes"] = list(self.shelves[self.here])
        finished, stopped = len(self.hall) == self.total, self.spent["steps"] >= MAX_STEPS
        message = {**first, "trolley": {"position": position, "carrying": self.carrying, "capacity": 5},
                   "reading_hall": {"volumes": self.hall}, "spent": dict(self.spent),
                   "done": finished or end or stopped}
        if message["done"]:
            message["reason"] = "finished" if finished else "ended" if end else "stopped"
        return message


class RefusesFirstTake(NightRound):
    """Refuses the first take once, as the arena refuses an action (README §2): the step is spent and
    nothing else changes."""

    refused = False

    def step(self, action: dict) -> dict:
        if action["action"] != "take" or self.refused:
            return super().step(action)
        self.refused = True
        self.spent["steps"] += 1
        self.observation = self._message(outcome={"invalid": {"code": "bad_take"}})
        return self.observation


def small() -> NightRound:
    """H -4- J -3- R1 (3 volumes), J -6- R2 (4 volumes), and R2 -10- H."""
    return NightRound([("H", 1, "J", 1, 4), ("J", 2, "R1", 1, 3), ("J", 3, "R2", 2, 6),
                       ("R2", 1, "H", 2, 10)],
                      {"R1": ["v-1", "v-2", "v-3"], "R2": ["v-4", "v-5", "v-6", "v-7"]})


def dead_end(arena: type[NightRound] = NightRound) -> NightRound:
    """Exit 1 of the hall leads 30 to an empty room, exit 2 leads 2 to every volume."""
    return arena([("H", 1, "E", 1, 30), ("H", 2, "N", 1, 2)], {"E": [], "N": ["v-1", "v-2"]})


def full_room() -> NightRound:
    """H -1- A (6 volumes) -5- B (1 volume): the trolley, which holds 5, fills up in A."""
    return NightRound([("H", 1, "A", 1, 1), ("A", 2, "B", 1, 5)],
                      {"A": [f"v-{i}" for i in range(6)], "B": ["v-6"]})


def fork() -> NightRound:
    """H -2- A (empty) -4- C (1 volume), and H -3- B (1 volume)."""
    return NightRound([("H", 1, "A", 1, 2), ("H", 2, "B", 1, 3), ("A", 2, "C", 1, 4)],
                      {"A": [], "B": ["v-1"], "C": ["v-2"]})


def replying(text: str, finish_reason: str = "stop"):
    """A stand-in for llm.chat that always gives this reply and keeps the prompts it was sent."""
    def chat(messages, **options):
        chat.prompts.append(messages[-1]["content"])
        choice = SimpleNamespace(message=SimpleNamespace(content=text), finish_reason=finish_reason)
        return SimpleNamespace(choices=[choice], usage=None)

    chat.prompts = []
    return chat


def started(arena: NightRound) -> SharedStore:
    store = SharedStore()
    store.observe(arena.observation, sent=None)
    return store


def test_improviser_delivers_every_volume():
    improviser = Improviser()
    last = Conductor(small(), improviser=improviser).play()
    assert last["reason"] == "finished" and len(last["reading_hall"]["volumes"]) == 7
    # It explores H, J, R1, J, R2, taking R1's three on the way, and sees the last volumes in R2.
    # The plan from there: home with three, then R2's four (H-R2 is not known: it goes by J).
    assert improviser.walked == {"exploring": 16, "carrying": 30}
    assert last["spent"]["distance"] == 46


def test_the_cheapest_untried_exit_is_walked_first():
    improviser = Improviser()
    assert Conductor(dead_end(), improviser=improviser).play()["spent"]["distance"] == 4
    assert improviser.walked == {"exploring": 2, "carrying": 2}
    # Depth-first tries exit 1 first and walks the empty room's corridor both ways.
    assert Conductor(dead_end(), improviser=DepthFirstWalker()).play()["spent"]["distance"] == 64


def test_a_full_trolley_goes_home_before_it_explores_on():
    # Home with five, back for A's last and on to B. Exploring on with a full trolley walks 24.
    assert Conductor(full_room(), improviser=Improviser()).play()["spent"]["distance"] == 14


def test_the_cost_of_an_exit_counts_the_walk_to_it():
    # In A, A's exit 2 (4) is cheaper than the hall's exit 2 (3, but 2 away); by length alone it is 22.
    assert Conductor(fork(), improviser=Improviser()).play()["spent"]["distance"] == 18


def test_the_plan_decides_every_take():
    arena, improviser, walk = dead_end(), Improviser(), {"action": "walk", "exit": 2}
    store = started(arena)
    store.observe(arena.step(walk), sent=walk)  # in N, with every volume in sight
    improviser.plan = [("N", 1), ("H", 0), ("N", 1), ("H", 0)]
    assert improviser.next_action(store, None) == {"action": "take", "volumes": ["v-1"]}


def test_a_plan_used_up_with_volumes_left_is_made_again():
    improviser = Improviser()
    improviser.plan = [("N", 1), ("H", 0)]  # leaves one of N's two volumes behind
    last = Conductor(dead_end(), improviser=improviser).play()
    assert last["reason"] == "finished" and last["spent"]["distance"] == 8


def test_depth_first_walker_delivers_every_volume():
    last = Conductor(small(), improviser=DepthFirstWalker()).play()
    assert last["reason"] == "finished" and last["spent"]["distance"] == 46


def test_after_a_refusal_the_model_chooses_among_the_allowed_actions(monkeypatch):
    arena, walk = small(), {"action": "walk", "exit": 1}
    store = started(arena)
    store.observe(arena.step(walk), sent=walk)  # at the junction: the latest message has no quest
    chat = replying('```json\n{"action": "walk", "exit": 2}\n```')
    monkeypatch.setattr(llm, "chat", chat)
    assert Improviser().next_action(store, "the arena refused the last action: no_exit") == \
        {"action": "walk", "exit": 2}
    assert json.dumps(store.quest) in chat.prompts[0]  # the rules refer to quest.total


def test_a_model_reply_that_is_not_allowed_leaves_the_move_to_the_conductor(monkeypatch):
    arena, walk = small(), {"action": "walk", "exit": 1}
    store = started(arena)
    store.observe(arena.step(walk), sent=walk)  # at the junction
    for reply in ('{"action": "walk", "exit": 9}', '{"action": "end"}'):  # no such exit; not the hall
        monkeypatch.setattr(llm, "chat", replying(reply))
        assert Improviser().next_action(store, "no_exit: the exits here are [1, 2, 3]") is None


def test_after_the_arena_refuses_a_take_the_model_takes_and_the_run_finishes(monkeypatch):
    chat = replying('{"action": "take", "volumes": ["v-1", "v-2"]}')
    monkeypatch.setattr(llm, "chat", chat)
    last = Conductor(dead_end(RefusesFirstTake), improviser=Improviser()).play()
    assert last["reason"] == "finished" and last["spent"]["distance"] == 4
    assert len(chat.prompts) == 1 and "the arena refused the last action: bad_take" in chat.prompts[0]


def test_after_an_unusable_model_reply_the_rules_still_finish_the_run(monkeypatch):
    monkeypatch.setattr(llm, "chat", replying("I cannot tell."))
    last = Conductor(dead_end(RefusesFirstTake), improviser=Improviser()).play()
    # The Conductor walks the nearest exit, home, and the plan is made again: back for both volumes.
    assert last["reason"] == "finished" and last["spent"]["distance"] == 8


def test_prompt_baseline_reads_its_action_from_the_reply(monkeypatch):
    arena = small()
    chat = replying('Exit 1 is shorter.\n```json\n{"action": "walk", "exit": 1}\n```')
    monkeypatch.setattr(llm, "chat", chat)
    assert PromptImproviser().next_action(started(arena), None) == {"action": "walk", "exit": 1}
    assert chat.prompts[0].startswith(RULES) and json.dumps(arena.observation) in chat.prompts[0]
    for text in ('Exit {1} is shorter: {"action": "walk", "exit": 1}',
                 '{"action": "walk", "exit": 1}, or else {"action": "walk", "exit": 2}'):
        monkeypatch.setattr(llm, "chat", replying(text))
        assert PromptImproviser().next_action(started(arena), None) == {"action": "walk", "exit": 1}


def test_an_unreadable_reply_goes_back_once_with_the_reason(monkeypatch):
    chat = replying('{"action": "walk", "exit": 1}', finish_reason="length")  # cut off
    monkeypatch.setattr(llm, "chat", chat)
    assert PromptImproviser().next_action(started(small()), None) == {}
    Conductor(small(), improviser=PromptImproviser()).play()
    assert "Your action null was not accepted: unreadable" in chat.prompts[2]


def test_prompt_baseline_records_each_new_message_once(monkeypatch):
    arena, baseline, walk = small(), PromptImproviser(), {"action": "walk", "exit": 1}
    monkeypatch.setattr(llm, "chat", replying(json.dumps(walk)))
    store = started(arena)
    baseline.next_action(store, None)
    baseline.next_action(store, "no_exit: the exits here are [1, 2]")  # the same message again
    assert len(baseline.turns) == 1
    store.observe(arena.step(walk), sent=walk)
    baseline.next_action(store, "the arena refused the last action: no_exit")
    assert len(baseline.turns) == 2  # recorded even when asked with feedback
