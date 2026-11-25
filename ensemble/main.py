"""The container's entry point. Every run setting comes from the environment.

ARCHIVE_ARENA_URL   the arena's address
ARCHIVE_TICKET      the ticket for this run; the arena's first message names the quest
(and the three ARCHIVE_LLM_ settings, which only llm/ reads)

It plays the self-test itself and hands the base quests to the Conductor, with the team's
specialists (docs/conductor.md). Any other quest stops after the arena's first message.

Each run writes the team's log to traces/, beside the arena's trace of the same run: every message
to and from the arena (logger "arena_client"), every model call (logger "llm") and every decision
(logger "conductor"). Add your own entries with logging.getLogger("your-agent").info(...).
"""

from __future__ import annotations

import logging
import os
import sys

import selftest
from arena_client import connect
from conductor import Conductor
from improviser import Improviser


def main() -> int:
    ticket = os.environ["ARCHIVE_TICKET"]
    os.makedirs("traces", exist_ok=True)
    logging.basicConfig(filename=f"traces/team-{ticket}.log", level=logging.INFO,
                        format="%(asctime)s %(name)s %(message)s")
    arena = connect(os.environ["ARCHIVE_ARENA_URL"], ticket)
    quest = arena.observation["quest"]["id"]
    print(f"Playing quest {quest} with ticket {ticket}")
    if quest == "selftest":
        passed = selftest.run(arena)
        print(f"The run is over: {arena.observation.get('reason')}")
        return 0 if passed else 1
    if quest in ("N", "R", "G"):
        last = Conductor(arena, improviser=Improviser()).play()
        print(f"The run is over: {last.get('reason')}")
        return 0

    arena.close()
    print(f"No code plays quest {quest} yet, so the run stops here. Its first message is in "
          f"traces/: in your log, team-{ticket}.log, and in the arena's trace.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
