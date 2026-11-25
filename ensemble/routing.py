"""Rule 4 of the Improviser: the remaining trips, once every volume has been seen (M1 §2.1).

This is capacitated routing: trips from the reading hall and back, each with at most a trolley load,
as short as possible in all. A room may be emptied over several trips (README §4: a take names "at
least one volume"). The first trip is the one under way: it starts where the trolley stands, with
what it carries. While the search is small every plan is tried, otherwise the savings heuristic of
Clarke and Wright (1964) is used.

A plan is the list of stops in order: (room, n) takes n volumes there, (hall, 0) unloads.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from itertools import combinations
from math import prod

Stop = tuple[str, int]
Distance = Callable[[str, str], int]

# The largest search tried in full: under a second and 80 MB (timed on 25 Nov 2026). Ten volumes and a
# trolley of five, as in practice instance 1, never need more than 75,000.
EXACT_STATES = 200_000
# The full search also goes about two calls deep per volume (a take, then the way home), and Python
# stops at 1,000: with 500 volumes in one room it failed.
EXACT_VOLUMES = 300
TROLLEY = None  # in a savings trip: where the trolley stands, at the head of the trip under way


def plan(here: str, load: int, left: dict[str, int], capacity: int, hall: str,
         distance: Distance) -> list[Stop]:
    """The stops of the remaining trips. `left` is how many volumes each room still holds."""
    distance = cache(distance)  # both methods ask for the same few distances again and again
    states = (len(left) + 2) * (capacity + 1) * prod(n + 1 for n in left.values())
    if states <= EXACT_STATES and sum(left.values()) <= EXACT_VOLUMES:
        return best_plan(here, load, left, capacity, hall, distance)
    return savings_plan(here, load, left, capacity, hall, distance)


def best_plan(here: str, load: int, left: dict[str, int], capacity: int, hall: str,
              distance: Distance) -> list[Stop]:
    """The shortest plan: every order of stops is tried, with every number of volumes to take.

    A path that passes the hall unloads early, which only leaves more room than planned; the plan
    with that stop made explicit is tried too, so the result is still the shortest.
    """
    rooms = list(left)

    @cache
    def best(place: str, load: int, counts: tuple[int, ...]) -> tuple[int, tuple[Stop, ...]]:
        if not any(counts):
            return distance(place, hall), ((hall, 0),)
        options = []
        if load:
            walked, stops = best(hall, 0, counts)
            options.append((distance(place, hall) + walked, ((hall, 0), *stops)))
        for i, room in enumerate(rooms):
            for n in range(1, min(counts[i], capacity - load) + 1):
                walked, stops = best(room, load + n, counts[:i] + (counts[i] - n,) + counts[i + 1:])
                options.append((distance(place, room) + walked, ((room, n), *stops)))
        # Of equally short plans, the one with the fewest stops: one take of four, not four of one.
        return min(options, key=lambda option: (option[0], len(option[1])))

    return list(best(here, load, tuple(left.values()))[1])


def savings_plan(here: str, load: int, left: dict[str, int], capacity: int, hall: str,
                 distance: Distance) -> list[Stop]:
    """Clarke and Wright's savings heuristic, for when there are too many plans to try them all.

    The trip under way first takes what fits where the trolley stands, since those volumes would
    otherwise need a walk back. A room with more than a trolley load then gets full trips of its own.
    Then every room starts on a trip of its own, and trips are joined end to end, where joining saves
    the most walking first, as long as the trolley can carry both loads. The trip under way starts
    where the trolley stands, so it can only grow at its end.
    """
    taken_here = []
    if left.get(here) and load < capacity:
        n = min(capacity - load, left[here])
        taken_here, load, left = [(here, n)], load + n, {**left, here: left[here] - n}
    full = [stop for room, n in left.items() for _ in range(n // capacity)
            for stop in ((room, capacity), (hall, 0))]
    loads = {TROLLEY: load} | {room: n % capacity for room, n in left.items() if n % capacity}

    def saving(a: str | None, b: str | None) -> int:
        """What one trip through a, then b, walks less than a trip that ends at a and one from b."""
        a, b = (here if node is TROLLEY else node for node in (a, b))
        return distance(a, hall) + distance(hall, b) - distance(a, b)

    trip_of = {node: [node] for node in loads}
    pairs = sorted(((saving(a, b), a, b) for a, b in combinations(loads, 2)),
                   key=lambda pair: pair[0], reverse=True)
    for gain, a, b in pairs:
        if gain <= 0:
            break  # no join saves anything any more
        first, second = trip_of[a], trip_of[b]
        if first is second or sum(loads[node] for node in first + second) > capacity:
            continue
        if TROLLEY in second:  # the trip under way stays in front
            a, b, first, second = b, a, second, first
        if first[-1] != a and TROLLEY not in first:
            first.reverse()
        if second[0] != b:
            second.reverse()
        if first[-1] != a or second[0] != b:  # a or b lies inside its trip, not at an end
            continue
        first += second
        for node in second:
            trip_of[node] = first

    trips = []
    for trip in trip_of.values():  # the trip under way first, as the trolley is the first node
        if trip not in trips:
            trips.append(trip)
    stops = [stop for trip in trips
             for stop in [(room, loads[room]) for room in trip if room is not TROLLEY] + [(hall, 0)]]
    return taken_here + stops + full
