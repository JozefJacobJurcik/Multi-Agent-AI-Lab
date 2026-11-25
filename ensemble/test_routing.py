from functools import cache

import networkx as nx

from routing import best_plan, plan, savings_plan


def distances(*corridors: tuple[str, str, int]):
    """The shortest distances between the places these corridors join."""
    graph = nx.Graph()
    graph.add_weighted_edges_from(corridors, weight="length")
    return cache(lambda a, b: nx.shortest_path_length(graph, a, b, weight="length"))


def walked(stops, here, load, left, capacity, distance) -> int:
    """The distance the stops walk from here. Checks every take and that every room is emptied."""
    left, total = dict(left), 0
    for place, n in stops:
        total, here = total + distance(here, place), place
        if place == "H":
            load = 0
        assert 0 <= n <= left.get(place, 0) and load + n <= capacity
        if n:
            left[place] -= n
            load += n
    assert here == "H" and not any(left.values())
    return total


def test_volumes_near_the_hall_wait_for_the_way_back():
    # Hall -1- A (3 volumes) -99- B (4), a trolley of 5: taking A's volumes on the way out walks 400,
    # leaving them for the way back 202.
    distance = distances(("H", "A", 1), ("A", "B", 99))
    left = {"A": 3, "B": 4}
    assert walked(plan("H", 0, left, 5, "H", distance), "H", 0, left, 5, distance) == 202


def test_of_equally_short_plans_the_one_with_the_fewest_stops():
    # Home first or a part now: 30 either way, and four takes of one would be as short.
    distance = distances(("H", "J", 4), ("J", "R2", 6))
    assert best_plan("R2", 3, {"R2": 4}, 5, "H", distance) == [("H", 0), ("R2", 4), ("H", 0)]


def test_savings_joins_rooms_that_lie_on_one_way():
    distance = distances(("H", "A", 10), ("A", "B", 1), ("B", "H", 10))
    left = {"A": 2, "B": 2}
    # One trip of 21, not two of 20.
    assert walked(savings_plan("H", 0, left, 5, "H", distance), "H", 0, left, 5, distance) == 21


def test_savings_takes_what_fits_where_the_trolley_stands():
    # An empty trolley in a room holding one load: home with it walks 10, home and back for it 30.
    distance = distances(("H", "R", 10))
    assert savings_plan("R", 0, {"R": 5}, 5, "H", distance) == [("R", 5), ("H", 0)]


def test_the_trip_under_way_grows_only_at_its_end():
    # The trolley stands in T. Its trip takes B, then A on the way home, and C gets a trip of its own:
    # 30. Turning the trip round to add C as well would start it in C, not where the trolley is: 32.
    distance = distances(("H", "C", 6), ("H", "A", 2), ("A", "B", 8), ("B", "T", 8), ("C", "T", 7))
    left = {"A": 1, "B": 2, "C": 2}
    assert walked(savings_plan("T", 0, left, 5, "H", distance), "T", 0, left, 5, distance) == 30


def test_both_plans_start_from_the_trolley_and_split_a_room_of_more_than_a_load():
    distance = distances(("H", "J", 4), ("J", "A", 3), ("J", "B", 5), ("B", "C", 2), ("H", "C", 9))
    left = {"A": 7, "B": 2, "C": 3}
    exact = walked(best_plan("B", 3, left, 5, "H", distance), "B", 3, left, 5, distance)
    heuristic = walked(savings_plan("B", 3, left, 5, "H", distance), "B", 3, left, 5, distance)
    assert exact <= heuristic


def test_too_large_a_search_falls_back_on_savings():
    rooms = [f"R{i}" for i in range(12)]
    distance = distances(*[("H", room, 10 + i) for i, room in enumerate(rooms)])
    left = dict.fromkeys(rooms, 4)
    stops = plan("H", 0, left, 5, "H", distance)
    assert stops == savings_plan("H", 0, left, 5, "H", distance)
    walked(stops, "H", 0, left, 5, distance)  # every take fits and every room is emptied


def test_a_large_stock_in_few_rooms_falls_back_on_savings():
    # Few states, but the full search would go about 1,000 calls deep.
    distance = distances(("H", "R", 10))
    assert walked(plan("H", 0, {"R": 500}, 5, "H", distance), "H", 0, {"R": 500}, 5, distance) == 2000
