"""A blocking client for the arena: websockets and JSON, nothing more.

    arena = connect(url, ticket)        # sends the ticket; the arena's first message arrives
    obs = arena.observation             # the latest observation
    obs = arena.step(action)            # an action, such as {"action": "walk", "exit": 2}
    reply = arena.query("read", volume="v-4326", section=3)   # a query; no turn passes

The message that carries "done": true is the arena's last; the arena then closes the connection.
Every message in both directions goes into the team's log (see main.py).
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import ExitStack

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection
from websockets.sync.client import connect as ws_connect

PROTOCOL = 1
log = logging.getLogger(__name__)


class ArenaError(Exception):
    """The arena refused the connection: a bad ticket, or a protocol it does not speak."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ArenaClient:
    def __init__(self, url: str, ticket: str, wait: float = 30):
        self._stack = ExitStack()
        self._ws = self._stack.enter_context(_open(url, wait))
        self._send({"hello": {"ticket": ticket, "protocol": PROTOCOL}})
        first = self._receive()
        if "error" in first:
            self.close()
            raise ArenaError(first["error"]["code"])
        self.observation: dict = first

    @property
    def done(self) -> bool:
        return bool(self.observation.get("done"))

    def step(self, action: dict) -> dict:
        """Send one action and return what it did with the new observation."""
        if self.done:
            raise RuntimeError("the run is over")
        self._send(action)
        self.observation = self._receive()
        if self.done:
            self.close()
        return self.observation

    def query(self, name: str, **arguments) -> dict:
        """Send one query and return the arena's reply: `reply` or `error`, `charged`, `spent`."""
        if self.done:
            raise RuntimeError("the run is over")
        self._send({"query": name, **arguments})
        return self._receive()

    def close(self) -> None:
        self._stack.close()

    def __enter__(self) -> ArenaClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _send(self, message: dict) -> None:
        text = json.dumps(message)
        log.info("sent %s", text)
        try:
            self._ws.send(text)
        except ConnectionClosed:
            raise RuntimeError("the arena closed the connection") from None

    def _receive(self) -> dict:
        try:
            text = self._ws.recv()
        except ConnectionClosed:
            raise RuntimeError("the arena closed the connection") from None
        log.info("received %s", text)
        return json.loads(text)


def _open(url: str, wait: float) -> ClientConnection:
    """Connect, retrying for a while: the arena may still be starting."""
    deadline = time.monotonic() + wait
    while True:
        try:
            return ws_connect(url, max_size=None)
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)


def connect(url: str, ticket: str) -> ArenaClient:
    return ArenaClient(url, ticket)
