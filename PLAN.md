# Minion Comms — Implementation Plan

Built from `docs/FRAMEWORK.md`. Dead-drop-teams v1 is reference implementation.

## Architecture

- **Dual transport** — same server logic, two ways in:
  - **MCP** (stdio) via FastMCP — for AI agents (Claude Code, Codex, OpenCode, Gemini, etc.)
  - **HTTP** (localhost) — REST API for scripts, CI/CD, monitoring, dashboards, non-MCP tools
- One shared SQLite DB, multiple agents connecting via either transport
- Python package: `minion-comms`
- Runtime: `~/.minion-comms/` (DB, class profiles, protocol doc)

## Dependency Graph

```
Phase 0 (scaffolding)
└── Phase 1 (core comms)
    ├── Phase 2 (war room)
    │   └── Phase 3 (task system) ← needs battle plan enforcement
    │       ├── Phase 5 (monitoring) ← needs tasks + claims data
    │       └── Phase 6 (lifecycle) ← needs battle plan + tasks + raid log
    ├── Phase 4 (file safety)
    │   └── Phase 5 (monitoring) ← needs file claims for mtime checks
    └── Phase 7 (trigger words) ← needs send
Phase 8 (docs) ← can start after Phase 1, finalize after all phases
```

## Phase 0 — Scaffolding

> No dependencies. Start here.

- [ ] `pyproject.toml` — package config, FastMCP dependency, entry point
- [ ] `src/minion_comms/__init__.py`
- [ ] `src/minion_comms/server.py` — FastMCP server setup, DB init
- [ ] `src/minion_comms/api.py` — HTTP server (Flask/FastAPI), same DB, same logic
- [ ] `scripts/install.sh` — deploy runtime files to `~/.minion-comms/`
- [ ] MCP config snippet for claude_desktop_config.json / .mcp.json
- [ ] API config: default port, localhost only

## Phase 1 — Core Comms

> Blocked by: Phase 0

- [ ] All tools exposed as `@mcp.tool()` via FastMCP
- [ ] SQLite schema: agents (with `agent_class`, `model` fields), messages, broadcast_reads
- [ ] `register` — with class validation, model whitelist enforcement, onboarding
- [ ] `send` — inbox discipline (block on unread), context freshness (block on stale, class-based thresholds), auto-CC lead, poll.sh reminder
- [ ] `check_inbox` — mark read, nag on stale context
- [ ] `get_history` — post-compaction catch-up
- [ ] `who` — all agents with HP, class, staleness flags
- [ ] `set_status`, `set_context` — HP tracking
- [ ] `rename` — zone assignment
- [ ] `deregister` — cleanup file claims, leave loot on disk
- [ ] `purge_inbox` — clear stale messages

## Phase 2 — War Room

> Blocked by: Phase 1

- [ ] `battle_plan` table with explicit statuses (active/superseded/completed/abandoned/obsolete)
- [ ] `set_battle_plan` — lead only, enforced before send
- [ ] `get_battle_plan`
- [ ] `raid_log` table with priority field (low/normal/high/critical)
- [ ] `log_raid` — any agent, with priority
- [ ] `get_raid_log` — filter by priority, count

## Phase 3 — Task System

> Blocked by: Phase 2 (battle plan enforcement on task creation)

- [ ] `tasks` table: id, title, task_file, project, zone, status (full enum), blocked_by, assigned_to, created_by, files, progress, activity_count, result_file, timestamps
- [ ] Task statuses: open, assigned, in_progress, fixed, verified, closed, abandoned, stale, obsolete
- [ ] `create_task` — lead only, task_file must exist, validate blocked_by
- [ ] `assign_task` — lead only
- [ ] `update_task` — auto-increment activity_count, warn at 4+, block status='closed'
- [ ] `get_tasks` — defaults to open/assigned/in_progress, filters for history
- [ ] `get_task` — full detail
- [ ] `submit_result` — file must exist
- [ ] `close_task` — lead only, block without result file

## Phase 4 — File Safety

> Blocked by: Phase 1

- [ ] `file_claims` table, `file_waitlist` table
- [ ] `claim_file` — normalize path, block if held, auto-waitlist
- [ ] `release_file` — auto-notify waitlist, lead can force-release
- [ ] `get_claims` — filter by agent

## Phase 5 — Monitoring & Health

> Blocked by: Phase 3, Phase 4 (needs tasks for activity counts, claims for mtime checks)

- [ ] `party_status` — full raid health in one call (HP, last seen, activity count, claimed files mtime, staleness flags)
- [ ] `check_activity` — per agent: claimed file mtime, zone mtime, last seen, last task update
- [ ] `check_freshness` — files modified since agent's last set_context
- [ ] Context freshness enforcement on `send` — class-based staleness thresholds
- [ ] Nag on stale context in `update_task`, `check_inbox` responses
- [ ] Surface metrics in all tool responses

## Phase 6 — Lifecycle

> Blocked by: Phase 2, Phase 3 (cold_start needs battle plan, tasks, raid log)

- [ ] `cold_start` — agent_name required, class-based briefing, returns battle plan + raid log + open tasks + agents + loot + convention file locations
- [ ] `fenix_down` — agent lists files written, comms records manifest, staleness protection (consumed flag)
- [ ] `debrief` — lead only, file must exist
- [ ] `end_session` — lead only, block without debrief, block with open tasks

## Phase 7 — Trigger Words

> Blocked by: Phase 1 (needs send)

- [ ] Comms recognizes trigger words in `send`: fenix_down, stand_down, sitrep, rally, retreat, moon_crash, hot_zone, recon
- [ ] `moon_crash` auto-blocks new task assignments
- [ ] Trigger words included in onboarding protocol

## Phase 8 — Docs & Onboarding

> Blocked by: all phases (docs reflect final state). Can draft early, finalize last.

- [ ] Class profiles: `docs/classes/lead.md`, `coder.md`, `builder.md`, `oracle.md`, `recon.md`
- [ ] Protocol doc: `docs/PROTOCOL.md`
- [ ] `scripts/install.sh` — deploy to `~/.minion-comms/`
- [ ] Onboarding on register: protocol + class profile + trigger words

## Filesystem Convention (not code — just structure)

```
<project>/.dead-drop/
├── CODE_MAP.md
├── CODE_OWNERS.md
├── traps/
│   ├── <trap-name>.md
│   └── resolved/
├── intel/
│   ├── <topic>.md
│   └── archived/
├── tasks/
│   └── <TASK-ID>/
│       └── task.md
└── <agent-name>/
```

## Reference

- Design spec: `docs/FRAMEWORK.md`
- v1 implementation: `~/projects/dead-drop-teams/src/dead_drop/server.py`
