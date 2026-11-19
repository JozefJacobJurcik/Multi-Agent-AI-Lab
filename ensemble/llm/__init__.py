"""The one place a model endpoint is named: it is read from the environment. Every call through
chat() goes into the team's log (see main.py).

ARCHIVE_LLM_URL     the endpoint's address (Morpheus while you develop; ours in graded runs)
ARCHIVE_LLM_MODEL   the model's id
ARCHIVE_LLM_KEY     your Morpheus key while you develop; in graded runs we set it

The endpoint is OpenAI-compatible, so any client works.
"""

from __future__ import annotations

import json
import logging
import os

from openai import OpenAI

log = logging.getLogger(__name__)


def client() -> OpenAI:
    # The endpoint gives up on a call after 300 seconds. Retries are left to you.
    return OpenAI(base_url=os.environ["ARCHIVE_LLM_URL"], api_key=os.environ["ARCHIVE_LLM_KEY"],
                  timeout=300, max_retries=0)


def model() -> str:
    return os.environ["ARCHIVE_LLM_MODEL"]


def chat(messages: list[dict], **options):
    """One call to the model; the messages sent and the text of the reply go into the log."""
    log.info("call %s", json.dumps({"messages": messages, **options}))
    reply = client().chat.completions.create(model=model(), messages=messages, **options)
    log.info("reply %s", reply.choices[0].message.content)
    return reply
