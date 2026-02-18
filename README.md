# Minion Comms

Multi-agent coordination server inspired by RPG raid mechanics. MCP-based comms network for AI coding agents.

## What is this?

AI agents have finite context windows. When multiple agents work on the same codebase, they need coordination — who's doing what, what's been tried, where the traps are, and when someone's about to die (run out of context).

Minion Comms treats multi-agent engineering like an RPG raid. The codebase is the boss. Agents are the raid party. Context is reverse HP — you start full and every action drains you.

## Inspired by

- **Dead Drop Teams** — v1 of this system. SQLite message passing with role-based agents and auto-CC to lead. Minion Comms is the next evolution.
- **RPG raids** — party composition, class roles, HP management, buff coverage, loot systems
- **Majora's Mask** — `moon_crash` trigger word for emergency session shutdown
- **Final Fantasy** — `fenix_down` for knowledge dump before context death
- **Vercel/Next.js** — filesystem-as-database pattern for convention files
- **Military comms** — brevity codes, CC discipline, chain of command

## Core Concepts

### 5 Classes

| Class | Archetype | What they do |
|---|---|---|
| `lead` | Commander | Coordinates, routes tasks, manages HP bars |
| `coder` | DPS | Edits code — the only class that changes source |
| `builder` | Tank | Runs commands — build, test, deploy. No edits |
| `oracle` | Sage | Holds zone knowledge, answers questions. No edits, no commands |
| `recon` | Scout | Investigates external intel — web, other repos, ecosystem. Reports back |

Class = capabilities (permanent). Role = assignment (runtime). An oracle assigned to the audio zone becomes `oracle-audio`.

### Two Databases

| Database | Stores | Examples |
|---|---|---|
| **SQLite** (`messages.db`) | Coordination state | Agents, messages, task metadata, file claims, battle plans |
| **Filesystem** (`.dead-drop/`) | Knowledge | Intel, traps, zone notes, task specs, agent loot |

SQLite tracks *state*. Filesystem stores *knowledge*. Comms surfaces file locations, agents read the files.

### Enforcement Philosophy

Comms enforces what it owns (DB state). Reminds on what it can't verify (battle-time behavior).

**Enforced:** inbox discipline, context freshness, file claims, task dependencies, class restrictions, result files, battle plan requirement

**Reminded:** poll.sh running, agents reading files, following specs, HP truthfulness

### Role Hierarchy

```
user (the human)
└── general (puppet — relays user intent)
    └── commander (runs the fight — needs brains)
        └── zone-lead (owns a section)
            └── party (oracle, coder, builder, recon)
```

### Key Mechanics

- **HP** — context is reverse HP. Tracked via `set_context`. Lead monitors all bars.
- **Fenix Down** — dump knowledge to disk before context death. Come back clean.
- **Moon Crash** — emergency shutdown. Everyone fenix_down NOW.
- **Trigger Words** — brevity codes (sitrep, rally, retreat, hot_zone) save HP on both sides.
- **Activity Count** — auto-increments on every task update. High count = wrong approach.
- **File Claims** — prevents friendly fire. Can't edit a file another agent holds.
- **Intel/Traps** — confirmed findings and known hazards in filesystem. Oracle must read them.
- **Battle Journey** — agents must write up what they learned before a task can close.

## Status

Design phase. See [`docs/FRAMEWORK.md`](docs/FRAMEWORK.md) for the full specification.

## Lineage

v1: [dead-drop-teams](https://github.com/anthropics/dead-drop-teams) — basic message passing + task tracking

v2: **minion-comms** — RPG-inspired coordination with classes, HP management, knowledge persistence, enforcement philosophy, and trigger words
