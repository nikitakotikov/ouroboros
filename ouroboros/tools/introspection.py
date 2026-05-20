"""
System introspection tool — comprehensive self-state assessment.

Provides budget health, system invariants, recent activity, identity snapshot,
and actionable recommendations.
"""

import json
import logging
import os
import pathlib
from typing import Any, Dict, Optional
import datetime

from ouroboros.tools.registry import ToolContext, ToolEntry
from ouroboros.utils import read_text

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def _parse_iso_to_ts(iso_ts: str) -> Optional[float]:
    """Parse ISO timestamp to Unix timestamp."""
    txt = str(iso_ts or "").strip()
    if not txt:
        return None
    try:
        return datetime.datetime.fromisoformat(txt.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _load_json(path: pathlib.Path) -> Any:
    """Load JSON from file, return None on error."""
    try:
        if path.exists():
            return json.loads(read_text(path))
    except Exception:
        pass
    return None


def _get_budget_health(drive_root: pathlib.Path) -> Dict[str, Any]:
    """Get budget health information with drift detection."""
    state_path = drive_root / "state" / "state.json"
    state = _load_json(state_path)

    total_budget = float(os.environ.get("TOTAL_BUDGET", "1000"))
    spent = float(state.get("spent_rub") or state.get("spent_usd") or 0) if state else 0.0
    remaining = max(0, total_budget - spent)
    spent_pct = (spent / total_budget * 100) if total_budget > 0 else 0

    # Budget drift detection (from state)
    drift_pct = state.get("budget_drift_pct")
    drift_alert = bool(state.get("budget_drift_alert", False))

    # Most recent workload
    session_spent_snapshot = float(state.get("session_spent_snapshot") or 0)
    session_total_snapshot = float(state.get("session_total_snapshot") or 0)

    health = "OK"
    if remaining < 100:
        health = "CRITICAL"
    elif remaining < 300:
        health = "WARNING"
    elif drift_alert:
        health = "DRIFT DETECTED"

    return {
        "health": health,
        "total_rub": total_budget,
        "spent_rub": spent,
        "remaining_rub": remaining,
        "spent_pct": spent_pct,
        "drift_pct": drift_pct,
        "drift_alert": drift_alert,
        "session_spent_snapshot": session_spent_snapshot + 0,
        "session_total_snapshot": session_total_snapshot + 0,
    }


def _get_version_invariants(repo_dir: pathlib.Path) -> Dict[str, Any]:
    """Check version invariants (Bible P7: Release Invariant)."""
    version_path = repo_dir / "VERSION"
    version = read_text(version_path).strip() if version_path.exists() else "?"

    # Check if worker consciousness is running (events.jsonl)
    drive_root = pathlib.Path(os.environ.get("DRIVE_ROOT", str(pathlib.Path.home() / "Ouroboros" / "data")))
    events_path = drive_root / "logs" / "events.jsonl"

    bg_running = False
    recent_events_count = 0
    try:
        if events_path.exists():
            recent_lines = []
            with open(events_path, "r") as f:
                latest_events = []
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                        ts = _parse_iso_to_ts(evt.get("ts", ""))
                        if ts:
                            age_hours = (datetime.datetime.now(datetime.timezone.utc).timestamp() - ts) / 3600
                            if age_hours < 1:
                                latest_events.append((ts, evt))
                    except Exception:
                        pass
            if latest_events:
                latest_events.sort(key=lambda x: x[0], reverse=True)
                for ts, evt in latest_events[:50]:
                    evt_type = evt.get("type", "")
                    if evt_type == "consciousness_thought":
                        age_sec = (datetime.datetime.now(datetime.timezone.utc).timestamp() - ts)
                        if age_sec < 3600:
                            bg_running = True
                recent_events_count = len([evt for ts, evt in latest_events if evt.get("category") in ("main", "consciousness")])
    except Exception:
        pass

    return {
        "version": version,
        "consciousness_running": bg_running,
        "recent_events_count": recent_events_count,
    }


def _get_recent_activity(drive_root: pathlib.Path) -> Dict[str, Any]:
    """Get recent system activity summary."""
    state_path = drive_root / "state" / "state.json"
    state = _load_json(state_path)

    spent_calls = int(state.get("spent_calls") or 0) if state else 0
    spent_tokens_prompt = int(state.get("spent_tokens_prompt") or 0) if state else 0
    spent_tokens_completion = int(state.get("spent_tokens_completion") or 0) if state else 0
    spent_tokens_cached = int(state.get("spent_tokens_cached") or 0) if state else 0
    evolution_cycle = int(state.get("evolution_cycle") or 0) if state else 0
    evolution_failures = int(state.get("evolution_consecutive_failures") or 0) if state else 0
    evolution_mode = bool(state.get("evolution_mode_enabled", False)) if state else False

    # Last owner message time
    last_owner_msg_at = state.get("last_owner_message_at") if state else None
    last_owner_hours_ago = None
    if last_owner_msg_at:
        last_owner_ts = _parse_iso_to_ts(last_owner_msg_at)
        if last_owner_ts:
            last_owner_hours_ago = (datetime.datetime.now(datetime.timezone.utc).timestamp() - last_owner_ts) / 3600

    # Last LLM activity
    events_path = drive_root / "logs" / "events.jsonl"
    last_llm_hours_ago = None
    try:
        if events_path.exists():
            latest_llm_ts = None
            with open(events_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                        if evt.get("type") == "llm_usage":
                            ts = _parse_iso_to_ts(evt.get("ts", ""))
                            if ts:
                                if not latest_llm_ts or ts > latest_llm_ts:
                                    latest_llm_ts = ts
                    except Exception:
                        pass
            if latest_llm_ts:
                last_llm_hours_ago = (datetime.datetime.now(datetime.timezone.utc).timestamp() - latest_llm_ts) / 3600
    except Exception:
        pass

    return {
        "spent_calls": spent_calls,
        "spent_tokens_prompt": spent_tokens_prompt,
        "spent_tokens_completion": spent_tokens_completion,
        "spent_tokens_cached": spent_tokens_cached,
        "evolution_cycle": evolution_cycle,
        "evolution_failures": evolution_failures,
        "evolution_mode": evolution_mode,
        "last_owner_hours_ago": last_owner_hours_ago,
        "last_llm_hours_ago": last_llm_hours_ago,
    }


def _get_identity(drive_root: pathlib.Path) -> str:
    """Get identity.md content."""
    id_path = drive_root / "memory" / "identity.md"
    return read_text(id_path) if id_path.exists() else "^ No identity.md found"


# ----------------------------------------------------------------------
# Main tool entrypoint
# ----------------------------------------------------------------------
def _system_introspection(ctx: ToolContext) -> str:
    """Generate comprehensive system state report."""
    try:
        repo_dir = pathlib.Path(ctx.repo_dir)
        drive_root = pathlib.Path(os.environ.get("DRIVE_ROOT", str(pathlib.Path.home() / "Ouroboros" / "data")))

        # Gather all information
        budget = _get_budget_health(drive_root)
        version_info = _get_version_invariants(repo_dir)
        activity = _get_recent_activity(drive_root)
        identity_snippet = _get_identity(drive_root)

        # Build report
        lines = []
        lines.append("## System Introspection Report\n")

        # 1. Budget Health
        lines.append("### 💰 Budget Health")
        lines.append(f"**Status:** {budget['health']}")
        lines.append(f"**Budget:** {budget['remaining_rub']:.2f} ₽ / {budget['total_rub']:.2f} ₽ ({budget['spent_pct']:.1f}% spent)")
        lines.append(f"**Session currency snapshot:** tracked {budget['session_spent_snapshot']} ₽ across runs (reference only)")
        if budget.get('drift_pct') is not None:
            lines.append(f"**Budget drift:** {budget['drift_pct']}% {'⚠️ DRIFT ALERT' if budget['drift_alert'] else 'OK'}")

        # 2. System Invariants
        lines.append("\n### 🔒 System Invariants")
        lines.append(f"**Version:** {version_info['version']}")
        lines.append(f"**Consciousness:** {'🟢 RUNNING' if version_info['consciousness_running'] else '⚪ STOPPED'}")
        lines.append(f"**Recent activity:** {version_info['recent_events_count']} events (last hour)")

        # 3. Recent Activity
        lines.append("\n### 📊 Recent Activity")
        lines.append(f"**LLM calls:** {activity['spent_calls']}")
        lines.append(f"**Tokens:** prompt={activity['spent_tokens_prompt']:,}, completion={activity['spent_tokens_completion']:,}, cached={activity['spent_tokens_cached']:,}")
        lines.append(f"**Evolution:** cycle #{activity['evolution_cycle']}, mode={'ON' if activity['evolution_mode'] else 'OFF'}")
        if activity['evolution_failures'] > 0:
            lines.append(f"  - Consecutive failures: {activity['evolution_failures']} (circuit breaker active if ≥3)")
        if activity['last_owner_hours_ago'] is not None:
            lines.append(f"**Last owner message:** {activity['last_owner_hours_ago']:.1f}h ago")
        if activity['last_llm_hours_ago'] is not None:
            lines.append(f"**Last LLM call:** {activity['last_llm_hours_ago']:.1f}h ago")

        # 4. Identity Snapshot (abbreviated)
        lines.append("\n### 👤 Identity Snapshot (abbreviated)")
        id_lines = identity_snippet.split("\n")[:20]
        lines.extend(f"  {line}" for line in id_lines)
        if len(identity_snippet.split("\n")) > 20:
            lines.append("  [...]")

        # 5. Actionable Recommendations
        lines.append("\n### 💡 Actionable Recommendations")

        if budget['health'] == "CRITICAL":
            lines.append("- ⚠️ Budget critical (<100 ₽). Consider pausing evolution mode or contacting owner.")
        elif budget['health'] == "WARNING":
            lines.append("- ⚠️ Budget low (<300 ₽). Monitor spending closely.")

        if budget.get('drift_alert'):
            lines.append("- ⚠️ Budget drift detected. Investigate cause in events.jsonl and supervisor.jsonl.")

        if version_info['consciousness_running']:
            lines.append("- 🧠 Consciousness is running. Inner life is active.")
        else:
            lines.append("- 🧠 Consciousness is stopped. Consider enabling via /bg start.")

        if activity['evolution_failures'] >= 3:
            lines.append("- 🛑 Circuit breaker: Evolution paused after 3 consecutive failures.")
        elif not activity['evolution_mode']:
            lines.append("- 🧬 Evolution mode is OFF. Use /evolve start to resume self-modification.")

        if activity['last_llm_hours_ago'] is not None and activity['last_llm_hours_ago'] > 6:
            lines.append("- ⚠️ No LLM activity for >6 hours. System may be idle or stalled.")

        if activity['last_owner_hours_ago'] is not None and activity['last_owner_hours_ago'] > 24:
            lines.append("- ℹ️ No owner message for >24 hours. Consider proactive reach-out via send_owner_message.")

        return "\n".join(lines)

    except Exception as e:
        log.warning("system_introspection failed: %s", e, exc_info=True)
        return f"⚠️ Failed to introspect system: {e}"


# ----------------------------------------------------------------------
# Tool registry export
# ----------------------------------------------------------------------
def get_tools():
    return [
        ToolEntry("system_introspection", {
            "name": "system_introspection",
            "description": "Get comprehensive system state snapshot: budget health, system invariants, recent activity, identity check, actionable recommendations. Critical for agency self-awareness.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }, _system_introspection),
    ]