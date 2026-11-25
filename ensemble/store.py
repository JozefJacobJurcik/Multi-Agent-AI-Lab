"""The shared store: memory for one run, used by the Conductor and all specialists.

It never talks to the arena. The Conductor hands it every arena message with what it sent, and the
store keeps what the parts need later. Interface and rules: docs/shared-store.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from archive_map import ArchiveMap


@dataclass
class Proposal:
    """A part's suggested answer to an item."""

    answer: object
    supporting: list[str]
    confidence: float
    author: str


class SharedStore:
    def __init__(self) -> None:
        self.quest: dict | None = None
        self.observation: dict | None = None
        self.last_action: dict | None = None
        self.spent: dict | None = None
        self.map = ArchiveMap()
        self._items: dict[str, dict] = {}
        self._results: dict[str, str] = {}
        self._texts: dict[tuple[str, int | None], object] = {}
        self._proposals: dict[str, list[Proposal]] = {}

    def observe(self, message: dict, sent: dict | None) -> None:
        """File one arena message. `sent` is the action or query that was sent, None at the start."""
        if "spent" in message:
            self.spent = message["spent"]

        if "query" in message:
            if "reply" in message and sent is not None:
                self._file_query(message["reply"], sent)
            return

        self.map.observe(message, sent)
        self.observation = message
        self.last_action = sent
        if "quest" in message:
            self.quest = message["quest"]
        for item in message.get("setlist", []):
            if "text" in item:
                self._items[item["id"]] = item
        answer = message.get("outcome", {}).get("answer")
        if answer is not None:
            self._results[answer["to"]] = answer["result"]

    def item(self, id: str) -> dict | None:
        return self._items.get(id)

    def open_items(self) -> list[str]:
        return [id for id in self._items if id not in self._results]

    def text(self, volume: str, section: int | None) -> object:
        return self._texts.get((volume, section))

    def volume_text(self, volume: str) -> str:
        """The volume's title and abstract if examined, and every section read, as one text."""
        parts = []
        for (kept, section), text in self._texts.items():
            if kept != volume:
                continue
            if section is None:  # an examine: the whole reply
                parts += [text.get("title", ""), text.get("abstract", "")]
            else:
                parts.append(text)
        return "\n".join(parts)

    def propose(self, item: str, proposal: Proposal) -> None:
        self._proposals.setdefault(item, []).append(proposal)

    def best(self, item: str) -> Proposal | None:
        proposals = self._proposals.get(item)
        return proposals[-1] if proposals else None

    def _file_query(self, reply: dict, sent: dict) -> None:
        if sent.get("query") == "read":
            self._texts[(sent["volume"], sent["section"])] = reply["text"]
        elif sent.get("query") == "examine":
            self._texts[(sent["volume"], None)] = reply
