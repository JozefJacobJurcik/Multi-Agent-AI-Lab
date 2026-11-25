"""The map of the archive, as far as the trolley has seen it. It lives in the shared store
(CONTEXT.md, decision 6), which hands it every arena message together with the action sent.

A place is filed when the trolley arrives: its exits with their lengths and, in a room, the volumes
on its shelves. A walk adds its corridor both ways, since the exit the trolley arrived by leads back
(README §4). Until it is walked, an exit shows only its length. Shortest paths come from NetworkX
(Hagberg et al., 2008).
"""

from __future__ import annotations

import networkx as nx


class ArchiveMap:
    def __init__(self) -> None:
        self.graph = nx.Graph()  # the places reached, joined by the corridors walked
        self.exits: dict[str, dict[int, int]] = {}  # place -> {exit: length}, places in the order found
        self.leads: dict[tuple[str, int], str] = {}  # (place, exit) -> where it leads, once walked
        self.volumes: dict[str, list[str]] = {}  # room -> the volumes on its shelves when last seen
        self.here: str | None = None
        self.hall: str | None = None

    def observe(self, message: dict, sent: dict | None) -> None:
        """File where the trolley stands and, after a walk, the corridor that brought it there."""
        if "trolley" not in message:
            return
        position = message["trolley"]["position"]
        move = message.get("outcome", {}).get("move")
        if move and sent and sent.get("action") == "walk":
            self._join(self.here, sent["exit"], position["id"], move["via"], move["walked"])
        self.here = position["id"]
        self.graph.add_node(self.here)
        self.exits[self.here] = {e["exit"]: e["length"] for e in position.get("exits", [])}
        if position["kind"] == "reading_hall":
            self.hall = self.here
        if "volumes" in position:
            self.volumes[self.here] = list(position["volumes"])

    def untried(self) -> list[tuple[str, int, int]]:
        """Every exit not walked yet, as (place, exit, length)."""
        return [(place, number, length) for place, exits in self.exits.items()
                for number, length in exits.items() if (place, number) not in self.leads]

    def distance(self, start: str, end: str) -> int:
        """The length of the shortest known path."""
        return nx.shortest_path_length(self.graph, start, end, weight="length")

    def first_exit(self, place: str) -> int:
        """The exit here that starts the shortest known path to the place."""
        path = nx.shortest_path(self.graph, self.here, place, weight="length")
        return self.graph.edges[self.here, path[1]]["exit_at"][self.here]

    def _join(self, start: str, start_exit: int, end: str, end_exit: int, length: int) -> None:
        self.leads[start, start_exit] = end
        self.leads[end, end_exit] = start
        known = self.graph.get_edge_data(start, end)
        # A corridor back to the same place shortens no path; of two between the same places, the
        # shorter is the one to walk.
        if start != end and (known is None or length < known["length"]):
            self.graph.add_edge(start, end, length=length, exit_at={start: start_exit, end: end_exit})
