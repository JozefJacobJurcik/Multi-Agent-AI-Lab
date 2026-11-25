"""Plays the Improviser and its two baselines on practice instances of the Night Round, for the
comparison in M1 §2.1. Run it outside Docker, from ensemble/, as SETUP.md step 5 describes:

    docker compose up --detach arena
    export ARCHIVE_ARENA_URL=ws://localhost:8765
    set -a; . ./.env; set +a              # the model's settings, for the plain-prompt baseline
    python measure.py 1 2 3 --seeds 3

Every run gets its own ticket, with --silence 0: in practice runs only messages to the arena count as
hearing from the team, not model calls (README §2). The table has a row per run; `defaults` counts the
actions the Conductor chose in the variant's place, and a run that failed shows its error as the
reason. The summary follows M1: how many runs delivered every volume, and over those, the mean and
standard deviation of distance and tokens, per variant and instance (the spread over seeds), then the
mean distance per variant. The plain-prompt baseline calls the model at every step, so it is slow and
uses many tokens; --max-steps bounds it. --log FILE keeps every run's decisions, rule lines and model
replies; keep that file out of the repository.
"""

from __future__ import annotations

import argparse
import logging
import os
import statistics
import subprocess

import llm
from arena_client import connect
from baselines import DepthFirstWalker, PromptImproviser
from conductor import Conductor, Decision
from improviser import Improviser

COLUMNS = ["instance", "variant", "seed", "delivered", "distance", "exploring", "carrying", "steps",
           "tokens", "defaults", "reason"]


class Counting(Conductor):
    """The Conductor, counting the actions it chose itself in the variant's place."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.defaults = 0

    def _decide(self) -> Decision:
        decision = super()._decide()
        self.defaults += decision.by == "Conductor"
        return decision


def ticket(instance: int, max_steps: int) -> str:
    """A ticket for one practice run, asked for as ./practice does. The arena's errors reach stderr."""
    command = ["docker", "compose", "exec", "-T", "arena", "archive-arena", "practice", "--quest", "N",
               "--instance", str(instance), "--max-steps", str(max_steps), "--silence", "0"]
    return subprocess.run(command, stdout=subprocess.PIPE, text=True, check=True).stdout.strip()


def play(improviser: object, instance: int, max_steps: int) -> dict:
    """One run with this improviser, and what it delivered and spent."""
    tokens = llm.tokens
    arena = connect(os.environ["ARCHIVE_ARENA_URL"], ticket(instance, max_steps))
    total = arena.observation["quest"]["total"]
    conductor = Counting(arena, improviser=improviser)
    last = conductor.play()
    walked = getattr(improviser, "walked", {})  # the prompt baseline has no rules to split by
    return {"delivered": f"{len(last['reading_hall']['volumes'])}/{total}",
            "distance": last["spent"]["distance"], "exploring": walked.get("exploring", "–"),
            "carrying": walked.get("carrying", "–"), "steps": last["spent"]["steps"],
            "tokens": llm.tokens - tokens, "defaults": conductor.defaults, "reason": last.get("reason")}


def spread(values: list[int]) -> str:
    if len(values) < 2:
        return str(values[0])
    return f"{statistics.mean(values):.1f} ± {statistics.stdev(values):.1f}"


def summary(rows: list[dict]) -> str:
    """How many runs delivered every volume, and over those, their distance and tokens."""
    finished = [row for row in rows if row["reason"] == "finished"]
    text = f"every volume delivered in {len(finished)} of {len(rows)} runs"
    if finished:
        text += (f"; over those, distance {spread([row['distance'] for row in finished])}, "
                 f"tokens {spread([row['tokens'] for row in finished])}")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("instances", type=int, nargs="+", help="the practice instances to play")
    parser.add_argument("--seeds", type=int, default=3, help="plain-prompt runs per instance")
    parser.add_argument("--max-steps", type=int, default=200, help="the arena stops a run there")
    parser.add_argument("--log", help="a file for every run's decisions, rule lines and model replies")
    args = parser.parse_args()
    if args.log:
        logging.basicConfig(filename=args.log, level=logging.INFO,
                            format="%(asctime)s %(name)s %(message)s")

    print("| " + " | ".join(COLUMNS) + " |")
    print("|" + "---|" * len(COLUMNS))
    runs: dict[tuple[str, int], list[dict]] = {}
    for instance in args.instances:
        variants = [("nearest-exit", "–", Improviser()), ("depth-first", "–", DepthFirstWalker())]
        variants += [("prompt", seed, PromptImproviser(seed)) for seed in range(args.seeds)]
        for variant, seed, improviser in variants:
            row = {"instance": instance, "variant": variant, "seed": seed}
            try:
                row |= play(improviser, instance, args.max_steps)
            except Exception as error:  # one failed run must not stop the comparison
                row |= dict.fromkeys(COLUMNS[3:-1], "–") | {"reason": f"failed: {error!r}"}
            runs.setdefault((variant, instance), []).append(row)
            print("| " + " | ".join(str(row[column]) for column in COLUMNS) + " |", flush=True)

    print()
    for (variant, instance), rows in runs.items():
        print(f"{variant}, instance {instance}: {summary(rows)}")
    for variant in dict.fromkeys(variant for variant, _ in runs):
        rows = [row for (name, _), group in runs.items() if name == variant for row in group]
        distances = [row["distance"] for row in rows if row["reason"] == "finished"]
        mean = f"{statistics.mean(distances):.1f}" if distances else "–"
        print(f"{variant}, all instances: every volume delivered in {len(distances)} of {len(rows)} "
              f"runs; mean distance over those {mean}")


if __name__ == "__main__":
    main()
