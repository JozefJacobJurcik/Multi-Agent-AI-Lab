# Context

Shared terms and decisions for the team's code. Use these names in code and in talk.

## Terms

- **Conductor**: plain code at the top. Holds the one arena connection, runs the loop, checks every action and hands each decision to one specialist.
- **Specialists**: Improviser (map and trolley, quest N), Musicologist (reading and questions, quest R), Player (puzzles, quest G).
- **Quests**: `selftest`, `N`, `R`, `G`, `O` (Overture, the whole ensemble). `V` is for teams of four, not ours.
- **Item**: one entry of the setlist: `question-*`, `gate-*` or `claim-*`.
- **Proposal**: a part's suggested answer to an item: answer, supporting volumes, confidence, author.
- **Shared store**: memory for one run, used by the Conductor and all specialists.
- **Action / query**: actions (`walk`, `take`, `answer`, `skip`, `end`) change the run. Queries (`browse`, `examine`, `read`) take no turn, but every `examine` and `read` is charged, even a repeated one.
- **Wrapper**: `llm.chat`, the only place the model is called.

## Decisions

1. The shared store is memory only. It never talks to the arena.
2. The Conductor hands every arena message to the shared store, together with the action or query it sent.
3. Arena replies are stored complete and unchanged. The store keeps no history of all messages; that is in the team log in `traces/`.
4. The Musicologist looks in the shared store before it queries the arena, and queries only for text that is not there yet.
5. The budget per question is tracked by the Musicologist, not by the store.
6. The map lives in the shared store, as M1 says. Jozef builds it on top of the store once the store's interface is settled. Leonie's view: the signs and room topics the Musicologist needs arrive in every observation anyway, so the map could also be the Improviser's own module if that is simpler for Jozef.

The store's interface: [docs/shared-store.md](docs/shared-store.md).

## Sources

- Rules and API: [README.md](README.md)
- M1 (agent designs, team part §2.2, plans §3): [Jurcik](../Jurcik/M1/m1.tex), [Merkl](../Merkl/M1/m1.tex), [Mukherjee](../M1_Indrakshee%20Mukherjee.pdf)
