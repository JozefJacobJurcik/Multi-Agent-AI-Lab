# Shared store: interface

Settled in a grilling session on 2026-11-23 (Leonie). Terms as in [CONTEXT.md](../CONTEXT.md). Code: `store.py`, tests: `test_store.py`.

## Methods

| Method | Who calls it | What it does |
|---|---|---|
| `observe(message, sent)` | Conductor, after every arena message | files what the message carries (see below). `sent` is the action or query that was sent, `None` for the first message |
| `quest` | Conductor | the first message's `quest` (id, goal, `total` in the Night Round). The Conductor routes by it |
| `item(id)` | everyone | the item in full, with its text, which the arena sends only once |
| `open_items()` | Conductor | the ids of the items without a result yet |
| `text(volume, section)` | Musicologist | for a `read` the section's text, for an `examine` (`section=None`) the whole reply unchanged; `None` if not read yet |
| `propose(item, proposal)` | specialists | adds a proposal for the item |
| `best(item)` | Conductor | the last proposal; `None` means skip. Asked only for `open_items()` |

## What `observe` files

| It finds | It keeps |
|---|---|
| `quest` (first message only) | `quest` |
| a setlist item with `text` | the item, under its id |
| `spent` | the latest `spent` |
| `outcome.answer` | the item's result (`correct`, `incorrect`, `skipped`) |
| any observation | it replaces the latest observation |
| `sent` is a `read` and the reply has `reply` | the text under `(volume, section)` |
| `sent` is an `examine` and the reply has `reply` | the reply under `(volume, None)` |
| a reply with `error` | nothing but `spent` |

A query reply does not reliably name its volume and section, which is why `observe` needs `sent`.

A refused action (`outcome.invalid`) leaves the item open: the store records no result, only the new observation (the old one with one more step).

## Proposal

A small class `Proposal` with fixed fields: `answer`, `supporting` (volume ids, as the arena expects them), `confidence`, `author`. Fixed fields make a typo fail at once, not in the arena.
