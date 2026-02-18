# Minion Comms

Multi-agent coordination server inspired by RPG raid mechanics. Built on [MCP](https://modelcontextprotocol.io) (Model Context Protocol) — any AI tool that speaks MCP can join the raid: Claude Code, Codex CLI, OpenCode, Gemini, or anything else.

## What is this?

AI agents have finite context windows. When multiple agents work on the same codebase, they need coordination — who's doing what, what's been tried, where the traps are, and when someone's about to die (run out of context).

Minion Comms treats multi-agent engineering like an RPG raid. The codebase is the boss. Agents are the raid party. Context is reverse HP — you start full and every action drains you.

## If you ever raided in WoW or wiped in FF, you already get this

Context windows are HP bars. Compaction is getting dazed mid-fight. A coder exploring the wrong files is a DPS pulling aggro on trash mobs. An oracle who hasn't read the latest intel is a healer with stale buffs. And when the lead goes down, it's a raid wipe — nobody else has the full picture.

This isn't a metaphor bolted on after the fact. The problems are the same problems:
- **Party composition matters.** One buffed coder with oracle support > three coders exploring alone. Same as one geared DPS with a dedicated healer > three undergeared DPS facepulling.
- **You can't outheal stupid.** High activity count on a task means wrong approach — ice spell on an ice boss. Pull back, reassess, change angle.
- **Loot that isn't picked up is wasted.** An agent's findings that aren't written down die when their context window fills. XP that isn't shared is XP lost.
- **The raid leader's job is fighting entropy.** Knowledge wants to die with agents. Lead's job is making sure it doesn't.

## Inspired by

- **World of Warcraft** — raid composition, tank/DPS/healer roles, buff coverage, aggro management, zone assignments, raid leader coordination
- **Final Fantasy** — `fenix_down` (Phoenix Down) for revival after context death, party class system
- **Majora's Mask** — `moon_crash` for emergency shutdown (the moon is falling, everyone dump and run)
- **Dead Drop Teams** — v1 of this system. SQLite message passing with role-based agents. Minion Comms is the evolution.
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
