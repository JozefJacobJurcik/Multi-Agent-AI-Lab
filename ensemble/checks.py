"""The checks in code that a specialist's action passes before the Conductor sends it.

refusal() says why the arena would refuse an action (README §8), doubt() why a well-formed answer to
a question is probably wrong. Either reason goes back to the specialist, which is asked once more.
"""

from __future__ import annotations

import json

from store import Proposal, SharedStore

ACTIONS = {"N": {"walk", "take", "end"}, "R": {"answer", "skip", "end"}, "G": {"answer", "skip", "end"}}
MAX_WORDS = 12  # README §5: "Twelve words is the most any answer needs"


def refusal(action: object, store: SharedStore) -> str | None:
    """Why the arena would refuse the action; None if it would take it."""
    if not isinstance(action, dict) or not isinstance(action.get("action"), str):
        return "unreadable: an action is a dict with its name as a string under 'action'"
    try:
        json.dumps(action)
    except (TypeError, ValueError):
        return "unreadable: an action holds only plain JSON values: dict, list, str, int"
    name, allowed = action["action"], ACTIONS[store.quest["id"]]
    if name not in allowed:
        return f"unknown_action: the actions of this quest are {sorted(allowed)}"
    observation = store.observation
    if name == "walk":
        exits = [e["exit"] for e in observation["trolley"]["position"].get("exits", [])]
        if action.get("exit") not in exits:
            return f"no_exit: the exits here are {exits}"
    if name == "take":
        return _bad_take(action.get("volumes"), observation["trolley"])
    if name in ("answer", "skip"):
        setlist = [item["id"] for item in observation.get("setlist", [])]
        if action.get("to") not in setlist:
            return f"no_item: the open items are {setlist}"
    if name == "answer":
        return _bad_answer(action["to"], action.get("answer"), action.get("supporting", []))
    return None


def doubt(item_id: str, proposal: Proposal, store: SharedStore) -> str | None:
    """Why a well-formed answer to a question is probably wrong; None if nothing speaks against it.

    A puzzle's grid is not doubted here: the Player checks it against the puzzle's rule.
    """
    if not item_id.startswith("question"):
        return None
    answer = _plain(proposal.answer)
    if len(answer.split()) > MAX_WORDS:
        return f"the answer has more than {MAX_WORDS} words"
    if not proposal.supporting:
        return "no supporting volumes"
    texts = {volume: _plain(store.volume_text(volume)) for volume in proposal.supporting}
    unread = [volume for volume, text in texts.items() if not text]
    if unread:
        return f"nothing of {', '.join(unread)} has been read or examined"
    missing = [part for part in answer.split(", ")
               if not any(part in text for text in texts.values())]
    if missing:
        return f"not in the text of the supporting volumes: {', '.join(missing)}"
    return None


def _bad_take(volumes: object, trolley: dict) -> str | None:
    here = trolley["position"].get("volumes", [])
    room = trolley["capacity"] - len(trolley["carrying"])
    if not isinstance(volumes, list) or not volumes:
        return "bad_take: volumes is a list of at least one volume id"
    if not all(volume in here for volume in volumes):
        return f"bad_take: the volumes here are {here}"
    if len(set(volumes)) < len(volumes):  # each is an id from here now, so set() can hash it
        return "bad_take: each volume is named once"
    if len(volumes) > room:
        return f"bad_take: the trolley has room for {room}"
    return None


def _bad_answer(item_id: str, answer: object, supporting: object) -> str | None:
    if item_id.startswith("question"):
        if not (isinstance(answer, str) and answer.strip()):
            return "bad_answer: a question takes a non-empty string"
        if not (isinstance(supporting, list) and all(isinstance(volume, str) for volume in supporting)):
            return "bad_answer: supporting is a list of volume ids"
    if item_id.startswith("gate") and not _is_grid(answer):
        return "bad_answer: a puzzle takes its grid as a list of equally long rows of whole numbers"
    return None


def _is_grid(answer: object) -> bool:
    if not (isinstance(answer, list) and answer and isinstance(answer[0], list) and answer[0]):
        return False
    # type(n) is int rather than isinstance: True and False are ints in Python too
    return all(isinstance(row, list) and len(row) == len(answer[0]) and all(type(n) is int for n in row)
               for row in answer)


def _plain(text: str) -> str:
    """Lower case, single spaces and no full stop at the end, so that texts compare by their words."""
    return " ".join(text.lower().split()).strip(".")
