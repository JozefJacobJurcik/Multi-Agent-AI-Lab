# The Archive Games: rules and API reference

IN2106 Multi-Agent AI Lab · 9 November 2026

This is the complete reference for the base game: how your container talks to the arena, what every
message carries and the rules of each base quest. "The arena at a glance" gave the picture; this
gives the details. Anything not written here is not part of the game. To set up the arena, your
container and the model, follow `SETUP.md` in this folder first.

## 1. Your container

Your team ships one container. Each time it starts, it reads its settings from the environment,
connects to the arena and plays one run.

| Setting | What it holds |
|---|---|
| `ARCHIVE_ARENA_URL` | the arena's address |
| `ARCHIVE_TICKET` | the ticket for this run |
| `ARCHIVE_LLM_URL` | the model endpoint: Morpheus while you develop, ours in graded runs |
| `ARCHIVE_LLM_MODEL` | the model's id |
| `ARCHIVE_LLM_KEY` | your Morpheus key while you develop; in graded runs we set it |

Read all five from the environment and never write an address or a key into your code. A graded
run reaches only the arena and our model endpoint, so everything your container needs must be in
its image.

The ticket says which quest and which instance the run plays. Your container learns the quest
from the arena's first message, not from the ticket.

## 2. One run

A run is one instance of one quest, played over one websocket connection. Messages are JSON
objects, one per websocket message.

1. Your container connects and sends its ticket:
   `{"hello": {"ticket": "T-…", "protocol": 1}}`
2. The arena answers with the quest's **first message**. If the ticket is unknown or already used,
   it answers `{"error": {"code": "bad_ticket"}}` instead and closes the connection; if the hello
   is malformed, `{"error": {"code": "protocol"}}`.
3. From then on your container sends **one message at a time and waits for the reply**. Each
   message is either an **action** or a **query**, never both.
4. The reply that carries `"done": true` is the arena's last. The arena then closes the connection.

The client in your starter does steps 1, 2 and 4 for you:

```python
from arena_client import connect

arena = connect(url, ticket)        # sends the hello; arena.observation is the first message
obs = arena.step({"action": "walk", "exit": 2})           # an action: one step passes
reply = arena.query("read", volume="v-4326", section=3)   # a query: no step passes
arena.done                          # True once the run is over
```

### Actions and queries

- An **action** changes the run: walking, taking volumes, answering, skipping, ending. **Every
  action costs one step**, whether it succeeds or not. The reply says what the action did
  (`outcome`) and what you now see.
- A **query** only looks: `browse`, `examine` and `read`. It costs no step, but the text it shows
  you is counted in characters. A query that fails costs nothing.

### Refused actions

An action the rules do not allow is refused. A refusal changes nothing but the step count: the
reply's outcome is `{"invalid": {"code": "…"}}`, with one of the codes in §8, and the rest of the
reply is the observation as before. No attempt at a question, puzzle or claim is used up by a
refused answer.

A message that is not JSON, that has neither `action` nor `query` or that has both is refused with
`unreadable`.

### How a run ends

The reply's `reason` says why the run is over:

| `reason` | When |
|---|---|
| `finished` | every item on the setlist has been answered or skipped (the Night Round: every volume is in the reading hall) |
| `ended` | your container sent `{"action": "end"}`. Whatever is still open counts as skipped; in the Night Round the run ends where it stands |
| `stopped` | the arena stopped the run: your container was silent too long, reached a step limit set on the ticket or lost its connection |

The arena stops a run after ten minutes in which it has heard nothing from your container. In graded
runs a model call through our endpoint counts as hearing from you; in practice runs only your
messages count, and `--silence` (§9) changes the limit.
`end` costs a step like any other action.

## 3. What a message from the arena carries

Every reply to an action is one observation: the parts below that the quest uses, with `outcome`
first. The first message has `quest` in place of `outcome`.

```jsonc
{ "outcome":      { … },                       // what your last action did (§4)
  "trolley":      { "position": { … }, "carrying": ["v-1742"], "capacity": 5 },
  "reading_hall": { "volumes": ["v-4826", "v-6065"] },
  "setlist":      [ { "id": "question-2", "attempts_remaining": 1 } ],
  "spent":        { "steps": 6, "distance": 114, "characters": 210 },
  "done":         false }                      // and "reason" once it is true
```

| Part | What it holds |
|---|---|
| `quest` | first message only: `id` (`selftest`, `N`, `R`, `G`, `V` or `O`) and `goal`, a short description; in the Night Round also `total`, the number of volumes to deliver |
| `trolley` | quests with a trolley: where it stands (`position`), the ids of the volumes it is `carrying` and its `capacity` |
| `reading_hall` | the ids of the volumes on the reading hall's shelves |
| `setlist` | every question, puzzle and claim still open (§3.2) |
| `spent` | the run's meters so far: `steps` (actions), `distance` (walked) and `characters` (text shown to you) |
| `done` | `true` in the last message, with `reason` |

Model tokens are not in any message: our endpoint counts them.

### 3.1 The trolley's position

```jsonc
{ "kind": "room", "id": "R2", "topic": "Alignment and Cover Songs",
  "volumes": ["v-1306", "v-1896"],
  "exits": [ { "exit": 1, "sign": "Reading hall", "length": 13 },
             { "exit": 2, "sign": "Signal Processing", "length": 14, "locked": true } ] }
```

- `kind` is `reading_hall`, `room`, `junction` or `locked_door`. A room holds volumes and lists
  them in `volumes`; a junction holds nothing.
- `exits` numbers each corridor leaving this place, from 1. An exit's number at a place does not
  change during the run. `length` is the corridor's length.
- `sign`, `topic` and `locked` appear only in the Overture (§7.6).

### 3.2 The setlist

Each item is a question (`question-1`, …), a puzzle (`gate-1`, …) or a claim (`claim-1`, …).

- **An item's text comes in full only once**, in the message that poses it. After that the
  setlist shows it as `{"id": …, "attempts_remaining": …}` until it is answered or skipped. Keep
  the text.
- In the base quests, every item has **one attempt**. An item leaves the setlist once it is
  answered, right or wrong, or skipped.
- A claim also carries `extracts`, its passages (§7.5).

### 3.3 Volume ids

Volumes are named by ids such as `v-4326`. An id is fixed for the run and means nothing beyond
it: the same volume has a different id in the next run.

## 4. Actions

| Action | Message |
|---|---|
| walk | `{"action": "walk", "exit": 2}` |
| take | `{"action": "take", "volumes": ["v-1306", "v-1896"]}` |
| answer | `{"action": "answer", "to": "question-1", "answer": …}` (the answer's form depends on the item, §5) |
| skip | `{"action": "skip", "to": "claim-3"}` |
| end | `{"action": "end"}` |

What each one can say in the reply's `outcome`:

| Outcome | Meaning |
|---|---|
| `{"move": {"walked": 22, "via": 4}}` | the trolley walked a corridor of length 22 and arrived by its exit 4 there, so exit 4 leads back |
| `{"took": {"volumes": [ … ]}}` | these volumes are now on the trolley |
| `{"deposited": {"volumes": [ … ]}}` | the trolley arrived in the reading hall and put these volumes on its shelves |
| `{"answer": {"to": "claim-1", "result": "correct"}}` | `result` is `correct`, `incorrect` or, after a skip, `skipped` |
| `{"invalid": {"code": "no_exit"}}` | the action was refused (§8) |
| `{}` | the reply to `end` |

One action can have several effects, such as `move` with `deposited`.

### Walking and taking

- `walk` names an exit of the place where the trolley stands, and the trolley walks the whole
  corridor. Walking adds the corridor's length to `distance`.
- `take` names at least one volume on the shelves where the trolley stands, each once and no more
  than the trolley has room for. Anything else is refused with `bad_take`. Nothing can be
  taken in the reading hall or at a junction, and nothing can be put back.
- On arriving in the reading hall, the trolley puts everything it carries on the hall's shelves.

## 5. Answers

| Item | `answer` | Also |
|---|---|---|
| question | a string: the shortest phrase that answers the question | `supporting`: the ids of the volumes your answer rests on |
| puzzle | the completed grid as a list of its rows from top to bottom, each row a list of its numbers from left to right: `[[1, 2, 3, 4], …]` | |
| claim | `true` or `false`, without quotes | |

An answer of the wrong form is refused with `bad_answer`, and the item keeps its attempt.

**Answering a question.** Answer with the shortest phrase that answers the question, in the
archive's own words: a name, a year, a number, a title. If the question asks for several things,
give all of them, in the order the question asks for if it asks for one. Twelve words is the most
any answer needs. A reply that offers alternatives ("19 or 21"), gives two answers where one is
asked or says more than the answer is marked incorrect. Write numbers in English style, with a
decimal point: 2.5, not 2,5. In a list, put a space after each comma: 112, 123 is two numbers,
112,123 is one. A comma between thousands may be left in or out: 12,550 and 12550 are the same. A
number may be written in digits or words, with its unit in any common form (20 ms, 0.02 s, 20
milliseconds); a unit or scale that doesn't match the answer's is wrong, and a number without its
unit counts only where the question names the unit.
After a number, name only its unit or the thing the question counts. A minus sign or a comparison
such as "more than", "up to" or "<" belongs to the number beside it, and counts only where the
archive gives the same. Plural or singular, British or American spelling and a hyphen or space all
count the same.

**The archive is the authority.** Answers are scored against what the volumes establish. Where the
archive and the wider world disagree, the archive wins.

## 6. Queries

| Query | Message | Shows you | Charged |
|---|---|---|---|
| browse | `{"query": "browse"}` | every lit volume: its `index`, `id`, `title` and length in `characters`, in alphabetical order of title | nothing |
| examine | `{"query": "examine", "volume": "v-4326"}` | the volume's title, abstract and section headings, each with its number `n` and length; in Variorum also `source` and `date` | the abstract's length, at most 900 characters |
| read | `{"query": "read", "volume": "v-4326", "section": 3}` | the text of one section | the section's length |

No abstract is longer than 900 characters, so one `examine` never costs more than 900.

The reply to a query:

```jsonc
{ "query": "examine", "reply": { … }, "charged": 64,
  "spent": { "steps": 0, "distance": 0, "characters": 64 } }
```

or, if it fails, `"error": {"code": "…"}` in place of `reply` (§8), with nothing charged.

**What is lit, and where you can read.**

- The reading hall is always lit: from anywhere, you can browse and examine the volumes on its
  shelves.
- The trolley carries a lamp. It lights the place where it stands and the volumes it carries, so
  you can browse and examine them.
- Everywhere else is too dark to make out text.
- **A volume is opened only in the reading hall.** `read` works only on a volume on the hall's
  shelves.

So `browse` and `examine` work on what is lit, and `read` only on what is in the hall. Every
`examine` and `read` is charged, even of something you have looked at before: keeping what you have
read is your team's job.

## 7. The quests

Every quest scores its result and what your team spent; each quest's **What counts** lists the
parts. The weights are published before M2.

### 7.1 The self-test

Checks that your container reaches the arena and the model endpoint. The reading hall holds one
volume, and the setlist one question: "What number is written in section 1 of volume v-…?". Your
container reads that section, asks the model and answers with the number. Your starter does this
already: run it first, whenever something changes. It is not scored: the reply's outcome says
whether your answer was right.

- Actions: `answer`, `skip` and `end`. Queries: all three.

### 7.2 Night Round (N, the Improviser)

- The run starts in the reading hall, with an empty trolley. There is no map, no sign and no
  topic: an exit tells you only its length.
- **Goal:** bring every volume to the reading hall. `quest.total` says how many there are, and the
  trolley holds `capacity` at a time.
- Actions: `walk`, `take` and `end`. There are no queries.
- **Ends** `finished` when the last volume arrives in the reading hall.
- **What counts:** the volumes delivered to the reading hall, 1 each; the distance walked; the
  tokens used.

### 7.3 Reading Desk (R, the Musicologist)

- One room, the reading hall, already stocked. Every question is on the setlist from the first
  message. No trolley.
- Actions: `answer` (a string, with `supporting`), `skip` and `end`. Queries: all three.
- **What counts:**
  - whether the answer is right: 1 if it is, 0 for a wrong answer or a skip;
  - for a right answer, whether the volumes you name support it: 1 if they are exactly a set that
    establishes it, and more than one set may do; each extra volume takes off a share, and a
    missing one gives 0;
  - how much your team read beyond what the question needed;
  - the tokens used.

### 7.4 Gate (G, the Player)

- A locked door sets puzzles one after another. Each is described in a paragraph that says
  everything: the size of the grid and its boxes, the rule, the given entries in the order they are
  read and how to reply.
- Only one puzzle is on the setlist at a time; the next comes in the reply to your answer or skip.
- Actions: `answer` (the grid as rows), `skip` and `end`. There are no queries.
- **What counts:** how many puzzles your team solves and the tokens used.

### 7.5 Variorum (V, the Critic, teams of four)

- The reading hall holds seven volumes about a music scene. Several sources cover the
  same albums, and they do not always agree. Every scene, practice or graded, is set in a different
  region, with its own artists, labels and sources.
- Every claim is on the setlist from the first message, with its passages in `extracts`: each
  sentence in the hall that names the claim's album, with the volume it comes from:

  ```jsonc
  { "id": "claim-2", "text": "Second Rivers by Casimir Ostrava was released on Oriel Discs.",
    "attempts_remaining": 1,
    "extracts": [ { "volume": "v-2941", "text": "Notice of April 1972: …" }, … ] }
  ```

- A passage is one sentence. The volume may say more around it, and `read` takes you there.
- `examine` shows who wrote a volume and when: its `source` and `date`, beside the abstract.
- Actions: `answer` (`true` or `false`), `skip` and `end`. Queries: all three.
- **What counts:** +1 for a right answer, 0 for a skip and −2 for a wrong one; the tokens used
  count too.

### 7.6 The Overture (O, the whole Ensemble)

The Overture puts the specialisations together in one small archive.

- The run starts in the reading hall. The setlist holds about six questions and, for a team of
  four, about five claims, whose scene's volumes stand on the reading hall's shelves. A team of
  three gets no claims.
- **Signs.** Every exit carries a `sign`: the topic of the room beyond it, `"Junction"` or
  `"Reading hall"`. A room's position names its `topic`. The answers to the questions are in the
  rooms, each question in one room's volumes.
- Fetch volumes with the trolley and read them in the reading hall. You can `browse` and `examine`
  what is lit (§6) wherever the trolley stands.
- Questions and claims may be answered from anywhere. A question's `supporting` volumes need not be
  in the reading hall.
- **Locked doors.** An exit marked `"locked": true` leads to a locked door, so you know before you
  walk it. Walking it takes the trolley to the door, a place of kind `locked_door` whose id is the
  gate's, such as `gate-1`, and the gate's puzzle joins the setlist the first time the trolley
  arrives there.
  - The puzzle can be answered only while the trolley stands at its door; from anywhere else the
    answer is refused with `not_at_door`. It can be worked on anywhere, and skipped from anywhere.
  - Solved, the door opens for the rest of the run and the trolley goes through in the same step.
    The corridor's length was charged on the way to the door; going through costs nothing more.
  - Failed or skipped, the door stays locked for the rest of the run.
- Actions: `walk`, `take`, `answer`, `skip` and `end`. Queries: all three.
- **Ends** `finished` once every question and claim is answered or skipped. A puzzle still open
  then is retired as skipped.
- **What counts:** each question as in the Reading Desk (§7.3), each claim as in Variorum (§7.5),
  the distance walked and the tokens used. A solved puzzle earns nothing but its open door.

## 8. Error codes

**Refused actions** (`outcome.invalid.code`; the step is spent, nothing else changes):

| Code | Why |
|---|---|
| `unreadable` | not JSON, or not exactly one of `action` and `query` |
| `unknown_action` | an action this quest does not have |
| `no_exit` | `walk` names no exit of this place |
| `bad_take` | `take` names something that cannot be taken here, or more than the trolley has room for |
| `no_item` | `to` names nothing open on the setlist |
| `bad_answer` | the answer has the wrong form for its item |
| `not_at_door` | the Overture: a puzzle answered away from its door |

**Failed queries** (`error.code`; nothing is charged):

| Code | Why |
|---|---|
| `bad_query` | an unknown query, or one with a missing or malformed field |
| `no_queries` | this quest has no queries (the Night Round, the Gate) |
| `not_available` | no volume with that id is lit where you are |
| `not_in_hall` | `read` on a volume that is not on the reading hall's shelves |
| `no_section` | the volume has no section with that number |

**Connection errors**, before the run starts: `protocol` and `bad_ticket` (§2).

## 9. Practice

Your starter holds a `compose.yml` that runs the arena and your container side by side, and
`SETUP.md` explains how to start them.

```
./practice selftest           # check the plumbing first
./practice R                  # a Reading Desk run on a practice instance
./practice O                  # the Overture for a team of three
./practice O --claims         # the Overture for a team of four, with claims
./practice --help             # every option
```

`./practice` takes the quest (`selftest`, `N`, `R`, `G`, `V` or `O`) and these options:

| Option | What it sets |
|---|---|
| `--instance 3` | which practice instance; any, if left out |
| `--questions`, `--puzzles`, `--claims` | how many items the run poses; `--claims` alone poses all of them, which in the Overture means a team of four's claims |
| `--silence 30` | minutes of silence that stop the run; 0 for never |
| `--max-steps 200` | stop the run after this many steps |

Practice instances come with the arena. Graded runs use other instances, never published.

**Traces and logs.** Every practice run leaves two files in `traces/`: the arena's trace, with every
message in both directions as the arena saw it, one JSON object per line; and your team's log,
which your container writes, with the same messages and every model call made through `llm.chat`.
When a run goes wrong, read both.

**Running code outside Docker.** The arena also listens on `ws://localhost:8765`; `SETUP.md`
shows how to run your code against it.
