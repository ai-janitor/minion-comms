# Opus Lead — Session Notes (fenix_down)

## What was done this session
- Designed the full Minion Comms framework from scratch with the user
- Created `~/projects/minion-comms/` repo with README.md, PLAN.md, docs/FRAMEWORK.md
- Framework evolved from dead-drop-teams v1 through extensive design discussion

## Key decisions made
- 5 classes: lead, coder, builder, oracle, recon (class = capability, role = runtime assignment)
- Role hierarchy: general → commander → zone-lead → party
- Two databases: SQLite for state, filesystem for knowledge (Vercel pattern)
- Enforcement philosophy: enforce DB state, remind on battle-time behavior
- Context freshness enforced on `send` with class-based thresholds
- Activity count auto-increments on update_task (replaces log_turn/task_turns from v1)
- Trigger words: fenix_down, moon_crash, sitrep, rally, retreat, hot_zone, stand_down, recon
- Intel and traps are filesystem convention dirs, not DB tables
- Oracle must read new intel and traps (enforced like inbox discipline)
- Never delete battle history — archive, don't purge
- Dual transport: MCP + local HTTP API
- Model restrictions: commander needs sonnet/opus/gemini-pro, builder/recon/general can be haiku

## What's NOT done
- No code written yet — design only
- v1 server.py in dead-drop-teams has partial changes from this session (cold_start briefing, class refs in ROLE_BRIEFING) but is NOT the v2 codebase
- Phase 0 scaffolding is the starting point

## Reference files
- `~/projects/minion-comms/PLAN.md` — gated implementation plan
- `~/projects/minion-comms/docs/FRAMEWORK.md` — full design spec
- `~/projects/dead-drop-teams/src/dead_drop/server.py` — v1 reference implementation
