# Setting up your team's container

Your team works with two containers. The **arena** runs the game: it is the same for every team,
and you get it as a ready-made image. The **team** container is yours: it is built from this
folder, connects to the arena and plays one run each time it starts. Your code calls the course
model on Morpheus.

```
  your machine
  ┌─ one Docker network ────────────────────────────────┐
  │                                                     │
  │  arena ◄── ws://arena:8765 ── team (your code) ─────┼────► Morpheus
  │    │                                                │
  └────┼────────────────────────────────────────────────┘
       └── also open on your machine at ws://localhost:8765
```

`compose.yml` sets this up: it starts both containers on one network and tells yours where the
arena is. You change nothing in it. All you add is your Morpheus key, in a file of its own (step 2).

## What you need

- **Docker** with Compose: Docker Desktop on macOS and Windows, or Docker Engine with the Compose
  plugin on Linux. On Windows, type the commands below in a WSL terminal (Windows Subsystem for
  Linux, which Docker Desktop uses too), since `./practice` is a shell script.
- **The arena image** from Moodle, the file for your kind of processor:
  `archive-arena-<date>-arm64.tar.gz` for Apple Silicon, `archive-arena-<date>-amd64.tar.gz` for
  Intel and AMD.
- **Your Morpheus key**, from Morpheus under *Profil > Einstellungen > Account*.

Type every command below in this folder, `ensemble/`, unless a step says otherwise.

## 1. Load the arena

```
docker load -i ~/Downloads/archive-arena-<date>-arm64.tar.gz     # or -amd64
docker image ls archive-arena          # one line, tagged latest
```

Give the path to wherever you saved the file from Moodle; it does not need to be in this folder.

Load it again whenever a new arena file appears on Moodle.

## 2. Connect the model

```
cp .env.example .env
```

`.env.example` is in this folder, `ensemble/`, beside this guide, but you may not see it: files
whose names start with a dot are hidden. `ls -a` lists them, and in the Finder on macOS Cmd+Shift+.
shows them. Open `.env` and put your key after `ARCHIVE_LLM_KEY=`. The other two lines name Morpheus
and the course model; leave them as they are. `.env` holds your key, so never commit it or copy it
into your image: `.gitignore` and `.dockerignore` already keep it out.

## 3. Check the plumbing

```
./practice selftest
```

This starts the arena, asks it for a practice ticket, builds your container and runs it with that
ticket. The first build takes a minute. The self-test reads one volume, asks the model a question
about it and sends back the answer. It ends with lines like

```
Playing quest selftest with ticket T-e7eac44a7bae
self-test: the model answered '1987', which is correct
The run is over: finished
```

If you get there, the arena, your container and the model all work together.

## 4. Play the quests

```
./practice R                  # a Reading Desk run
./practice O                  # the Overture for a team of three
./practice O --claims         # the Overture for a team of four, with claims
./practice --help             # the quests and every option
```

`./practice` rebuilds your container each time, so it always runs your latest code. The arena keeps
running between runs.

Until your code plays a quest, a run of it starts, the arena sends its first message, and your
container stops with a line saying where your code goes: in `main.py`, at "Your code starts here".
That first message is in both files in `traces/`, described next: read it there.

Every run leaves two files in `traces/`, both named with the run's ticket:

- **the arena's trace**, such as `20261104-163102-selftest-e7eac44a7bae.jsonl`: every message as the
  arena received and sent it, one JSON object per line;
- **your team's log**, such as `team-T-e7eac44a7bae.log`: written by your container, with every
  message to and from the arena and every model call made through `llm.chat`, with the text of its
  reply. `main.py` starts it. Add your own entries with Python's `logging`, for instance
  which agent acted and why.

When a run goes wrong, read both. The API reference explains the messages and the options: it is
this folder's `README.md`.

Everything in this folder goes into your container, except what `.dockerignore` keeps out: your
key, `.venv/` and `traces/`. When your code uses a new package, add it to `requirements.txt`. A
graded run can download nothing, so what is missing from the image is missing for good.

When you are done for the day:

```
docker compose down
```

## 5. Run your code outside Docker

While you develop, you can run your code straight from your machine, with a debugger or in a
notebook. The arena listens on `ws://localhost:8765` as well:

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
docker compose up --detach arena
export ARCHIVE_ARENA_URL=ws://localhost:8765
export ARCHIVE_TICKET=$(docker compose exec -T arena archive-arena practice --quest selftest)
set -a; . ./.env; set +a              # the three ARCHIVE_LLM_ settings
python main.py
```

A ticket is good for one run, so ask for a new one before each run.

## The five settings

Your container reads everything it needs from the environment and nothing else. Never write an
address or a key into your code.

| Setting | Set by | What it holds |
|---|---|---|
| `ARCHIVE_ARENA_URL` | `compose.yml` | the arena's address: `ws://arena:8765` inside Docker |
| `ARCHIVE_TICKET` | `./practice` | the ticket for this run |
| `ARCHIVE_LLM_URL` | `.env` | the model endpoint |
| `ARCHIVE_LLM_MODEL` | `.env` | the model's id |
| `ARCHIVE_LLM_KEY` | `.env` | your Morpheus key |

In a graded run we start your container ourselves and set all five: the arena is ours, and the
model endpoint and key are ours too. Your container then reaches nothing but those two, so
everything it needs must be in its image.

## When something goes wrong

| You see | What to do |
|---|---|
| `pull access denied for archive-arena` or `No such image` | load the arena image (step 1) |
| `The requested image's platform (linux/amd64) does not match` | you loaded the file for the other processor; load the right one |
| `Cannot connect to the Docker daemon` | start Docker Desktop |
| `env file … .env not found`, or a 401 error from the model | `.env` is missing or has no key (step 2) |
| `the model answered …, which is incorrect` | the model and the arena work; the answer was wrong. Run it again, then read the log |
| `port is already allocated` for 8765 | another arena is still running: `docker compose down`, or stop the other one |
| `The run is over: stopped` | the arena stopped the run: your code was silent for ten minutes, or reached the step limit you set with `--max-steps`. The end of the arena's trace in `traces/` shows which; see "How a run ends" in `README.md` |
| `the run is over` | your code sent something after the run had ended; stop once `arena.done` is true |
| `the arena closed the connection` | the connection closed during the run; read the arena's trace and your log in `traces/` to see why |
| `ArenaError: bad_ticket` | that ticket was used already, or the arena was restarted since it was issued; ask for a new one |
| `No code plays quest … yet, so the run stops here` | nothing in `main.py` plays that quest yet: your code starts at "Your code starts here" |
