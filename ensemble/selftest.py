"""The self-test: read one volume, ask the model, send the answer back.

It proves the connection to the arena, a query, the model and an action all work. Then break the
prompt below and run it again: it must fail. A test that passes with and without the model was
never testing the model.
"""

from __future__ import annotations

import llm
from arena_client import ArenaClient


def run(arena: ArenaClient) -> bool:
    question = arena.observation["setlist"][0]
    volume = arena.observation["reading_hall"]["volumes"][0]

    text = arena.query("read", volume=volume, section=1)["reply"]["text"]

    prompt = (f"Text of section 1 of volume {volume}:\n{text}\n\nQuestion: {question['text']}\n"
              "Copy the number from the text exactly. Reply with the number only.")
    reply = llm.chat([{"role": "user", "content": prompt}], temperature=0, seed=7, max_tokens=1000)
    answer = (reply.choices[0].message.content or "").strip()

    result = arena.step({"action": "answer", "to": question["id"], "answer": answer})
    verdict = result["outcome"]["answer"]["result"]
    print(f"self-test: the model answered {answer!r}, which is {verdict}")
    if verdict != "correct":
        print("The arena, your container and the model are connected; the model's answer was "
              "wrong. Run the self-test again, and if it keeps failing, read the log in traces/.")
    return verdict == "correct"
