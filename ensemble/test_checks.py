from checks import doubt, refusal
from store import Proposal, SharedStore

SPENT = {"steps": 0, "distance": 0, "characters": 0}
QUESTION = {"id": "question-1", "text": "When was Second Rivers released?", "attempts_remaining": 1}


def started(first: dict) -> SharedStore:
    store = SharedStore()
    store.observe({**first, "spent": SPENT, "done": False}, sent=None)
    return store


def answer(to: str, value: object, **more) -> dict:
    return {"action": "answer", "to": to, "answer": value, **more}


def test_night_round_refusals():
    store = started({"quest": {"id": "N", "goal": "...", "total": 4},
                     "trolley": {"position": {"kind": "room", "id": "R1", "volumes": ["v-1", "v-2"],
                                              "exits": [{"exit": 1, "length": 9}]},
                                 "carrying": ["v-3"], "capacity": 2}})
    assert refusal({"action": "walk", "exit": 1}, store) is None
    assert refusal({"action": "take", "volumes": ["v-1"]}, store) is None
    assert refusal({"action": "end"}, store) is None
    assert refusal({"action": "walk", "exit": 2}, store) == "no_exit: the exits here are [1]"
    assert refusal({"action": "take", "volumes": ["v-9"]}, store).startswith("bad_take")
    # The trolley holds two and carries one, so it has room for one more.
    assert refusal({"action": "take", "volumes": ["v-1", "v-2"]}, store).startswith("bad_take")
    # A set is not JSON, so the arena client could not send it.
    assert refusal({"action": "take", "volumes": {"v-1"}}, store).startswith("unreadable")
    assert refusal({"action": "skip", "to": "question-1"}, store).startswith("unknown_action")
    assert refusal("walk", store).startswith("unreadable")
    assert refusal({"action": ["walk"]}, store).startswith("unreadable")


def test_answer_refusals():
    desk = started({"quest": {"id": "R", "goal": "..."}, "reading_hall": {"volumes": ["v-1"]},
                    "setlist": [QUESTION]})
    assert refusal(answer("question-1", "1972", supporting=["v-1"]), desk) is None
    assert refusal(answer("question-1", " "), desk).startswith("bad_answer")
    assert refusal(answer("question-1", "1972", supporting="v-1"), desk).startswith("bad_answer")
    assert refusal(answer("question-2", "1972"), desk).startswith("no_item")

    gate = started({"quest": {"id": "G", "goal": "..."},
                    "setlist": [{"id": "gate-1", "text": "A 2 by 2 grid ...", "attempts_remaining": 1}]})
    assert refusal(answer("gate-1", [[1, 2], [2, 1]]), gate) is None
    assert refusal(answer("gate-1", [[1, 2], [2]]), gate).startswith("bad_answer")
    assert refusal(answer("gate-1", [["1", "2"], ["2", "1"]]), gate).startswith("bad_answer")


def test_doubt_wants_the_answer_in_the_text_it_cites():
    store = started({"quest": {"id": "R", "goal": "..."}, "reading_hall": {"volumes": ["v-1", "v-2"]},
                     "setlist": [QUESTION]})
    store.observe({"query": "read", "reply": {"text": "Second Rivers came out in 1972 on Oriel Discs."},
                   "charged": 46, "spent": {"steps": 0, "distance": 0, "characters": 46}},
                  sent={"query": "read", "volume": "v-1", "section": 1})

    def doubt_about(value: str, supporting: list[str]) -> str | None:
        return doubt(QUESTION["id"], Proposal(value, supporting, 0.9, "Musicologist"), store)

    assert doubt_about("1972", ["v-1"]) is None
    assert doubt_about("Oriel Discs, 1972.", ["v-1"]) is None
    assert doubt_about("1980", ["v-1"]) == "not in the text of the supporting volumes: 1980"
    assert doubt_about("1972", []) == "no supporting volumes"
    assert doubt_about("1972", ["v-2"]) == "nothing of v-2 has been read or examined"
    assert doubt_about(" ".join(["word"] * 13), ["v-1"]) == "the answer has more than 12 words"
