from store import Proposal, SharedStore


def test_item_text_survives_later_setlists():
    store = SharedStore()
    store.observe({"quest": {"id": "R", "goal": "..."},
                   "setlist": [{"id": "question-1", "text": "Who wrote X?", "attempts_remaining": 1}]},
                  sent=None)
    store.observe({"outcome": {"invalid": {"code": "no_item"}},
                   "setlist": [{"id": "question-1", "attempts_remaining": 1}]},
                  sent={"action": "skip", "to": "question-9"})
    assert store.item("question-1")["text"] == "Who wrote X?"


def test_last_action_is_kept_across_queries():
    store = SharedStore()
    store.observe({"quest": {"id": "R", "goal": "..."},
                   "setlist": [{"id": "question-1", "text": "Q1?", "attempts_remaining": 1}]},
                  sent=None)
    assert store.last_action is None
    answer = {"action": "answer", "to": "question-1", "answer": 42}
    store.observe({"outcome": {"invalid": {"code": "bad_answer"}},
                   "setlist": [{"id": "question-1", "attempts_remaining": 1}]},
                  sent=answer)
    store.observe({"query": "read", "reply": {"text": "..."},
                   "charged": 3, "spent": {"steps": 1, "distance": 0, "characters": 3}},
                  sent={"query": "read", "volume": "v-1", "section": 1})
    assert store.last_action == answer


def test_read_text_is_kept():
    store = SharedStore()
    assert store.text("v-4326", 3) is None
    store.observe({"query": "read", "reply": {"text": "Section three ..."},
                   "charged": 17, "spent": {"steps": 0, "distance": 0, "characters": 17}},
                  sent={"query": "read", "volume": "v-4326", "section": 3})
    assert store.text("v-4326", 3) == "Section three ..."

    examined = {"title": "A", "abstract": "...", "sections": []}
    store.observe({"query": "examine", "reply": examined,
                   "charged": 3, "spent": {"steps": 0, "distance": 0, "characters": 20}},
                  sent={"query": "examine", "volume": "v-4326"})
    assert store.text("v-4326", None) == examined


def test_volume_text_joins_what_was_examined_and_read():
    store = SharedStore()
    assert store.volume_text("v-4326") == ""
    examined = {"title": "Cover Songs", "abstract": "On covers.", "sections": []}
    store.observe({"query": "examine", "reply": examined,
                   "charged": 10, "spent": {"steps": 0, "distance": 0, "characters": 10}},
                  sent={"query": "examine", "volume": "v-4326"})
    store.observe({"query": "read", "reply": {"text": "Released in 1972."},
                   "charged": 17, "spent": {"steps": 0, "distance": 0, "characters": 27}},
                  sent={"query": "read", "volume": "v-4326", "section": 2})
    assert store.volume_text("v-4326") == "Cover Songs\nOn covers.\nReleased in 1972."
    assert store.volume_text("v-1") == ""


def test_answered_item_leaves_open_items():
    store = SharedStore()
    store.observe({"quest": {"id": "R", "goal": "..."},
                   "setlist": [{"id": "question-1", "text": "Q1?", "attempts_remaining": 1},
                               {"id": "question-2", "text": "Q2?", "attempts_remaining": 1}]},
                  sent=None)
    store.observe({"outcome": {"invalid": {"code": "bad_answer"}},
                   "setlist": [{"id": "question-1", "attempts_remaining": 1},
                               {"id": "question-2", "attempts_remaining": 1}]},
                  sent={"action": "answer", "to": "question-2", "answer": 42})
    store.observe({"outcome": {"answer": {"to": "question-1", "result": "correct"}},
                   "setlist": [{"id": "question-2", "attempts_remaining": 1}]},
                  sent={"action": "answer", "to": "question-1", "answer": "X", "supporting": []})
    assert store.open_items() == ["question-2"]


def test_best_returns_last_proposal():
    store = SharedStore()
    assert store.best("question-1") is None
    store.propose("question-1", Proposal(answer="1971", supporting=["v-1"], confidence=0.4, author="Musicologist"))
    store.propose("question-1", Proposal(answer="1972", supporting=["v-2"], confidence=0.8, author="Musicologist"))
    assert store.best("question-1").answer == "1972"
