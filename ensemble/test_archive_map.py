from archive_map import ArchiveMap

# The first two places of a practice run: exit 3 of the hall leads to room R5, entered by its exit 1.
HALL = {"kind": "reading_hall", "id": "H",
        "exits": [{"exit": 1, "length": 22}, {"exit": 2, "length": 16}, {"exit": 3, "length": 12}]}
R5 = {"kind": "room", "id": "R5", "volumes": [],
      "exits": [{"exit": 1, "length": 12}, {"exit": 2, "length": 17}]}


def at(position: dict, **outcome) -> dict:
    """A Night Round message with the trolley at this position."""
    return {"outcome": outcome, "trolley": {"position": position, "carrying": [], "capacity": 5}}


def walk(number: int) -> dict:
    return {"action": "walk", "exit": number}


def test_a_walk_joins_both_places_both_ways():
    archive = ArchiveMap()
    archive.observe(at(HALL), sent=None)
    archive.observe(at(R5, move={"walked": 12, "via": 1}), sent=walk(3))
    assert archive.leads == {("H", 3): "R5", ("R5", 1): "H"}
    assert archive.untried() == [("H", 1, 22), ("H", 2, 16), ("R5", 2, 17)]
    assert archive.distance("R5", "H") == 12
    assert archive.first_exit("H") == 1
    assert (archive.hall, archive.here, archive.volumes) == ("H", "R5", {"R5": []})


def test_a_refused_walk_adds_no_corridor():
    archive = ArchiveMap()
    archive.observe(at(HALL), sent=None)
    archive.observe(at(HALL, invalid={"code": "no_exit"}), sent=walk(7))
    assert archive.leads == {}
    assert len(archive.untried()) == 3


def test_the_shelves_show_what_a_take_left():
    archive = ArchiveMap()
    room = {"kind": "room", "id": "R1", "volumes": ["v-1", "v-2"], "exits": [{"exit": 1, "length": 3}]}
    archive.observe(at(room), sent=None)
    archive.observe(at({**room, "volumes": ["v-2"]}, took={"volumes": ["v-1"]}),
                    sent={"action": "take", "volumes": ["v-1"]})
    assert archive.volumes == {"R1": ["v-2"]}


def test_of_two_corridors_between_two_places_the_shorter_is_walked():
    archive = ArchiveMap()
    exits = [{"exit": 1, "length": 9}, {"exit": 2, "length": 4}]
    hall = {"kind": "reading_hall", "id": "H", "exits": exits}
    junction = {"kind": "junction", "id": "J", "exits": exits}
    archive.observe(at(hall), sent=None)
    # The short corridor first: the long one, walked later, must not replace it.
    archive.observe(at(junction, move={"walked": 4, "via": 2}), sent=walk(2))
    archive.observe(at(hall, move={"walked": 9, "via": 1}), sent=walk(1))
    assert archive.distance("H", "J") == 4
    assert archive.first_exit("J") == 2
    assert archive.untried() == []
