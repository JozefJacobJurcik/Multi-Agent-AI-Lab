import json
import logging

from conductor import Conductor
from store import Proposal

SPENT = {"steps": 0, "distance": 0, "characters": 0}
QUESTION = {"id": "question-1", "text": "When was Second Rivers released?", "attempts_remaining": 1}
DESK = {"quest": {"id": "R", "goal": "..."}, "reading_hall": {"volumes": ["v-1"]},
        "setlist": [QUESTION], "spent": SPENT, "done": False}
READ = {"query": "read",
        "reply": {"volume": "v-1", "section": 1, "text": "Second Rivers came out in 1972."},
        "charged": 31, "spent": {"steps": 0, "distance": 0, "characters": 31}}
ANSWER_1972 = {"action": "answer", "to": "question-1", "answer": "1972", "supporting": ["v-1"]}


class FakeArena:
    """Plays the arena's part of a run: the next scripted message for every action or query sent."""

    def __init__(self, first: dict, *messages: dict) -> None:
        self.observation = first
        self.messages = list(messages)
        self.sent: list[dict] = []

    @property
    def done(self) -> bool:
        return bool(self.observation.get("done"))

    def step(self, action: dict) -> dict:
        self.sent.append(action)
        self.observation = self.messages.pop(0)
        return self.observation

    def query(self, name: str, **arguments) -> dict:
        self.sent.append({"query": name, **arguments})
        return self.messages.pop(0)


class Reader:
    """A Musicologist that reads v-1 once and proposes its answers one after another."""

    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.feedback: list[str | None] = []

    def propose(self, item, store, query, feedback):
        self.feedback.append(feedback)
        if store.text("v-1", 1) is None:
            query("read", volume="v-1", section=1)
        return Proposal(self.answers.pop(0), ["v-1"], 0.9, "Musicologist")


def last(item: str, result: str, steps: int = 1) -> dict:
    """The arena's last message, after the answer or skip that closed the setlist."""
    return {"outcome": {"answer": {"to": item, "result": result}}, "setlist": [],
            "spent": {"steps": steps, "distance": 0, "characters": 31},
            "done": True, "reason": "finished"}


def at(position: dict, **rest) -> dict:
    """A Night Round message with the trolley at this position."""
    return {"trolley": {"position": position, "carrying": [], "capacity": 5}, "spent": SPENT,
            "done": False, **rest}


HALL = at({"kind": "reading_hall", "id": "H",
           "exits": [{"exit": 1, "length": 13}, {"exit": 2, "length": 9}]},
          quest={"id": "N", "goal": "...", "total": 3})
JUNCTION = at({"kind": "junction", "id": "J", "exits": [{"exit": 1, "length": 9}]},
              outcome={"move": {"walked": 9, "via": 1}})
ENDED = {**JUNCTION, "outcome": {}, "done": True, "reason": "ended"}


def test_checked_answer_is_sent_with_its_supporting_volumes():
    arena = FakeArena(DESK, READ, last("question-1", "correct"))
    Conductor(arena, musicologist=Reader("1972")).play()
    assert arena.sent == [{"query": "read", "volume": "v-1", "section": 1}, ANSWER_1972]


def test_doubted_answer_goes_back_once_then_the_last_well_formed_is_sent():
    reader = Reader("1980", "1990")
    arena = FakeArena(DESK, READ, last("question-1", "incorrect"))
    Conductor(arena, musicologist=reader).play()
    assert reader.feedback == [None, "not in the text of the supporting volumes: 1980"]
    assert arena.sent[-1]["answer"] == "1990"


def test_failing_specialist_falls_back_on_its_best_answer_so_far():
    class Crashing:
        def propose(self, item, store, query, feedback):
            store.propose(item["id"], Proposal("1972", ["v-1"], 0.5, "Musicologist"))
            raise TimeoutError("the model took too long")

    arena = FakeArena(DESK, last("question-1", "correct"))
    Conductor(arena, musicologist=Crashing()).play()
    assert arena.sent == [ANSWER_1972]


def test_proposal_of_the_wrong_type_goes_back_with_the_reason():
    class Sloppy:
        def __init__(self) -> None:
            self.feedback: list[str | None] = []

        def propose(self, item, store, query, feedback):
            self.feedback.append(feedback)
            return {"answer": "1972", "supporting": ["v-1"]}

    sloppy = Sloppy()
    arena = FakeArena(DESK, last("question-1", "skipped"))
    Conductor(arena, musicologist=sloppy).play()
    assert sloppy.feedback == [None, "propose returns a Proposal or None"]
    assert arena.sent == [{"action": "skip", "to": "question-1"}]


def test_filed_proposal_of_the_wrong_type_is_not_sent():
    class Filing:
        def propose(self, item, store, query, feedback):
            store.propose(item["id"], {"answer": "1972", "supporting": ["v-1"]})
            return None

    arena = FakeArena(DESK, last("question-1", "skipped"))
    Conductor(arena, musicologist=Filing()).play()
    assert arena.sent == [{"action": "skip", "to": "question-1"}]


def test_item_without_its_specialist_is_skipped():
    arena = FakeArena(DESK, last("question-1", "skipped"))
    Conductor(arena).play()
    assert arena.sent == [{"action": "skip", "to": "question-1"}]


def test_malformed_grid_is_skipped():
    class Player:
        def propose(self, item, store, query, feedback):
            return Proposal([[1, "2"], [2, 1]], [], 1.0, "Player")

    gate = {"quest": {"id": "G", "goal": "..."},
            "setlist": [{"id": "gate-1", "text": "A 2 by 2 grid ...", "attempts_remaining": 1}],
            "spent": SPENT, "done": False}
    arena = FakeArena(gate, last("gate-1", "skipped"))
    Conductor(arena, player=Player()).play()
    assert arena.sent == [{"action": "skip", "to": "gate-1"}]


def test_answer_the_arena_refuses_is_skipped_next():
    refused = {"outcome": {"invalid": {"code": "bad_answer"}}, "reading_hall": {"volumes": ["v-1"]},
               "setlist": [{"id": "question-1", "attempts_remaining": 1}],
               "spent": {"steps": 1, "distance": 0, "characters": 31}, "done": False}
    arena = FakeArena(DESK, READ, refused, last("question-1", "skipped", steps=2))
    Conductor(arena, musicologist=Reader("1972")).play()
    assert arena.sent[1:] == [ANSWER_1972, {"action": "skip", "to": "question-1"}]


def test_night_round_walks_the_nearest_exit_then_ends():
    class Lost:
        def __init__(self) -> None:
            self.feedback: list[str | None] = []

        def next_action(self, store, feedback):
            self.feedback.append(feedback)
            return {"action": "walk", "exit": 7}

    improviser = Lost()
    arena = FakeArena(HALL, JUNCTION, JUNCTION, JUNCTION, ENDED)
    Conductor(arena, improviser=improviser).play()
    assert arena.sent == [{"action": "walk", "exit": 2}, {"action": "walk", "exit": 1},
                          {"action": "walk", "exit": 1}, {"action": "end"}]
    assert improviser.feedback[:2] == [None, "no_exit: the exits here are [1, 2]"]


def test_action_the_arena_refuses_is_followed_by_the_nearest_exit(caplog):
    class Improviser:
        def __init__(self) -> None:
            self.actions = [{"action": "walk", "exit": 1}, {"action": "end"}]
            self.seen: list[dict | None] = []

        def next_action(self, store, feedback):
            self.seen.append(store.last_action)
            return self.actions.pop(0)

    caplog.set_level(logging.INFO, logger="conductor")
    refused = at(HALL["trolley"]["position"], outcome={"invalid": {"code": "no_exit"}})
    improviser = Improviser()
    arena = FakeArena(HALL, refused, JUNCTION, ENDED)
    Conductor(arena, improviser=improviser).play()
    assert arena.sent == [{"action": "walk", "exit": 1}, {"action": "walk", "exit": 2},
                          {"action": "end"}]
    # Not asked after the refusal, and then shown the walk the Conductor chose in its place.
    assert improviser.seen == [None, {"action": "walk", "exit": 2}]
    whys = [json.loads(message.removeprefix("decision "))["why"] for message in caplog.messages]
    assert whys == ["passed the checks", "nearest exit: the arena refused the last action",
                    "passed the checks"]


def test_each_action_is_logged_with_who_decided_and_what_it_cost(caplog):
    caplog.set_level(logging.INFO, logger="conductor")
    arena = FakeArena(DESK, READ, last("question-1", "correct"))
    Conductor(arena, musicologist=Reader("1972")).play()
    record = json.loads(caplog.messages[-1].removeprefix("decision "))
    assert record["by"] == "Musicologist"
    assert record["why"] == "passed the checks"
    assert record["tokens"] == 0
    assert record["spent"] == {"steps": 1, "distance": 0, "characters": 31}
