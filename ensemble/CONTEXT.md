# Context

Shared terms and decisions for the team's code. Use these names in code and in talk.

## Terms

- **Conductor**: plain code at the top. Holds the one arena connection, runs the loop, checks every action and hands each decision to one specialist.
- **Specialists**: Improviser (map and trolley, quest N), Musicologist (reading and questions, quest R), Player (puzzles, quest G).
- **Quests**: `selftest`, `N`, `R`, `G`, `O` (Overture, the whole ensemble). `V` is for teams of four, not ours.
- **Item**: one entry of the setlist: `question-*`, `gate-*` or `claim-*`.
- **Proposal**: a part's suggested answer to an item: answer, supporting volumes, confidence, author.
- **Feedback**: why a proposal or action failed the Conductor's check. The specialist gets it back once.
- **Decision log**: one line per action in the team log: the deciding part, why, its tokens and its change in `spent`.
- **Shared store**: memory for one run, used by the Conductor and all specialists.
- **Map**: the places, exits, corridors and shelves the trolley has seen, kept in the shared store.
- **Plan**: the Improviser's stops for the remaining trips, made once every volume has been seen or no exit is left to try, and made again if it runs out with volumes still on a shelf.
- **Action / query**: actions (`walk`, `take`, `answer`, `skip`, `end`) change the run. Queries (`browse`, `examine`, `read`) take no turn, but every `examine` and `read` is charged, even a repeated one.
- **Wrapper**: `llm.chat`, the only place the model is called.

## Decisions

1. The shared store is memory only. It never talks to the arena.
2. The Conductor hands every arena message to the shared store, together with the action or query it sent.
3. Arena replies are stored complete and unchanged. The store keeps no history of all messages; that is in the team log in `traces/`.
4. The Musicologist looks in the shared store before it queries the arena, and queries only for text that is not there yet.
5. The budget per question is tracked by the Musicologist, not by the store.
6. The map lives in the shared store, as M1 says: `store.map` (`archive_map.py`). `observe` files every place the trolley reaches and every corridor it walks, the Conductor's default walks included.
7. Specialists never use the arena. They return a proposal or an action, and they query through `Conductor.query`.
8. Every action is checked in code before it is sent (`checks.py`). What fails goes back once, with the reason. Then the Conductor sends the last proposal in the store if it is well-formed, else a default that uses no tokens: a skip, or the nearest exit. Three nearest-exit defaults in a row end a Night Round. In the Night Round an action the arena refuses also goes back to the Improviser once, with the arena's reason; if the arena refuses its next action as well, the Conductor walks the nearest exit.
9. The Conductor files every well-formed proposal it gets. Specialists file their best answer so far themselves.
10. The Conductor plays the base quests. The Overture follows once the Improviser's distances and the Musicologist's ratings exist.

The store's interface: [docs/shared-store.md](docs/shared-store.md). The Conductor's: [docs/conductor.md](docs/conductor.md).

## Sources

- Rules and API: [README.md](README.md)
- M1 (agent designs, team part §2.2, plans §3): [Jurcik](../Jurcik/M1/m1.tex), [Merkl](../Merkl/M1/m1.tex), [Mukherjee](../M1_Indrakshee%20Mukherjee.pdf)
