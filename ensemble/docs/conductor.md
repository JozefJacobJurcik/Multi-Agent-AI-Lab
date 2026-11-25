# Conductor: interface

How the Conductor plays a run, and what it needs from each specialist. Design: M1 §2.2. Terms as in [CONTEXT.md](../CONTEXT.md). Code: `conductor.py`, `checks.py`, `specialists.py`; tests: `test_conductor.py`, `test_checks.py`.

## A run

`main.py` plays the self-test itself and hands the base quests to the Conductor. The Overture comes once the Improviser's distances and the Musicologist's ratings exist.

| Quest | Each turn, the Conductor |
|---|---|
| N | asks the Improviser for its next action |
| R, G | takes the first open item, asks the Musicologist (a question) or the Player (a puzzle) for a proposal, then answers or skips |

## Your specialist

Write a class with your role's method from `specialists.py`; no base class is needed. Hand an instance to the Conductor in `main.py`:

```python
Conductor(arena, improviser=Improviser(), musicologist=Musicologist(), player=Player()).play()
```

| Role | Method | Returns |
|---|---|---|
| Improviser | `next_action(store, feedback)` | a `walk`, `take` or `end` action as in README §4, or `None` |
| Musicologist | `propose(item, store, query, feedback)` | a `Proposal` with the answer and its `supporting` volumes, or `None` |
| Player | `propose(item, store, query, feedback)` | a `Proposal` with the grid as `answer` and `supporting=[]`, or `None` to skip |

- `item` is the setlist entry in full, with its `text`.
- Never use the arena yourself. `query("read", volume="v-4326", section=3)` sends a query, files the reply in the store and returns it. Look in the store first: every `examine` and `read` is charged again.
- `feedback` is `None` on the first ask. If what you return fails a check, you are asked once more, with the reason. In the Night Round the Improviser is also asked once after the arena refuses its action, with the arena's reason (`the arena refused the last action: no_exit`).
- Return `None` when you have nothing to offer. If your method raises, its traceback goes into the team log and the Conductor falls back.
- `store.last_action` is the action actually sent last: after a default, the Conductor's, not yours.
- During long work, file your best answer so far with `store.propose(item["id"], proposal)`. If you then fail, the Conductor sends it.
- Call the model only through `llm.chat`, which counts the tokens.

## Checks and defaults

| When | The Conductor |
|---|---|
| the arena would refuse the action (`checks.refusal`, README §8) | asks once more, with the reason |
| an answer to a question has more than twelve words, no supporting volume, a supporting volume nothing was read of, or a part (split at `", "`) that is not in the supporting volumes' text (`checks.doubt`) | asks once more, with the reason |
| the second proposal fails too, or the specialist returns `None`, raises or is missing | sends the last proposal in the store if it is well-formed, else skips |
| the Improviser's second action fails too, or it returns `None`, raises or is missing | walks the nearest exit; after three of these in a row, ends the run |
| the arena refuses an answer that passed the checks | does not try it again: skips that item |
| the arena refuses the Improviser's action | asks it once more, with the arena's reason; if the arena refuses that action too, walks the nearest exit |

The Conductor checks only a grid's form; the Player checks it against the puzzle's rule. A model call is stopped after 240 seconds and retried once (`llm/`), so one call stays below the arena's ten minutes of silence. In graded runs each model call counts as hearing from the team; in practice runs only messages to the arena do, so a turn with several calls may need `--silence` (README §2).

## The decision log

One line per action in `traces/team-<ticket>.log`, from the logger `conductor`:

```
decision {"by": "Musicologist", "why": "passed the checks", "action": {…}, "outcome": {…}, "tokens": 1840, "spent": {"steps": 1, "distance": 0, "characters": 612}}
```

`by` is the part that decided, and `why` is the check's result or the reason for a default. `tokens` and `spent` count everything since the previous action, so they include the model calls and queries that led to this one.

## Testing without the arena

`test_conductor.py` plays scripted runs against a `FakeArena`: it hands out the arena's messages in order and records what was sent. Test your specialist the same way.
