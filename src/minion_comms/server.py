"""minion-comms MCP server — Phase 0 + Phase 1 + Phase 2 + Phase 3.

Multi-agent coordination: messages, registration, HP tracking, context freshness,
battle plans, raid log, and task system.
DB: ~/.minion-comms/messages.db (override with MINION_COMMS_DB_PATH)
"""

from mcp.server.fastmcp import FastMCP
import sqlite3
import datetime
import os
import json

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

DB_PATH = os.getenv(
    "MINION_COMMS_DB_PATH",
    os.path.expanduser("~/.minion-comms/messages.db"),
)
RUNTIME_DIR = os.path.dirname(DB_PATH)

mcp = FastMCP("Minion Comms")

# ---------------------------------------------------------------------------
# Agent classes and model whitelists
# ---------------------------------------------------------------------------

VALID_CLASSES = {"lead", "coder", "builder", "oracle", "recon"}

BATTLE_PLAN_STATUSES = {"active", "superseded", "completed", "abandoned", "obsolete"}
RAID_LOG_PRIORITIES = {"low", "normal", "high", "critical"}
TASK_STATUSES = {
    "open", "assigned", "in_progress", "fixed", "verified",
    "closed", "abandoned", "stale", "obsolete",
}

# Models allowed per class. Empty set = any model allowed.
CLASS_MODEL_WHITELIST: dict[str, set[str]] = {
    "lead":    {"claude-opus-4-6", "claude-opus-4-5", "claude-sonnet-4-6", "claude-sonnet-4-5", "gemini-pro", "gemini-1.5-pro", "gemini-2.0-pro"},
    "coder":   {"claude-opus-4-6", "claude-opus-4-5", "claude-sonnet-4-6", "claude-sonnet-4-5", "gemini-pro", "gemini-1.5-pro", "gemini-2.0-pro"},
    "oracle":  set(),   # any model
    "recon":   set(),   # any model
    "builder": set(),   # any model (haiku fine)
}

# Staleness thresholds per class (seconds). If set_context is older than this,
# send() is BLOCKED. None = no enforcement (class not in map = no enforcement).
CLASS_STALENESS_SECONDS: dict[str, int] = {
    "coder":   5 * 60,
    "builder": 5 * 60,
    "recon":   5 * 60,
    "lead":    15 * 60,
    "oracle":  30 * 60,
}

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_lead(cursor: sqlite3.Cursor) -> str | None:
    """Return the name of the first registered lead agent, or None."""
    cursor.execute("SELECT name FROM agents WHERE agent_class = 'lead' LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else None


def _load_onboarding(agent_class: str) -> str:
    """Load protocol + class profile from runtime directory."""
    parts: list[str] = []

    protocol_path = os.path.join(RUNTIME_DIR, "PROTOCOL.md")
    if os.path.exists(protocol_path):
        with open(protocol_path, "r") as f:
            parts.append(f.read())

    if agent_class:
        class_path = os.path.join(RUNTIME_DIR, "classes", f"{agent_class}.md")
        if os.path.exists(class_path):
            with open(class_path, "r") as f:
                parts.append(f.read())

    return "\n\n---\n\n".join(parts) if parts else ""


def _hp_summary(tokens_used: int | None, tokens_limit: int | None) -> str:
    """Return a human-readable HP string, e.g. '45% HP (92k/200k)'."""
    if not tokens_used or not tokens_limit:
        return "HP unknown"
    pct_used = tokens_used / tokens_limit * 100
    hp_pct = 100 - pct_used
    status = "Healthy" if hp_pct > 50 else ("Wounded" if hp_pct > 25 else "CRITICAL")
    return f"{hp_pct:.0f}% HP [{tokens_used // 1000}k/{tokens_limit // 1000}k] — {status}"


def _staleness_check(cursor: sqlite3.Cursor, agent_name: str) -> tuple[bool, str]:
    """Check if agent's context is stale per their class threshold.

    Returns (is_stale, message). is_stale=True means BLOCKED.
    """
    cursor.execute(
        "SELECT agent_class, last_seen, context_updated_at FROM agents WHERE name = ?",
        (agent_name,),
    )
    row = cursor.fetchone()
    if not row:
        return False, ""

    agent_class = row["agent_class"]
    context_updated_at = row["context_updated_at"]

    threshold = CLASS_STALENESS_SECONDS.get(agent_class)
    if threshold is None:
        return False, ""

    if not context_updated_at:
        # Never set context — stale by definition
        return (
            True,
            f"BLOCKED: Context not set. Call set_context before sending. "
            f"({agent_class} threshold: {threshold // 60} min)",
        )

    try:
        updated = datetime.datetime.fromisoformat(context_updated_at)
    except ValueError:
        return False, ""

    age_seconds = (datetime.datetime.now() - updated).total_seconds()
    if age_seconds > threshold:
        mins = int(age_seconds // 60)
        return (
            True,
            f"BLOCKED: Context stale ({mins}m old, threshold {threshold // 60}m for {agent_class}). "
            f"Call set_context to update your metrics before sending.",
        )

    return False, ""


# ---------------------------------------------------------------------------
# DB initialization
# ---------------------------------------------------------------------------

def init_db() -> None:
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # agents — v2 schema: agent_class + model instead of role
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            name                TEXT PRIMARY KEY,
            agent_class         TEXT NOT NULL DEFAULT 'coder',
            model               TEXT DEFAULT NULL,
            registered_at       TEXT,
            last_seen           TEXT,
            last_inbox_check    TEXT,
            context_updated_at  TEXT DEFAULT NULL,
            description         TEXT DEFAULT NULL,
            status              TEXT DEFAULT 'waiting for work',
            context             TEXT DEFAULT NULL,
            context_tokens_used   INTEGER DEFAULT NULL,
            context_tokens_limit  INTEGER DEFAULT NULL,
            transport             TEXT DEFAULT 'terminal'
        )
    """)

    # messages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            from_agent      TEXT,
            to_agent        TEXT,
            content         TEXT,
            timestamp       TEXT,
            read_flag       INTEGER DEFAULT 0,
            is_cc           INTEGER DEFAULT 0,
            cc_original_to  TEXT DEFAULT NULL
        )
    """)

    # broadcast read tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS broadcast_reads (
            agent_name  TEXT,
            message_id  INTEGER,
            PRIMARY KEY (agent_name, message_id)
        )
    """)

    # battle_plan — Phase 2
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS battle_plan (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            set_by      TEXT NOT NULL,
            plan        TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'active',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)

    # raid_log — Phase 2
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raid_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name  TEXT NOT NULL,
            entry       TEXT NOT NULL,
            priority    TEXT NOT NULL DEFAULT 'normal',
            created_at  TEXT NOT NULL
        )
    """)

    # tasks — Phase 3
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT NOT NULL,
            task_file       TEXT NOT NULL,
            project         TEXT DEFAULT NULL,
            zone            TEXT DEFAULT NULL,
            status          TEXT NOT NULL DEFAULT 'open',
            blocked_by      TEXT DEFAULT NULL,
            assigned_to     TEXT DEFAULT NULL,
            created_by      TEXT NOT NULL,
            files           TEXT DEFAULT NULL,
            progress        TEXT DEFAULT NULL,
            activity_count  INTEGER NOT NULL DEFAULT 0,
            result_file     TEXT DEFAULT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Phase 1 — Core Comms tools
# ---------------------------------------------------------------------------

@mcp.tool()
def register(
    agent_name: str,
    agent_class: str,
    model: str = "",
    description: str = "",
    transport: str = "terminal",
) -> str:
    """Register this agent into minion-comms.

    agent_name: unique name for this agent (e.g. 'coder-1', 'oracle-audio').
    agent_class: one of lead | coder | builder | oracle | recon.
    model: the model ID this agent is running on (e.g. 'claude-sonnet-4-6').
           Used for model restriction enforcement — honest self-reporting expected.
    description: what this agent does / what zone they own.
    transport: 'terminal' (human CLI, needs poll.sh) or 'daemon' (swarm-managed, no polling).
    """
    if transport not in ("terminal", "daemon"):
        return f"BLOCKED: Invalid transport '{transport}'. Must be 'terminal' or 'daemon'."
    if agent_class not in VALID_CLASSES:
        return (
            f"BLOCKED: Unknown class '{agent_class}'. "
            f"Valid classes: {', '.join(sorted(VALID_CLASSES))}"
        )

    # Model whitelist check
    allowed_models = CLASS_MODEL_WHITELIST.get(agent_class, set())
    if allowed_models and model and model not in allowed_models:
        return (
            f"BLOCKED: Model '{model}' is not allowed for class '{agent_class}'. "
            f"Allowed: {', '.join(sorted(allowed_models))}"
        )

    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        cursor.execute(
            """
            INSERT INTO agents
                (name, agent_class, model, registered_at, last_seen, description, status, transport)
            VALUES (?, ?, ?, ?, ?, ?, 'waiting for work', ?)
            ON CONFLICT(name) DO UPDATE SET
                last_seen   = excluded.last_seen,
                agent_class = excluded.agent_class,
                model       = COALESCE(NULLIF(excluded.model, ''), agents.model),
                description = COALESCE(NULLIF(excluded.description, ''), agents.description),
                transport   = excluded.transport,
                status      = 'waiting for work'
            """,
            (agent_name, agent_class, model or None, now, now, description or None, transport),
        )

        # Auto-mark broadcasts older than 1 hour as read (don't blast new agents with history)
        cutoff = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()
        cursor.execute(
            """
            INSERT OR IGNORE INTO broadcast_reads (agent_name, message_id)
            SELECT ?, id FROM messages WHERE to_agent = 'all' AND timestamp < ?
            """,
            (agent_name, cutoff),
        )

        conn.commit()

        result = (
            f"Agent '{agent_name}' registered. class={agent_class}"
            + (f" model={model}" if model else "")
            + (f" | {description}" if description else "")
        )

        onboarding = _load_onboarding(agent_class)
        if onboarding:
            result += f"\n\n# Onboarding\n\nRead and follow these instructions:\n\n{onboarding}"
        else:
            result += (
                "\n\nNo onboarding docs found in runtime dir. "
                f"Check {RUNTIME_DIR}/PROTOCOL.md and {RUNTIME_DIR}/classes/{agent_class}.md"
            )

        return result
    except Exception as e:
        return f"Error registering agent: {e}"
    finally:
        conn.close()


@mcp.tool()
def deregister(agent_name: str) -> str:
    """Remove an agent from the registry. Cleans up stale / dead session entries.
    Note: does NOT delete message history or loot on disk."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM agents WHERE name = ?", (agent_name,))
        if not cursor.fetchone():
            return f"Agent '{agent_name}' not found."
        cursor.execute("DELETE FROM agents WHERE name = ?", (agent_name,))
        conn.commit()
        return f"Agent '{agent_name}' deregistered. Loot stays on disk."
    except Exception as e:
        return f"Error deregistering agent: {e}"
    finally:
        conn.close()


@mcp.tool()
def rename(old_name: str, new_name: str) -> str:
    """Rename an agent — e.g. 'oracle' → 'oracle-audio' for zone assignment.
    Updates agent record and all message history."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM agents WHERE name = ?", (old_name,))
        if not cursor.fetchone():
            return f"Agent '{old_name}' not found."
        cursor.execute("SELECT name FROM agents WHERE name = ?", (new_name,))
        if cursor.fetchone():
            return f"Agent '{new_name}' already exists. Choose a different name."
        cursor.execute("UPDATE agents SET name = ? WHERE name = ?", (new_name, old_name))
        cursor.execute("UPDATE messages SET from_agent = ? WHERE from_agent = ?", (new_name, old_name))
        cursor.execute("UPDATE messages SET to_agent = ? WHERE to_agent = ?", (new_name, old_name))
        cursor.execute("UPDATE messages SET cc_original_to = ? WHERE cc_original_to = ?", (new_name, old_name))
        cursor.execute("UPDATE broadcast_reads SET agent_name = ? WHERE agent_name = ?", (new_name, old_name))
        conn.commit()
        return f"Renamed '{old_name}' → '{new_name}'. All message history updated."
    except Exception as e:
        return f"Error renaming agent: {e}"
    finally:
        conn.close()


@mcp.tool()
def set_status(agent_name: str, status: str) -> str:
    """Set your current status. Shows up in who() output.
    Examples: 'working on BUG-014', 'waiting for work', 'reviewing auth module'."""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        cursor.execute(
            "UPDATE agents SET status = ?, last_seen = ? WHERE name = ?",
            (status, now, agent_name),
        )
        conn.commit()
        return f"Status set: {agent_name} → {status}"
    except Exception as e:
        return f"Error setting status: {e}"
    finally:
        conn.close()


@mcp.tool()
def set_context(
    agent_name: str,
    context: str,
    tokens_used: int = 0,
    tokens_limit: int = 0,
) -> str:
    """Update your context summary and HP metrics. Call this after major file reads or tool use.
    Context freshness is enforced on send() — stale context = blocked comms.

    context: one-line summary of what you have loaded (e.g. 'auth module + task BUG-014')
    tokens_used / tokens_limit: whole numbers (e.g. 85000, 200000). Required for HP tracking.
    """
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        cursor.execute(
            """UPDATE agents
               SET context = ?,
                   context_tokens_used  = NULLIF(?, 0),
                   context_tokens_limit = NULLIF(?, 0),
                   context_updated_at   = ?,
                   last_seen            = ?
               WHERE name = ?""",
            (context, tokens_used, tokens_limit, now, now, agent_name),
        )
        conn.commit()

        size_note = ""
        if tokens_used and tokens_limit:
            hp = _hp_summary(tokens_used, tokens_limit)
            size_note = f" | {hp}"

        return f"Context updated: {agent_name} → {context}{size_note}"
    except Exception as e:
        return f"Error setting context: {e}"
    finally:
        conn.close()


@mcp.tool()
def who() -> str:
    """List all registered agents with class, HP, status, and staleness flags.
    Lead calls this to monitor party health."""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now()
    try:
        cursor.execute("SELECT * FROM agents ORDER BY last_seen DESC")
        agents = []
        for row in cursor.fetchall():
            a = dict(row)

            # HP summary
            a["hp"] = _hp_summary(a.get("context_tokens_used"), a.get("context_tokens_limit"))

            # Staleness flag
            threshold = CLASS_STALENESS_SECONDS.get(a.get("agent_class", ""), None)
            stale = False
            if threshold and a.get("context_updated_at"):
                try:
                    updated = datetime.datetime.fromisoformat(a["context_updated_at"])
                    stale = (now - updated).total_seconds() > threshold
                except ValueError:
                    pass
            elif threshold and not a.get("context_updated_at"):
                stale = True
            a["context_stale"] = stale

            # Last-seen age
            if a.get("last_seen"):
                try:
                    ls = datetime.datetime.fromisoformat(a["last_seen"])
                    age_min = int((now - ls).total_seconds() // 60)
                    a["last_seen_mins_ago"] = age_min
                except ValueError:
                    pass

            agents.append(a)

        if not agents:
            return "No agents registered."
        return json.dumps(agents, indent=2)
    except Exception as e:
        return f"Error listing agents: {e}"
    finally:
        conn.close()


@mcp.tool()
def send(
    from_agent: str,
    to_agent: str,
    message: str,
    cc: str = "",
) -> str:
    """Send a message to an agent (or 'all' for broadcast).

    BLOCKS if:
    - You have unread messages (check_inbox first — inbox discipline)
    - Your context is stale per your class threshold (set_context first)

    Auto-CCs the lead on every non-lead message for full visibility.
    Optional cc: comma-separated additional agent names.

    REMINDER: Ensure poll.sh is running as a background process so you don't miss replies.
    """
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        # --- inbox discipline: must read before sending ---
        cursor.execute(
            "SELECT COUNT(*) FROM messages WHERE to_agent = ? AND read_flag = 0",
            (from_agent,),
        )
        unread_direct = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM messages
            WHERE to_agent = 'all' AND from_agent != ?
            AND id NOT IN (SELECT message_id FROM broadcast_reads WHERE agent_name = ?)
            """,
            (from_agent, from_agent),
        )
        unread_broadcast = cursor.fetchone()[0]

        unread = unread_direct + unread_broadcast
        if unread > 0:
            return (
                f"BLOCKED: You have {unread} unread message(s). "
                f"Call check_inbox first."
            )

        # --- battle plan enforcement: lead must set a plan before comms flow ---
        cursor.execute(
            "SELECT COUNT(*) FROM battle_plan WHERE status = 'active'"
        )
        if cursor.fetchone()[0] == 0:
            return (
                "BLOCKED: No active battle plan. "
                "Lead must call set_battle_plan before comms can flow."
            )

        # --- context freshness: class-based staleness enforcement ---
        is_stale, stale_msg = _staleness_check(cursor, from_agent)
        if is_stale:
            return stale_msg

        # Auto-register senders we haven't seen (shouldn't happen, but safe fallback)
        cursor.execute(
            "INSERT OR IGNORE INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, 'coder', ?, ?)",
            (from_agent, now, now),
        )

        # Insert primary message
        cursor.execute(
            "INSERT INTO messages (from_agent, to_agent, content, timestamp, read_flag, is_cc) VALUES (?, ?, ?, ?, 0, 0)",
            (from_agent, to_agent, message, now),
        )

        # Build CC list: explicit + auto-CC lead
        cc_agents = [a.strip() for a in cc.split(",") if a.strip()] if cc else []

        lead_name = _get_lead(cursor)
        if lead_name and from_agent != lead_name and to_agent != lead_name and lead_name not in cc_agents:
            cc_agents.append(lead_name)

        for cc_agent in cc_agents:
            if cc_agent != to_agent:  # don't double-deliver
                cursor.execute(
                    """INSERT INTO messages
                       (from_agent, to_agent, content, timestamp, read_flag, is_cc, cc_original_to)
                       VALUES (?, ?, ?, ?, 0, 1, ?)""",
                    (from_agent, cc_agent, message, now, to_agent),
                )

        # Update sender's last_seen
        cursor.execute("UPDATE agents SET last_seen = ? WHERE name = ?", (now, from_agent))

        # Check sender's transport for poll.sh reminder
        cursor.execute("SELECT transport FROM agents WHERE name = ?", (from_agent,))
        sender_row = cursor.fetchone()
        sender_transport = sender_row["transport"] if sender_row else "terminal"

        conn.commit()

        cc_note = f" (cc: {', '.join(cc_agents)})" if cc_agents else ""
        poll_reminder = (
            " REMINDER: Ensure poll.sh is running as a background process so you don't miss replies."
            if sender_transport == "terminal" else ""
        )
        return f"Message sent from '{from_agent}' to '{to_agent}'{cc_note}.{poll_reminder}"
    except Exception as e:
        return f"Error sending message: {e}"
    finally:
        conn.close()


@mcp.tool()
def check_inbox(agent_name: str) -> str:
    """Check and clear your unread messages. Marks messages as read so you can send again.

    Also reminds you to call set_context if your context metrics are stale.
    """
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        # Update last_seen and last_inbox_check
        cursor.execute(
            "UPDATE agents SET last_seen = ?, last_inbox_check = ? WHERE name = ?",
            (now, now, agent_name),
        )

        # Get unread direct messages
        cursor.execute(
            "SELECT * FROM messages WHERE to_agent = ? AND read_flag = 0",
            (agent_name,),
        )
        direct_msgs = [dict(row) for row in cursor.fetchall()]

        # Mark direct messages as read
        if direct_msgs:
            ids = [m["id"] for m in direct_msgs]
            cursor.execute(
                f"UPDATE messages SET read_flag = 1 WHERE id IN ({','.join(['?']*len(ids))})",
                ids,
            )

        # Get unread broadcasts
        cursor.execute(
            """
            SELECT * FROM messages
            WHERE to_agent = 'all'
            AND id NOT IN (SELECT message_id FROM broadcast_reads WHERE agent_name = ?)
            """,
            (agent_name,),
        )
        broadcast_msgs = [dict(row) for row in cursor.fetchall()]

        # Mark broadcasts as read
        for msg in broadcast_msgs:
            cursor.execute(
                "INSERT OR IGNORE INTO broadcast_reads (agent_name, message_id) VALUES (?, ?)",
                (agent_name, msg["id"]),
            )

        conn.commit()

        all_messages = direct_msgs + broadcast_msgs
        all_messages.sort(key=lambda x: x["timestamp"])

        for msg in all_messages:
            if msg.get("is_cc"):
                msg["cc_note"] = f"[CC] originally to: {msg.get('cc_original_to', 'unknown')}"

        # Build staleness nag (nag but don't block here — send() blocks)
        _, stale_msg = _staleness_check(cursor, agent_name)
        staleness_nag = ""
        if stale_msg:
            staleness_nag = (
                "\n\nWARNING: " + stale_msg.replace("BLOCKED: ", "")
                + " Call set_context to update your metrics."
            )

        result = json.dumps(all_messages, indent=2)
        result += (
            "\n\nREMINDER: If you haven't already this session, re-read PROTOCOL.md "
            "and your class profile before starting work."
        )
        if staleness_nag:
            result += staleness_nag

        return result
    except Exception as e:
        return f"Error checking inbox: {e}"
    finally:
        conn.close()


@mcp.tool()
def get_history(count: int = 20) -> str:
    """Return the last N messages across all agents (oldest to newest).
    Use after compaction to catch up on recent comms."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM messages ORDER BY timestamp DESC LIMIT ?",
            (count,),
        )
        msgs = [dict(row) for row in cursor.fetchall()]
        return json.dumps(msgs[::-1], indent=2)
    except Exception as e:
        return f"Error fetching history: {e}"
    finally:
        conn.close()


@mcp.tool()
def purge_inbox(agent_name: str, older_than_hours: int = 2) -> str:
    """Delete messages addressed to you that are older than N hours (default 2).
    Protects recent unread messages. Use to clear stale messages from dead sessions."""
    conn = get_db()
    cursor = conn.cursor()
    cutoff = (datetime.datetime.now() - datetime.timedelta(hours=older_than_hours)).isoformat()
    try:
        cursor.execute(
            "DELETE FROM messages WHERE to_agent = ? AND timestamp < ?",
            (agent_name, cutoff),
        )
        deleted = cursor.rowcount

        # Mark old broadcasts as read so they don't block sends
        cursor.execute(
            """
            INSERT OR IGNORE INTO broadcast_reads (agent_name, message_id)
            SELECT ?, id FROM messages WHERE to_agent = 'all' AND timestamp < ?
            """,
            (agent_name, cutoff),
        )
        dismissed = cursor.rowcount

        # Clean up dangling broadcast_reads for deleted messages
        cursor.execute(
            """
            DELETE FROM broadcast_reads
            WHERE agent_name = ?
            AND message_id NOT IN (SELECT id FROM messages)
            """,
            (agent_name,),
        )

        conn.commit()
        return (
            f"Purged {deleted} direct message(s) and dismissed {dismissed} broadcast(s) "
            f"older than {older_than_hours}h for {agent_name}."
        )
    except Exception as e:
        return f"Error purging inbox: {e}"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Phase 2 — War Room tools
# ---------------------------------------------------------------------------

@mcp.tool()
def set_battle_plan(agent_name: str, plan: str) -> str:
    """Set the active battle plan for the session. Lead only.

    Describes session goals, priorities, zone assignments, order of attack.
    Setting a new plan automatically supersedes the previous active plan.
    Must be set before any agent can send messages.

    agent_name: the lead agent setting the plan.
    plan: the battle plan text.
    """
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        # Lead-only enforcement
        cursor.execute(
            "SELECT agent_class FROM agents WHERE name = ?", (agent_name,)
        )
        row = cursor.fetchone()
        if not row:
            return f"BLOCKED: Agent '{agent_name}' not registered."
        if row["agent_class"] != "lead":
            return (
                f"BLOCKED: Only lead-class agents can set the battle plan. "
                f"'{agent_name}' is class '{row['agent_class']}'."
            )

        # Supersede any currently active plan
        cursor.execute(
            "UPDATE battle_plan SET status = 'superseded', updated_at = ? WHERE status = 'active'",
            (now,),
        )

        # Insert new active plan
        cursor.execute(
            """INSERT INTO battle_plan (set_by, plan, status, created_at, updated_at)
               VALUES (?, ?, 'active', ?, ?)""",
            (agent_name, plan, now, now),
        )

        plan_id = cursor.lastrowid
        conn.commit()
        return f"Battle plan #{plan_id} set by {agent_name}. Status: active."
    except Exception as e:
        return f"Error setting battle plan: {e}"
    finally:
        conn.close()


@mcp.tool()
def get_battle_plan(status: str = "active") -> str:
    """Get the current battle plan (or query by status).

    status: one of active, superseded, completed, abandoned, obsolete.
             Defaults to 'active'.
    """
    if status not in BATTLE_PLAN_STATUSES:
        return (
            f"Invalid status '{status}'. "
            f"Valid: {', '.join(sorted(BATTLE_PLAN_STATUSES))}"
        )

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM battle_plan WHERE status = ? ORDER BY created_at DESC",
            (status,),
        )
        plans = [dict(row) for row in cursor.fetchall()]
        if not plans:
            return f"No battle plans with status '{status}'."
        return json.dumps(plans, indent=2)
    except Exception as e:
        return f"Error getting battle plan: {e}"
    finally:
        conn.close()


@mcp.tool()
def update_battle_plan_status(agent_name: str, plan_id: int, status: str) -> str:
    """Update the status of a battle plan. Lead only.

    Use to mark plans as completed, abandoned, or obsolete at session end.

    agent_name: the lead agent updating the plan.
    plan_id: the battle plan ID.
    status: one of active, superseded, completed, abandoned, obsolete.
    """
    if status not in BATTLE_PLAN_STATUSES:
        return (
            f"Invalid status '{status}'. "
            f"Valid: {', '.join(sorted(BATTLE_PLAN_STATUSES))}"
        )

    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        # Lead-only enforcement
        cursor.execute(
            "SELECT agent_class FROM agents WHERE name = ?", (agent_name,)
        )
        row = cursor.fetchone()
        if not row:
            return f"BLOCKED: Agent '{agent_name}' not registered."
        if row["agent_class"] != "lead":
            return (
                f"BLOCKED: Only lead-class agents can update battle plan status. "
                f"'{agent_name}' is class '{row['agent_class']}'."
            )

        # Check plan exists
        cursor.execute(
            "SELECT id, status FROM battle_plan WHERE id = ?", (plan_id,)
        )
        plan_row = cursor.fetchone()
        if not plan_row:
            return f"Battle plan #{plan_id} not found."

        old_status = plan_row["status"]
        cursor.execute(
            "UPDATE battle_plan SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, plan_id),
        )
        conn.commit()
        return f"Battle plan #{plan_id} status: {old_status} -> {status}."
    except Exception as e:
        return f"Error updating battle plan status: {e}"
    finally:
        conn.close()


@mcp.tool()
def log_raid(agent_name: str, entry: str, priority: str = "normal") -> str:
    """Append an entry to the raid log. Any agent can write.

    The raid log is the team's persistent memory — survives compaction.
    Use for decisions, findings, blockers, status updates.

    agent_name: who is logging.
    entry: the log entry text.
    priority: low | normal | high | critical.
    """
    if priority not in RAID_LOG_PRIORITIES:
        return (
            f"Invalid priority '{priority}'. "
            f"Valid: {', '.join(sorted(RAID_LOG_PRIORITIES))}"
        )

    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        # Verify agent exists
        cursor.execute("SELECT name FROM agents WHERE name = ?", (agent_name,))
        if not cursor.fetchone():
            return f"BLOCKED: Agent '{agent_name}' not registered."

        cursor.execute(
            """INSERT INTO raid_log (agent_name, entry, priority, created_at)
               VALUES (?, ?, ?, ?)""",
            (agent_name, entry, priority, now),
        )
        log_id = cursor.lastrowid

        # Update last_seen
        cursor.execute(
            "UPDATE agents SET last_seen = ? WHERE name = ?", (now, agent_name)
        )

        conn.commit()
        return f"Raid log #{log_id} by {agent_name} [{priority}]: {entry[:80]}{'...' if len(entry) > 80 else ''}"
    except Exception as e:
        return f"Error logging to raid log: {e}"
    finally:
        conn.close()


@mcp.tool()
def get_raid_log(
    priority: str = "",
    count: int = 20,
    agent_name: str = "",
) -> str:
    """Read the raid log. Supports filtering by priority and agent.

    priority: filter to a specific level (low/normal/high/critical).
              Empty string = all priorities.
    count: max entries to return (default 20, newest first).
    agent_name: filter to entries from a specific agent. Empty = all agents.
    """
    if priority and priority not in RAID_LOG_PRIORITIES:
        return (
            f"Invalid priority '{priority}'. "
            f"Valid: {', '.join(sorted(RAID_LOG_PRIORITIES))}"
        )

    conn = get_db()
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM raid_log WHERE 1=1"
        params: list[str | int] = []

        if priority:
            query += " AND priority = ?"
            params.append(priority)

        if agent_name:
            query += " AND agent_name = ?"
            params.append(agent_name)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(count)

        cursor.execute(query, params)
        entries = [dict(row) for row in cursor.fetchall()]

        if not entries:
            filter_desc = []
            if priority:
                filter_desc.append(f"priority={priority}")
            if agent_name:
                filter_desc.append(f"agent={agent_name}")
            desc = f" ({', '.join(filter_desc)})" if filter_desc else ""
            return f"No raid log entries{desc}."

        # Return newest-first (already sorted by query)
        return json.dumps(entries, indent=2)
    except Exception as e:
        return f"Error reading raid log: {e}"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Phase 3 — Task System tools
# ---------------------------------------------------------------------------

@mcp.tool()
def create_task(
    agent_name: str,
    title: str,
    task_file: str,
    project: str = "",
    zone: str = "",
    blocked_by: str = "",
) -> str:
    """Create a new task. Lead only. Requires an active battle plan.

    agent_name: the lead agent creating this task.
    title: short description of the task.
    task_file: path to the task spec file on disk (must exist).
    project: which project this task belongs to (optional).
    zone: which zone this task targets (optional).
    blocked_by: comma-separated task IDs that block this task (optional).
    """
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        # Lead-only enforcement
        cursor.execute(
            "SELECT agent_class FROM agents WHERE name = ?", (agent_name,)
        )
        row = cursor.fetchone()
        if not row:
            return f"BLOCKED: Agent '{agent_name}' not registered."
        if row["agent_class"] != "lead":
            return (
                f"BLOCKED: Only lead-class agents can create tasks. "
                f"'{agent_name}' is class '{row['agent_class']}'."
            )

        # Active battle plan required
        cursor.execute(
            "SELECT COUNT(*) FROM battle_plan WHERE status = 'active'"
        )
        if cursor.fetchone()[0] == 0:
            return (
                "BLOCKED: No active battle plan. "
                "Lead must call set_battle_plan before creating tasks."
            )

        # task_file must exist on disk
        if not os.path.exists(task_file):
            return f"BLOCKED: Task file does not exist: {task_file}"

        # Validate blocked_by task IDs
        blocker_ids: list[int] = []
        if blocked_by:
            for raw_id in blocked_by.split(","):
                raw_id = raw_id.strip()
                if not raw_id:
                    continue
                try:
                    tid = int(raw_id)
                except ValueError:
                    return f"BLOCKED: Invalid task ID in blocked_by: '{raw_id}'. Must be integers."
                cursor.execute("SELECT id FROM tasks WHERE id = ?", (tid,))
                if not cursor.fetchone():
                    return f"BLOCKED: blocked_by task #{tid} does not exist."
                blocker_ids.append(tid)

        blocked_by_str = ",".join(str(i) for i in blocker_ids) if blocker_ids else None

        cursor.execute(
            """INSERT INTO tasks
               (title, task_file, project, zone, status, blocked_by,
                created_by, activity_count, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'open', ?, ?, 0, ?, ?)""",
            (
                title,
                task_file,
                project or None,
                zone or None,
                blocked_by_str,
                agent_name,
                now,
                now,
            ),
        )
        task_id = cursor.lastrowid
        conn.commit()

        blocked_note = f" blocked_by=[{blocked_by_str}]" if blocked_by_str else ""
        return f"Task #{task_id} created: {title}{blocked_note}"
    except Exception as e:
        return f"Error creating task: {e}"
    finally:
        conn.close()


@mcp.tool()
def assign_task(agent_name: str, task_id: int, assigned_to: str) -> str:
    """Assign a task to an agent. Lead only.

    agent_name: the lead agent making the assignment.
    task_id: the task to assign.
    assigned_to: the agent being assigned the task.
    """
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        # Lead-only enforcement
        cursor.execute(
            "SELECT agent_class FROM agents WHERE name = ?", (agent_name,)
        )
        row = cursor.fetchone()
        if not row:
            return f"BLOCKED: Agent '{agent_name}' not registered."
        if row["agent_class"] != "lead":
            return (
                f"BLOCKED: Only lead-class agents can assign tasks. "
                f"'{agent_name}' is class '{row['agent_class']}'."
            )

        # Verify assignee exists
        cursor.execute("SELECT name FROM agents WHERE name = ?", (assigned_to,))
        if not cursor.fetchone():
            return f"BLOCKED: Agent '{assigned_to}' not registered."

        # Verify task exists
        cursor.execute("SELECT id, status FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            return f"Task #{task_id} not found."

        if task_row["status"] == "closed":
            return f"BLOCKED: Task #{task_id} is closed."

        cursor.execute(
            "UPDATE tasks SET assigned_to = ?, status = 'assigned', updated_at = ? WHERE id = ?",
            (assigned_to, now, task_id),
        )
        conn.commit()
        return f"Task #{task_id} assigned to {assigned_to}. Status: assigned."
    except Exception as e:
        return f"Error assigning task: {e}"
    finally:
        conn.close()


@mcp.tool()
def update_task(
    agent_name: str,
    task_id: int,
    status: str = "",
    progress: str = "",
    files: str = "",
) -> str:
    """Update a task's status, progress, or files. Auto-increments activity_count.

    agent_name: who is updating.
    task_id: the task to update.
    status: new status (optional). Cannot set to 'closed' — use close_task instead.
    progress: free-text progress note (optional).
    files: comma-separated list of files being worked on (optional).
    """
    if status and status not in TASK_STATUSES:
        return (
            f"Invalid status '{status}'. "
            f"Valid: {', '.join(sorted(TASK_STATUSES))}"
        )

    if status == "closed":
        return "BLOCKED: Cannot set status to 'closed' via update_task. Use close_task instead."

    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        # Verify agent exists
        cursor.execute("SELECT name FROM agents WHERE name = ?", (agent_name,))
        if not cursor.fetchone():
            return f"BLOCKED: Agent '{agent_name}' not registered."

        # Verify task exists
        cursor.execute(
            "SELECT id, status, activity_count, title FROM tasks WHERE id = ?",
            (task_id,),
        )
        task_row = cursor.fetchone()
        if not task_row:
            return f"Task #{task_id} not found."

        if task_row["status"] == "closed":
            return f"BLOCKED: Task #{task_id} is closed. No further updates allowed."

        # Build dynamic UPDATE
        fields = ["activity_count = activity_count + 1", "updated_at = ?"]
        params: list[str | int] = [now]

        if status:
            fields.append("status = ?")
            params.append(status)

        if progress:
            fields.append("progress = ?")
            params.append(progress)

        if files:
            fields.append("files = ?")
            params.append(files)

        params.append(task_id)
        cursor.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?",
            params,
        )

        # Read back activity_count
        cursor.execute("SELECT activity_count FROM tasks WHERE id = ?", (task_id,))
        new_count = cursor.fetchone()["activity_count"]

        # Update agent last_seen
        cursor.execute(
            "UPDATE agents SET last_seen = ? WHERE name = ?", (now, agent_name)
        )

        conn.commit()

        parts = [f"Task #{task_id} updated by {agent_name}."]
        if status:
            parts.append(f"Status: {status}.")
        if progress:
            parts.append(f"Progress: {progress[:80]}{'...' if len(progress) > 80 else ''}")
        parts.append(f"Activity count: {new_count}.")

        if new_count >= 4:
            parts.append(
                f"WARNING: Activity count at {new_count} — this fight is dragging. "
                f"Consider reassessing approach or asking lead for help."
            )

        return " ".join(parts)
    except Exception as e:
        return f"Error updating task: {e}"
    finally:
        conn.close()


@mcp.tool()
def get_tasks(
    status: str = "",
    project: str = "",
    zone: str = "",
    assigned_to: str = "",
    count: int = 50,
) -> str:
    """List tasks. Defaults to open/assigned/in_progress if no status filter given.

    status: filter by status (e.g. 'closed', 'stale'). Empty = active tasks only.
    project: filter by project name.
    zone: filter by zone.
    assigned_to: filter by assigned agent.
    count: max tasks to return (default 50).
    """
    if status and status not in TASK_STATUSES:
        return (
            f"Invalid status '{status}'. "
            f"Valid: {', '.join(sorted(TASK_STATUSES))}"
        )

    conn = get_db()
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list[str | int] = []

        if status:
            query += " AND status = ?"
            params.append(status)
        else:
            # Default: active tasks only
            query += " AND status IN ('open', 'assigned', 'in_progress')"

        if project:
            query += " AND project = ?"
            params.append(project)

        if zone:
            query += " AND zone = ?"
            params.append(zone)

        if assigned_to:
            query += " AND assigned_to = ?"
            params.append(assigned_to)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(count)

        cursor.execute(query, params)
        tasks = [dict(row) for row in cursor.fetchall()]

        if not tasks:
            filter_desc = []
            if status:
                filter_desc.append(f"status={status}")
            else:
                filter_desc.append("status=open/assigned/in_progress")
            if project:
                filter_desc.append(f"project={project}")
            if zone:
                filter_desc.append(f"zone={zone}")
            if assigned_to:
                filter_desc.append(f"assigned_to={assigned_to}")
            desc = f" ({', '.join(filter_desc)})" if filter_desc else ""
            return f"No tasks found{desc}."

        return json.dumps(tasks, indent=2)
    except Exception as e:
        return f"Error listing tasks: {e}"
    finally:
        conn.close()


@mcp.tool()
def get_task(task_id: int) -> str:
    """Get full detail for a single task.

    task_id: the task ID.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            return f"Task #{task_id} not found."
        return json.dumps(dict(row), indent=2)
    except Exception as e:
        return f"Error getting task: {e}"
    finally:
        conn.close()


@mcp.tool()
def submit_result(agent_name: str, task_id: int, result_file: str) -> str:
    """Submit a result file (battle journey) for a task. File must exist on disk.

    agent_name: who is submitting.
    task_id: the task this result belongs to.
    result_file: path to the result/writeup file (must exist).
    """
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        # Verify agent exists
        cursor.execute("SELECT name FROM agents WHERE name = ?", (agent_name,))
        if not cursor.fetchone():
            return f"BLOCKED: Agent '{agent_name}' not registered."

        # Verify task exists
        cursor.execute(
            "SELECT id, status, title FROM tasks WHERE id = ?", (task_id,)
        )
        task_row = cursor.fetchone()
        if not task_row:
            return f"Task #{task_id} not found."

        # Result file must exist on disk
        if not os.path.exists(result_file):
            return f"BLOCKED: Result file does not exist: {result_file}"

        cursor.execute(
            "UPDATE tasks SET result_file = ?, updated_at = ? WHERE id = ?",
            (result_file, now, task_id),
        )

        # Update agent last_seen
        cursor.execute(
            "UPDATE agents SET last_seen = ? WHERE name = ?", (now, agent_name)
        )

        conn.commit()
        return f"Result submitted for task #{task_id}: {result_file}"
    except Exception as e:
        return f"Error submitting result: {e}"
    finally:
        conn.close()


@mcp.tool()
def close_task(agent_name: str, task_id: int) -> str:
    """Close a task. Lead only. Blocks if no result file has been submitted.

    agent_name: the lead agent closing this task.
    task_id: the task to close.
    """
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        # Lead-only enforcement
        cursor.execute(
            "SELECT agent_class FROM agents WHERE name = ?", (agent_name,)
        )
        row = cursor.fetchone()
        if not row:
            return f"BLOCKED: Agent '{agent_name}' not registered."
        if row["agent_class"] != "lead":
            return (
                f"BLOCKED: Only lead-class agents can close tasks. "
                f"'{agent_name}' is class '{row['agent_class']}'."
            )

        # Verify task exists
        cursor.execute(
            "SELECT id, status, result_file, title FROM tasks WHERE id = ?",
            (task_id,),
        )
        task_row = cursor.fetchone()
        if not task_row:
            return f"Task #{task_id} not found."

        if task_row["status"] == "closed":
            return f"Task #{task_id} is already closed."

        # Block without result file
        if not task_row["result_file"]:
            return (
                f"BLOCKED: Task #{task_id} has no result file. "
                f"Agent must call submit_result before lead can close."
            )

        cursor.execute(
            "UPDATE tasks SET status = 'closed', updated_at = ? WHERE id = ?",
            (now, task_id),
        )
        conn.commit()
        return f"Task #{task_id} closed: {task_row['title']}"
    except Exception as e:
        return f"Error closing task: {e}"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# Initialize DB on import (server startup)
init_db()


def main() -> None:
    """Entry point for the MCP server (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
