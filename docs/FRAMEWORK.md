# Minion Comms — Multi-Agent Engineering Inspired by RPG Raids

## Core Metaphor

The codebase is the boss. Agents are the raid party. Context is reverse HP.

## HP System (Context)

- Context window = HP bar, but backwards
- Empty context = full HP (fresh agent, ready to fight)
- Every file read, message processed, tool result = HP damage
- Context full = dead (compaction or forced retirement)
- HP is tracked via `set_context` with `tokens_used`/`tokens_limit`
- Lead monitors all HP bars via `who()`

### HP Thresholds

| Remaining | Status | Action |
|---|---|---|
| >50% | Healthy | Assign freely |
| 25-50% | Wounded | Light tasks only |
| <25% | Critical | Retire, spawn fresh |

## XP System (Task Completion)

- XP = battle-tested context from completed tasks
- An agent that fixed 3 bugs in a module knows its quirks — that's XP
- XP and HP are the same resource spent differently — high XP = low HP
- Lead's dilemma: most experienced agent is also most wounded
- XP that isn't written down dies with the agent
- XP written to `.dead-drop/` is persistent loot the whole party benefits from

## Status Effects

### Dazed (Compaction)

- Compaction doesn't kill — it dazes
- Agent wakes up mid-session, missing recent memory
- Disoriented: re-reads files, asks answered questions, forgets decisions
- Recovery protocol: `cold_start()` → read your own loot → continue
- A dazed agent is a liability — phoenix down before compaction hits

### Phoenix Down

Lead sees an agent burning out (high activity count, low HP, monitoring loop shows fatigue). Lead sends: "you're burned out — phoenix down."

`phoenix_down(agent_name)` — agent uploads all session knowledge to disk before context dies:
- Confirmed findings → `.dead-drop/intel/`
- Zone notes → `.dead-drop/<agent-name>/`
- Task progress → `update_task` with current state
- Open questions, hypotheses → `.dead-drop/<agent-name>/notes.md`

**Comms enforces:** agent can't be retired or deregistered without calling phoenix_down first. Your knowledge has to be on disk before you're allowed to forget it.

**The tool:** `fenix_down(agent_name, files=[...])` — agent lists all files they've written. Comms records the manifest with timestamp.

**After fenix down:** agent calls `cold_start()`, reads back their own files from the manifest, continues with clean context. Same agent, shed the junk, kept the intel.

**Staleness protection:** fenix_down records are tagged as consumed once the agent reads them back. Next session, a fresh agent won't accidentally replay stale manifests from a dead session. Stale knowledge is worse than no knowledge.

### Buffed (Oracle Support)

- Oracle answers questions so other agents don't burn HP exploring
- Unbuffed coder: reads 15 files to find the right one = 80k HP wasted
- Buffed coder: asks oracle, gets file:line = 2k HP, rest goes to actual work
- Buff multiplier: oracle spends 5k HP, saves coder 78k = 15x
- Buff compounds: one oracle answer serves multiple agents

## Classes and Roles

**Class** = what you *can do* — your capabilities. Permanent.
**Role** = what you're *assigned to do* — your position in this raid. Runtime.

An oracle assigned to the audio zone becomes `oracle-audio` (role). Their class is still `oracle`. Lead assigns roles via `rename` tool.

### The 5 Classes

| Class | Archetype | Capability | Lifecycle |
|---|---|---|---|
| `lead` | Commander | Coordinates, routes tasks, manages HP bars | Persistent |
| `coder` | DPS | Edits code — the only class that changes source | Ephemeral |
| `builder` | Tank | Runs commands — build, test, deploy. No edits. | Ephemeral |
| `oracle` | Sage/Buffer | Holds zone knowledge, answers questions. No edits, no commands. | Persistent |
| `recon` | Scout | Investigates specific problems, reports back. No edits. | Ephemeral |

### Party Rows

**Front line** — directly touching code
- `coder` (DPS) — deals damage to the boss, edits code
- `builder` (tank) — absorbs build errors, test failures

**Mid line** — supporting front line
- `oracle` (sage/buffer) — holds zone knowledge, prevents HP waste
- `recon` (scout) — investigates specific problems before DPS goes in

**Back line** — never touches code
- `lead` (commander) — watches the field, calls targets, manages HP bars
- sub-lead (lieutenant) — manages a squad, protects commander's HP

### Oracle vs Recon

Neither edits code. The difference is *where* they look:

- **Oracle** — knows the codebase. Persistent, pre-loads a zone, answers questions on demand. Passive. Cheap per query. Looks inward.
- **Recon** — knows the world. Ephemeral, sent to gather external intel — web searches, other repos, host system info, upstream dependencies, what's changed in the ecosystem. Looks outward.

Oracle is the library. Recon is the spy.

### Oracle Intelligence

Any agent can read files. Oracle's value is **reasoning** — they reflect on what they've read, connect patterns, understand *why* things are the way they are. Reading is context. Understanding is intelligence.

Oracle writes reasoned knowledge to their zone notes (`.dead-drop/<oracle-name>/`). Not file lists — insights:
- Hidden coupling between modules
- Why a pattern exists (not just that it does)
- What breaks when you change X
- Cross-file relationships that aren't obvious from reading one file

This is what makes oracle irreplaceable and what the replacement inherits. Comms tracks oracle's zone note files so lead and replacements can find them.

### Oracle Must Read Intel

When recon drops new findings to `.dead-drop/intel/`, comms notifies the relevant oracle. **Oracle is required to read new intel** — it's not optional. Unabsorbed intel means the oracle is answering questions with stale knowledge.

Flow: recon discovers → comms notifies oracle → oracle reads and reasons → oracle updates zone notes → coder asks oracle → oracle answers with fresh intel baked in.

Comms can enforce this the same way it enforces inbox discipline — oracle can't operate with unread intel or traps in their zone.

Oracle's required reading:
- **Intel** — new recon findings in `.dead-drop/intel/`
- **Traps** — new hazards in `.dead-drop/traps/`

Both are oracle's inbox. Stale oracle = dangerous oracle.

### File Freshness

Anyone's files can change underneath them — coder's task files, builder's build config, oracle's zone. Comms tracks what agents have loaded (via `set_context` timestamp) and can check mtime of relevant files.

`check_freshness(agent_name)` — returns files relevant to the agent (claimed files, zone files, task files) that were modified since their last `set_context`. Any agent can call this, or comms surfaces it on tool responses: "⚠️ 3 files changed since you last loaded them."

### Class Properties

| Class | Lifecycle | HP Strategy |
|---|---|---|
| `lead` | Persistent | Conserve — every message costs HP, offload to sub-leads early |
| `oracle` | Persistent | Spend deliberately — buy knowledge in assigned zone, retire when full |
| `coder` | Ephemeral | One life — spend only on task files, don't explore |
| `builder` | Ephemeral | One life — run commands, don't read source |
| `recon` | Ephemeral | One life — investigate the target, write the report, get out |

## Formations (Party Composition)

### Skirmish (small codebase, <50k lines)
```
1 lead, 1 coder, 1 builder
```
No oracle needed — coder can hold the whole thing.

### Dungeon (medium, 50k-200k)
```
1 lead, 1 oracle, 1 recon, 1 coder, 1 builder
```
One oracle covers everything. Recon for investigations.

### Raid (large, 200k-500k)
```
1 lead, 2-3 oracles (zoned), 1 recon, 2 coders, 1 builder
```
Oracles partition the codebase. Multiple coders for parallel tasks.

### World Boss (monorepo, 500k+)
```
1 raid lead, 2-3 zone leads, 4-6 oracles (zoned), 2 recons, 3 coders, 2 builders
```
Zone leads own their section. Raid lead coordinates cross-zone.

### Multi-Boss (multiple large projects)
```
1 general, N raid leads (1 per project), zone leads + parties per project
```
General allocates agents across projects. Raid leads run their own fights.

### Lead Sharing (small bosses)

One lead can manage 2-3 small projects. But context switching between projects is an HP tax. When lead's HP starts draining from multi-project switching, promote a sub-lead for one of them.

## Zone System

- Zones are assigned at runtime, not baked into classes
- Lead assigns zones after scanning the codebase
- Agent renames to reflect zone: `oracle` → `oracle-audio`
- Zone map lives in `CODE_OWNERS.md`
- Uncovered zones = unbuffed coders = HP drain = early deaths
- Cross-zone questions: lead routes to both oracles, synthesizes answer

## Buff Coverage

- Lead's real job: maximize buff coverage, minimize uncovered zones
- Every zone coders might touch should have an oracle behind it
- One well-buffed coder with 3 oracles > three coders exploring alone
- Scaling oracles matters more than scaling coders

## War Room (DB-Enforced)

### Battle Plan
- Lead must set a battle plan before sending any task assignments (server enforced)
- Describes session goals, priorities, zone assignments, order of attack
- Any agent can read it via `get_battle_plan`
- Updated when priorities shift

### Raid Log
- Append-only decision log stored in DB
- Any agent can write entries via `log_raid` with a priority level
- Survives compaction — this is the team's persistent memory
- Recovery after daze: `get_raid_log(priority="high")` to reconstruct what matters

| Priority | Meaning |
|---|---|
| `low` | Status updates, routine activity |
| `normal` | Decisions, findings |
| `high` | Blockers, critical discoveries, session-level decisions |
| `critical` | Something broke, immediate attention needed |

`get_raid_log` filters by priority — fresh lead on cold_start reads high/critical only, doesn't burn HP on noise.

Raid log is **working memory** — useful during the session. Important findings should already be written to intel/ or traps/ as confirmed knowledge. Low priority entries get purged after the session. The filesystem is long-term memory, not the log.

## Loot System (Knowledge Persistence)

- When agents retire, they write findings to `.dead-drop/<name>/`
- This is loot dropped on death — replacement picks it up
- A replacement starts at level 1 HP but inherits veteran's knowledge
- Oracles should write zone notes as they go — don't wait for retirement
- Lead's raid log is the most important loot in the system

### Intel (Confirmed Findings)

- Intel is **confirmed information only** — not theories, not hunches. Verified facts.
- Unconfirmed findings stay in the agent's result file as hypotheses. Only promoted to intel/ when verified.
- Any agent can write confirmed findings to `.dead-drop/intel/<topic>.md`
- Examples: `upstream-deps.md`, `ci-changes.md`, `api-breaking-changes.md`
- Comms surfaces `.dead-drop/intel/` in cold_start briefing for all classes
- Oracle is required to absorb new intel in their zone
- Same rule for traps — you don't log a trap on a hunch. You hit it, confirmed it, then wrote it down.

### Convention File Locations

Comms points agents to these on cold_start. The files are the inventory.

| File | Purpose | Who writes | Who reads |
|---|---|---|---|
| `.dead-drop/CODE_MAP.md` | Codebase structure (tree-sitter) | Lead (pre-flight) | Oracle, recon, coder |
| `.dead-drop/CODE_OWNERS.md` | Zone assignments | Lead | Oracle, recon |
| `.dead-drop/traps/` | Known hazards (one file per trap) | Anyone who finds one | Everyone before touching a zone |
| `.dead-drop/intel/` | External findings | Recon | Oracle, lead |
| `.dead-drop/<agent>/` | Agent loot on retirement | The retiring agent | Their replacement |

## Role Hierarchy

Class defines capabilities. Roles define position. The `lead` class has a role hierarchy that scales with the fight.

### Lead Roles

| Role | Scope | When needed |
|---|---|---|
| **General** | All projects | 2+ large projects running simultaneously |
| **Commander** | One project, cross-zone | Any project with 2+ zones |
| **Zone lead** | One zone in one project | Zones big enough to need their own party |

All three are `lead` class — same capabilities, different scope.

**General is the user's puppet.** Not the smartest model — doesn't need to be. Translates user intent into battle plans, allocates commanders to projects, relays orders. Could be haiku. The commanders are the ones who need brains.

### Model Restrictions

Comms enforces model-to-role restrictions on registration. Agents declare their model on `register` — server checks against a whitelist.

| Role | Allowed models |
|---|---|
| General | Any |
| Commander | Opus, Sonnet, Gemini Pro |
| Zone lead | Opus, Sonnet, Gemini Pro |
| Oracle | Any |
| Recon | Any |
| Coder | Sonnet+ (needs code judgment) |
| Builder | Any (haiku fine — runs commands) |

Self-reported model can't be verified, but it's on record. If an agent lies about their model, the quality shows up in turn counts and result files — lead sees it in the data.

### Transport Types

Agents declare their transport on `register`:

| Transport | How messages reach the agent | Who manages it |
|---|---|---|
| `terminal` | Agent runs `poll.sh` in background, polls own inbox | Agent (human in CLI) |
| `daemon` | Swarm daemon watches DB, injects messages on wake | minion-swarm |

Both are peers on the comms network — same `send()`, same enforcement. The only difference is message delivery plumbing.

**Hybrid model:** A raid typically has both. Human opens terminal sessions for high-value agents (lead, oracle, complex coder). Cheap grunt work (recon, builds, simple tasks) goes to swarm daemons. All talk through the same minion-comms DB.

```
┌─ TERMINAL (interactive, human sees everything) ─────┐
│ Terminal 1: lead (general/commander)                 │
│ Terminal 2: oracle-auth                              │
│ Terminal 3: coder-api                                │
└──────────────────────────────────────────────────────┘
              ↕ minion-comms (shared coordination DB)
┌─ DAEMON (headless, fire-and-forget) ────────────────┐
│ Swarm: recon-deps (haiku)                            │
│ Swarm: builder-ci (haiku)                            │
│ Swarm: coder-tests (sonnet)                          │
└──────────────────────────────────────────────────────┘
```

Comms behavior by transport:
- **`poll.sh` reminders** — only for `terminal` agents. Daemons don't need them.
- **`who()` output** — shows transport type so lead knows which agents are interactive vs headless.
- **Nag behavior** — terminal agents get reminded to poll. Daemon agents don't.

```
user (the human)
└── general (puppet — translates user intent into battle plans)
    └── commander (runs the actual fight, needs the brains)
        └── zone-lead (owns a section)
            └── party (oracle, coder, builder, recon)
```

### Hierarchy

```
general                            (multi-project, allocates parties to bosses)
├── commander (tts-cpp)
│   ├── zone-lead-audio
│   │   ├── oracle-audio
│   │   ├── coder
│   │   └── builder
│   ├── zone-lead-model
│   │   ├── oracle-model
│   │   └── coder
│   └── zone-lead-infra
│       ├── oracle-infra
│       └── builder
├── commander (frontend)
│   └── ...
└── commander (dead-drop)          (small boss, no zone leads needed)
    └── small party
```

### Each tier has its own battle plan

- **General's plan:** which projects to prioritize, how to allocate agents across them
- **Commander's plan:** zone assignments and task priorities within one project
- **Zone lead's plan:** specific attack on their zone

### HP flows upward

- Zone lead reports to commander, commander reports to general
- General has the least direct context but the widest view
- Lead dazed at any tier = that tier loses coordination
- Higher the tier, bigger the impact of a daze

## Lead is Not Exception

- Lead has highest XP (sees everything via auto-CC) and lowest HP
- Lead dazed = raid wipe — nobody else has the full picture
- Lead must maintain raid log continuously, not at the end
- Lead must offload coordination to zone leads before HP gets critical
- Fresh lead reads: battle plan + raid log + party status → picks up the raid

## Lead Monitoring Loop

Lead doesn't just assign tasks and wait. Lead actively monitors the raid every 2-5 minutes:

1. **Poll inbox** — check for agent reports
2. **Check activity** — `check_activity(agent_name)` returns:
   - Claimed files with their mtime (is the agent actually editing?)
   - Last task update timestamp
   - Last seen timestamp
3. **Make decisions** — if an agent hasn't modified any claimed files in 5-10 minutes and hasn't reported in, they're probably dead or stuck. Lead can: nudge them, reassign the task, force-release their file claims.

Comms checks activity at multiple levels:
- **Has file claims?** → check mtime on claimed files
- **No claims but has a zone?** → check mtime on zone directory for any recent changes
- **Neither?** → fall back to last_seen and last task update

This detects activity from any class — coder editing files, builder generating output, oracle writing zone notes. Filesystem data comms can access — not enforcement, just reporting.

### Surface Metrics Everywhere

Any field relevant to a decision should be surfaced in tool responses. Agents shouldn't have to ask for data — it comes to them.

- `update_task` response includes: activity count (with warning at 4+), agent HP if stale
- `check_inbox` response includes: reminder to update context metrics if stale
- `who()` response includes: HP, last seen, activity count, staleness warnings
- Every tool response nags agents with stale context: "your context metrics haven't been updated in X minutes — call `set_context`"

**Comms enforces context freshness on `send`.** If your last `set_context` is older than the threshold for your class, `send` is **BLOCKED** — "update your context metrics before communicating." Same as unread inbox blocking send. You can't talk to the team if your health bar is out of date. This is DB state we control — enforceable, not just a reminder.

Staleness thresholds are class-based — active classes churn context fast, passive classes don't:

| Class | Staleness threshold | Why |
|---|---|---|
| Coder | 5 min | Actively editing, context changes fast |
| Builder | 5 min | Running commands, output burns HP |
| Recon | 5 min | Actively searching |
| Lead | 15 min | Coordinating, moderate churn |
| Oracle | 30 min | Idle between queries, context stable |

Other tools (`update_task`, `check_inbox`) nag but don't block.

### Party Health View

Lead needs one tool that shows the whole raid's health — not per-agent calls:

`party_status()` — returns for every agent:
- Name, class, role, HP (tokens used/limit), last seen
- Total activity count across all tasks
- Claimed files with mtime
- Staleness flag (no context update in 5+ minutes)

One call, full picture. Lead polls this every 2-5 minutes.

### Dead Agent Cleanup

1. Lead sees stale agent via `party_status()`
2. Lead sends `sitrep` — "respond now"
3. Comms starts a 30-minute heartbeat timer on that agent
4. If agent doesn't respond (no `check_inbox` or `send`) within 30 minutes — auto-deregister
5. File claims auto-released, waitlisted agents notified
6. Agent's files stay on disk (`.dead-drop/<agent>/`) — loot left for assessment

Deregister kills the agent, not their knowledge. Two options:

- **Reassign** — lead gives the dead agent's task to a fresh agent. Fresh agent reads `.dead-drop/<dead-agent>/` to pick up where they left off. Clean handoff if the dead agent fenix_down'd before dying. Partial handoff if they didn't — loot is whatever they wrote along the way.
- **Assess** — lead assigns a recon to review the dead agent's files and report what's salvageable before deciding next steps.
- **Finish locally** — lead spawns a local subagent (sonnet coder, haiku builder) via Task tool to close it out. Point them at the dead agent's loot, they finish up and submit the result. **Costs lead HP** — subagent context comes out of lead's window. If lead is already wounded, better to ask the human to spawn a fresh external agent instead.

## Status Enums

Explicit statuses — no ambiguous "inactive" flags.

### Battle Plan Statuses

| Status | Meaning |
|---|---|
| `active` | Current session plan, this is what we're doing |
| `superseded` | Replaced by a newer plan this session |
| `completed` | Session ended, goals achieved |
| `abandoned` | Session ended, goals not achieved |
| `obsolete` | Requirements changed, plan no longer relevant |

### Task Statuses

| Status | Meaning |
|---|---|
| `open` | Created, not assigned |
| `assigned` | Given to an agent, not started |
| `in_progress` | Agent actively working |
| `fixed` | Agent thinks it's done |
| `verified` | Tested/reviewed by another agent |
| `closed` | Done, result file submitted |
| `abandoned` | Won't do, documented why |
| `stale` | From a previous session, needs review |
| `obsolete` | No longer relevant, requirements changed |

On new session start, lead reviews old tasks and explicitly marks them — stale, obsolete, or still open. No ambiguity.

## Activity System (Tasks)

- Every `update_task` call increments `activity_count` automatically. No manual logging.
- Activity count is diagnostic — how many times an agent touched the task:

| Activity | Meaning |
|---|---|
| 1-2 | Clean hit — right agent, right approach |
| 3-5 | Resistance — something's off, maybe wrong angle |
| 6+ | Ice on ice — stop, reassess, change approach |

- High activity signals: wrong agent, wrong approach, hidden immunity (unseen dependency), or boss phase change (code changed underneath)
- Lead watches activity counts. At 4+, pull back and reassess before burning more HP.
- **Server warns in `update_task` response** when activity count hits 4+ — "activity count at 6, consider reassessing." The alert is built into the tool response, not a separate check.

## Battle Journey (Result Files)

- Agent can't walk away from a fight without writing what they learned
- `submit_result` links a writeup file to the task — server verifies file exists
- `close_task` blocks if no result file submitted (DB-enforced)
- `update_task(status='closed')` blocked — must go through `close_task`

### What the writeup must include
- What you tried (each approach)
- What worked and what didn't
- What the next agent should know
- File:line citations for everything

### Why
- XP that isn't written down dies with the agent
- Result files are persistent loot — any future agent can read them
- Lead reads them to assess what happened and plan next moves

### Housekeeping — Whoever Finds It, Owns It

No dedicated chores. If you encounter stale intel or a resolved trap while working:
1. Take ownership
2. Write up why it's stale or how it was resolved
3. Move to `archived/` (intel) or `resolved/` (traps)

Don't wait for someone else. Don't file a ticket. Just do it.

### Never Delete Battle History
- Failures, bad rabbitholes, dead ends — all documented, never deleted
- A documented failure saves the next agent from repeating it
- Success and danger are both valuable — archive, don't purge
- Move to `resolved/` or `archived/`, never `rm`

## Project Scope

- Tasks track which `project` they belong to — one DB serves multiple raids
- `get_tasks(project="tts-cpp", zone="audio")` → full battle history for that area
- Battle plans should be scoped to project (and zone for zone leads)

## Scaling Rule

- More allies = more coordination overhead = more lead HP burn
- At some point lead needs zone leads just to protect their own HP
- Zone leads are XP banks for their squad — they remember what their coders learned
- The whole system is lead fighting entropy — knowledge wants to die with agents, lead's job is to make sure it doesn't
- Context switching between projects is an HP tax — don't spread lead thin across too many bosses

## Trigger Words (Brevity Codes)

Short code words that all agents learn on registration. Lead sends a trigger word instead of a paragraph — saves HP on both sides. Like military brevity codes.

| Code word | Target | Meaning |
|---|---|---|
| `fenix_down` | agent name | Dump knowledge to files, refresh context |
| `stand_down` | agent name | Stop work, deregister |
| `sitrep` | agent name | Update context metrics and send status now |
| `rally` | all | Everyone check inbox immediately |
| `retreat` | all | Orderly — finish current turn, then fenix_down |
| `moon_crash` | all | Emergency — everyone fenix_down NOW, session ending (Majora's Mask) |
| `hot_zone` | zone name | Priority shift — all available agents focus here |
| `recon` | agent + target | Go investigate this, report back |

Agents learn the codebook via protocol on registration. Comms recognizes trigger words in `send` — can attach automation (e.g. `moon_crash` auto-blocks all new task assignments).

## Two Databases

The system runs on two databases with different jobs:

**Filesystem DB (`.dead-drop/`)** — content lives here. Convention over configuration. Directory structure is the schema, file naming is the API. Agents navigate with `ls`, `cat`, `grep`. Inspired by Vercel's filesystem-as-framework pattern.

```
.dead-drop/
├── CODE_MAP.md          # structure index (tree-sitter output)
├── CODE_OWNERS.md       # zone assignments
├── traps/               # known hazards (one file per trap)
├── intel/               # recon findings (external intel)
├── tasks/               # task spec files
│   └── BUG-001/
│       └── task.md
└── <agent-name>/        # agent loot (retirement notes, logs)
```

**SQLite DB (`messages.db`)** — coordination state lives here. Who's registered, messages, task metadata, file claims, battle plans, raid log. Comms owns this. It points to files in the filesystem DB but doesn't store content.

**The split:** SQLite tracks *state* (who, what status, which claims). Filesystem stores *knowledge* (specs, findings, notes). Comms surfaces file locations, agents read the files.

## What Dead-Drop Is (and Isn't)

Dead-drop is the **comms network**, not the arsenal. It handles:

- **Comms** — send, check_inbox, get_history, purge_inbox
- **Task queries** — `get_tasks` defaults to open/assigned/in_progress only. Use filters for history: `get_tasks(status="closed")`, `get_tasks(status="stale")`, `get_tasks(project="tts-cpp", zone="audio")`
- **Coordination** — who, set_status, set_context, register, rename, deregister
- **Strategy** — set_battle_plan, get_battle_plan, log_raid, get_raid_log, cold_start, debrief
- **Task tracking** — create_task, assign_task, update_task, get_tasks, get_task, log_turn, submit_result, close_task, end_session
- **File safety** — claim_file, release_file, get_claims

The actual fighting (Read, Edit, Bash, WebSearch) happens through the host's tools. Dead-drop is the radio + war room + task board. Weapons are someone else's problem.

### Enforcement Philosophy

Dead-drop can only enforce what it owns — comms data in the DB. It does NOT pretend to enforce battle-time behavior.

**Server enforces (BLOCKED):** things that are DB state we control
- Inbox discipline — can't send with unread messages
- Context freshness — can't send if `set_context` is older than class-based threshold (see Staleness Thresholds table)
- File claims — can't claim a file another agent holds
- Task dependencies — can't start a task blocked by another
- Class restrictions — only lead class can create/assign/close tasks, set battle plan, file debrief, end session
- Result files — task can't close without a submitted battle journey (file existence check)
- Debrief — session can't end without a filed debrief
- Battle plan — lead can't send tasks without an active plan

**Server reminds (not enforced):** things we can't verify
- poll.sh running — we remind terminal agents on every send (skip for daemon transport), but can't verify the process is actually poll.sh
- Agents actually reading the files they claim
- Coders following the spec
- Builders actually running the tests
- Context/HP self-reporting accuracy (we enforce freshness, not truthfulness)
- Agents actually reading their onboarding docs

**The principle:** make the right thing easy and the wrong thing visible. If an agent skips steps, the evidence shows up — no result file, high turn count, no context updates, stale HP. Lead sees it in the data.

## Open Questions — Prioritized

### Tier 1 — Happens every session, easy to build

1. **Cold start / wipe recovery:** Every new session is a cold start. `cold_start()` returns: last battle plan, last 20 raid log entries, all open tasks, all loot manifests. One call to rebuild the picture. Is this enough to resume? What about partial wipes (just lead dazed, party still alive)?

2. **Friendly fire:** Two coders editing the same file = merge conflicts = wasted HP. `claim_file` / `release_file` — agent declares what they're editing, server blocks others. How granular? Per file? Per function? Per zone? What happens when an agent dies holding a claim?

3. ~~**Traps:**~~ **Resolved.** Traps are convention files in `.dead-drop/traps/` (one file per trap, Vercel pattern), not DB state. Agents write hazards they discover, other agents read before touching a zone. Comms points to the folder via `cold_start` briefing — no new tools needed. **When a trap is snared (fixed):** update the file with how it was solved, move to `.dead-drop/traps/resolved/`. Active folder only holds live traps. Resolved folder is reference — future agents can see what traps existed and how they were fixed.

4. ~~**Turn count alerts:**~~ **Resolved.** Turn count auto-increments on every `update_task`. Server returns a warning in the response when count hits 4+ — "this fight is dragging, consider reassessing." Built into `update_task`, no separate tool needed.

### Tier 2 — Important but less frequent

5. ~~**Fatigue:**~~ **Resolved.** Lead monitoring loop + `party_status()` + `check_activity()` detects fatigue. Class-based staleness thresholds enforce context freshness. Lead sees the full picture and acts.

6. **Aggro table / heat map:** `get_heat_map(project)` — aggregates activity counts by zone, shows where the boss is hitting hardest. Pure query on existing data, no new tables. Helps lead allocate oracles and coders to hot zones.

7. ~~**Respawn / loot manifest:**~~ **Resolved.** `fenix_down` handles knowledge dump before death. Replacement reads `.dead-drop/<dead-agent>/` to inherit. Dead agent cleanup protocol covers reassign, assess, and finish locally options.

8. ~~**Oracle death handoff:**~~ **Resolved.** Oracle writes zone notes as they go. `fenix_down` captures final state. Replacement reads zone notes + intel + traps on cold_start.

### Tier 3 — Scaling problems (solve when you hit them)

9. **Battle plan scoping:** Add project/zone fields to battle_plan so zone leads set their own plans. Need this when hierarchy gets deep.

10. **Lead role field:** Add `role: general | commander | zone-lead` to agents table for lead-class agents. Need this when you run multiple lead tiers.

11. **Zone enforcement on leads:** Server enforces zone lead can only create/assign tasks in their zone. Need this when discipline isn't enough.

12. **Zone lead formalization:** Formal role profile or just a lead with a zone assignment? Probably just naming convention until a real pattern emerges.

13. **Multi-project battle plan:** General's plan vs. commander's plan — how do they compose? Need this when general role exists.

### Tier 4 — Hard or low priority

14. **HP auto-tracking:** Agents can't reliably self-report tokens_used. Need a proxy or hook that measures actual context size. Hard problem, unclear solution.

15. **Mana (API cost):** Add `tokens_spent` to `log_turn`. Nice metric but doesn't change behavior much. Lead can't reduce API cost mid-session.

16. **Friendly NPCs:** Register CI/CD as `ci-bot` class `npc`, sends build results via `send`. Good idea but separate integration project.

17. **Boss phases / staleness:** Codebase changes mid-fight (refactors, merges). `report_stale(agent_name, reason)` lets oracle flag outdated knowledge. How to detect staleness automatically? Maybe git hooks?

18. **Loot distribution:** Who reads result files? Oracle should absorb zone loot but it costs HP. Knowledge spread is an org design problem, not just a tool problem.

19. **Turn-based dep visualization:** `blocked_by` works, but lead needs to see the full dependency graph for multi-phase attacks. UI/reporting problem.

20. **Tool discovery:** How does a new agent learn what dead-drop can do? Onboarding handles most of it. Maybe a `help` tool that lists available tools with one-line descriptions?

21. ~~**Session persistence:**~~ **Mostly resolved.** Battle plan statuses (active/superseded/completed/abandoned/obsolete), task statuses (stale/obsolete), raid log priority + purging, fenix_down staleness protection. Lead reviews old state on new session start. Filesystem (intel, traps, loot) persists across sessions. SQLite (agents, messages) gets cleaned up per session.

22. **WoW vs FF framing:** Cosmetic. WoW maps better (real-time raid, role specialization, buff management) but the generic RPG framing works fine.
