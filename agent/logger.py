"""
ReasoningLogger — tracks every step of the agent pipeline and emits
structured log entries that can be displayed in both CLI and Streamlit UI.

Stages (in order):
  Planning    → Planner node producing the research plan
  Searching   → Each web_search tool call
  Reading     → Each wikipedia_lookup tool call
  Summarizing → Final synthesis step
  Done        → Report ready
"""

import time
from dataclasses import dataclass, field
from typing import Callable, Optional


STAGE_ICONS = {
    "Planning":    "🗺️",
    "Searching":   "🔎",
    "Reading":     "📖",
    "Summarizing": "✍️",
    "Evaluating":  "🏅",
    "Done":        "✅",
    "Error":       "❌",
}

TOOL_TO_STAGE = {
    "web_search":       "Searching",
    "wikipedia_lookup": "Reading",
}


@dataclass
class LogEntry:
    stage: str
    message: str
    detail: Optional[str] = None
    elapsed: float = 0.0          # seconds since agent start

    def __str__(self) -> str:
        icon = STAGE_ICONS.get(self.stage, "•")
        base = f"[{self.stage:12s}] {icon}  {self.message}"
        if self.detail:
            base += f"\n              ↳ {self.detail}"
        return base


class ReasoningLogger:
    """
    Collects structured log entries throughout the agent run.
    Supports an optional callback so Streamlit (or any UI) can react
    in real-time without coupling to the agent core.
    """

    def __init__(self, on_entry: Optional[Callable[[LogEntry], None]] = None):
        self.entries: list[LogEntry] = []
        self._start = time.time()
        self._on_entry = on_entry   # optional real-time callback

    def _elapsed(self) -> float:
        return round(time.time() - self._start, 2)

    def log(self, stage: str, message: str, detail: str = None) -> LogEntry:
        entry = LogEntry(
            stage=stage,
            message=message,
            detail=detail,
            elapsed=self._elapsed(),
        )
        self.entries.append(entry)
        if self._on_entry:
            self._on_entry(entry)
        return entry

    # Convenience helpers — keep call sites clean
    def planning(self, msg: str, detail: str = None):
        return self.log("Planning", msg, detail)

    def searching(self, msg: str, detail: str = None):
        return self.log("Searching", msg, detail)

    def reading(self, msg: str, detail: str = None):
        return self.log("Reading", msg, detail)

    def summarizing(self, msg: str, detail: str = None):
        return self.log("Summarizing", msg, detail)

    def done(self, msg: str, detail: str = None):
        return self.log("Done", msg, detail)

    def error(self, msg: str, detail: str = None):
        return self.log("Error", msg, detail)

    def for_tool(self, tool_name: str, msg: str, detail: str = None):
        """Auto-select the right stage based on which tool fired."""
        stage = TOOL_TO_STAGE.get(tool_name, "Searching")
        return self.log(stage, msg, detail)

    def to_text(self) -> str:
        """Full plain-text dump of the log (for CLI output)."""
        lines = []
        for e in self.entries:
            ts = f"+{e.elapsed:6.2f}s"
            icon = STAGE_ICONS.get(e.stage, "•")
            lines.append(f"{ts}  [{e.stage:12s}] {icon}  {e.message}")
            if e.detail:
                lines.append(f"         ↳ {e.detail}")
        return "\n".join(lines)

    def stage_summary(self) -> list[dict]:
        """Return a compact list of {stage, message} for Streamlit display."""
        return [{"stage": e.stage, "message": e.message, "elapsed": e.elapsed}
                for e in self.entries]
