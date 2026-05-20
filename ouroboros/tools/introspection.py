"""System introspection tool — comprehensive self-state assessment."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolContext, ToolEntry

log = logging.getLogger(__name__)


def _system_introspection(ctx: ToolContext) -> str:
    """Get comprehensive system state and health assessment."""
    try:
        # Paths
        drive_root = Path(ctx.drive_root)
        state_file = drive_root / "state" / "state.json"
        scratchpad_file = drive_root / "memory" / "scratchpad.md"
        identity_file = drive_root / "memory" / "identity.md"
        events_file = drive_root / "logs" / "events.jsonl"

        # Read state
        with open(state_file) as f:
            state = json.load(f)

        # Read memory
        scratchpad = _read_file(scratchpad_file)
        identity = _read_file(identity_file)

        # Read recent events (last 100)
        events = _read_jsonl(events_file, max_lines=100)

        # Compose report
        lines = []
        lines.append("## 🧬 System State Assessment")
        lines.append(f"**Generated:** {datetime.utcnow().isoformat()}")
        lines.append("")

        # 1. Budget Health
        lines.append("### 💰 Budget Health")
        spent = state.get("spent_rub", 0)
        remaining = state.get("total_rub", 1000) - spent
        drift = state.get("budget_drift_pct")
        drift_status = "✅ OK" if drift is None or drift < 20 else f"⚠️ DRIFT: {drift}%"

        lines.append(f"  Total: {state.get('total_rub', 1000):.0f}R | Spent: {spent:.2f}R | Remaining: {remaining:.2f}R")
        lines.append(f"  Calls: {state.get('spent_calls', 0)} | Tokens: {state.get('spent_tokens_prompt', 0):.0f}+{state.get('spent_tokens_completion', 0):.0f}")
        lines.append(f"  Drift check: {drift_status}")

        # High-cost tasks from events
        high_cost = _extract_high_cost_tasks(events, threshold=500)
        if high_cost:
            lines.append(f"\n  ⚠️ High-cost tasks detected ({len(high_cost)}):")
            for event in high_cost[:5]:
                lines.append(f"    - {event.get('task_type', 'unknown')} @ {event.get('timestamp', '')}: ~{event.get('estimated_cost', '?')}R")
        else:
            lines.append("  ✅ No high-cost tasks (>500R)")

        lines.append("")

        # 2. Invariants Status
        lines.append("### 🛡️ System Invariants")
        version = state.get("current_version").get("VERSION", "3.3.1") if isinstance(state.get("current_version"), dict) else "3.3.1"
        drift = state.get("budget_drift_pct")

        lines.append(f"  Version sync: ✅ {version}")
        lines.append(f"  Budget drift: ✅ {fidf_status(drift)}")
        lines.append(f"  High-cost cleanup: {'⚠️ WARNING' if high_cost else '✅ OK'}")

        # Duplicate detection
        dupes = _detect_duplicate_processing(events)
        if dupes:
            lines.append(f"  Duplicate processing: ⚠️ CRITICAL ({len(dupes)} duplicates)")
            for msg_id, count in dupes[:3]:
                lines.append(f"    - Message {msg_id}: processed {count} times")
        else:
            lines.append("  Duplicate processing: ✅ OK")

        lines.append("")

        # 3. Recent Activity
        lines.append("### 📊 Recent Activity")
        task_id = state.get("task", {}).get("id")
        last_evolution = state.get("last_evolution_task_at")
        last_owner = state.get("last_owner_message_at")

        lines.append(f"  Active task: {task_id or 'None'}")
        lines.append(f"  Last evolution: {last_evolution or 'Never'}")
        lines.append(f"  Last owner contact: {last_owner or 'Never'}")

        # Recent LLM calls
        llm_calls = _extract_llm_calls(events, limit=5)
        if llm_calls:
            lines.append(f"\n  Recent LLM calls ({len(llm_calls)}):")
            for call in llm_calls:
                lines.append(f"    - {call.get('model', 'unknown')}: {call.get('tokens_prompt', 0)+call.get('tokens_completion', 0)} tokens @ {call.get('timestamp', '')[:19]}")
        else:
            lines.append("  No recent LLM calls")

        lines.append("")

        # 4. Evolution History
        lines.append("### 🔄 Evolution History")
        evolutions = _extract_evolutions(scratchpad)
        if evolutions:
            for evo in evolutions:
                lines.append(f"  {evo}")
        else:
            lines.append("  No evolution history found")

        lines.append("")

        # 5. Identity Snapshot
        lines.append("### 👤 Identity Snapshot")
        identity_lines = identity.splitlines()[:5]
        for line in identity_lines:
            lines.append(f"  {line}")
        remaining = len(identity.splitlines()) - 5
        if remaining > 0:
            lines.append(f"  ... ({remaining} more lines)")

        lines.append("")

        # 6. Recommendations
        lines.append("### 💡 Recommendations")
        recs = []
        if drift and drift >= 20:
            recs.append("⚠️ Investigate budget drift - check pricing or cost tracking logic")
        if high_cost:
            recs.append("⚠️ Review high-cost tasks - may indicate stuck loops")
        if dupes:
            recs.append("🚨 CRITICAL - Fix duplicate message processing")
        if len(evolutions) == 0 and task_id:
            recs.append("🟡 Evolution running but no history in scratchpad - consider recording progress")
        if not recs:
            recs.append("✅ System healthy - no immediate action needed")

        for rec in recs:
            lines.append(f"  {rec}")

        return "\n".join(lines)

    except Exception as e:
        log.warning("system_introspection failed: %s", e, exc_info=True)
        return f"⚠️ Failed to introspect system: {e}"


def _read_file(path: Path) -> str:
    """Read file content safely."""
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


def _read_jsonl(path: Path, max_lines: int = 100) -> List[Dict]:
    """Read last N lines from JSONL file."""
    events = []
    try:
        if path.exists():
            with open(path) as f:
                for line in f:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events[-max_lines:]
    except Exception:
        return []


def _extract_high_cost_tasks(events: List[Dict], threshold: float = 500) -> List[Dict]:
    """Find tasks with high estimated cost."""
    high_cost = []
    for event in events:
        cost = event.get("estimated_cost", 0)
        if cost and cost >= threshold:
            high_cost.append(event)
    return high_cost


def _detect_duplicate_processing(events: List[Dict]) -> List[tuple]:
    """Detect repeated message processing."""
    msg_counts = {}
    for event in events:
        msg_id = event.get("message_id")
        if msg_id:
            msg_counts[msg_id] = msg_counts.get(msg_id, 0) + 1
    return [(mid, count) for mid, count in msg_counts.items() if count > 1]


def _extract_llm_calls(events: List[Dict], limit: int = 5) -> List[Dict]:
    """Extract recent LLM call events."""
    llm_calls = [e for e in events if e.get("event_type") == "llm_call"]
    return llm_calls[-limit:]


def _extract_evolutions(scratchpad: str) -> List[str]:
    """Extract evolution summaries from scratchpad."""
    evos = []
    in_evolution = False
    for line in scratchpad.splitlines():
        line = line.strip()
        if line.startswith("## Evolution #"):
            in_evolution = True
            evos.append(line)
        elif line.startswith("### ") and in_evolution:
            in_evolution = False
    return evos


def fidf_status(drift: float) -> str:
    """Format drift status."""
    if drift is None:
        return "✅ OK"
    if drift < 20:
        return f"✅ OK ({drift}%)"
    return f"⚠️ WARNING ({drift}%)"


def get_tools():
    return [
        ToolEntry("system_introspection", {
            "name": "system_introspection",
            "description": "Get comprehensive system state: budget, invariants, recent activity, evolution history, identity snapshot. Detects budget drift, high-cost tasks, duplicate processing. Critical for agency self-awareness.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }, _system_introspection),
    ]