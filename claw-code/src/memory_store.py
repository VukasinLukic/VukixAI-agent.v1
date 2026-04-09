from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MEMORY_FILENAME = ".agent_memory.json"
# Kept short so model context stays lean: max turns persisted to disk
MAX_HISTORY_PERSIST = 30


@dataclass
class AgentMemory:
    """Per-project persistent memory for the agent."""
    history: list[dict] = field(default_factory=list)
    preferences: dict[str, str] = field(default_factory=dict)
    facts: list[str] = field(default_factory=list)
    project_path: str = ""

    def to_dict(self) -> dict:
        return {
            "history": self.history,
            "preferences": self.preferences,
            "facts": self.facts,
            "project_path": self.project_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentMemory":
        return cls(
            history=data.get("history", []),
            preferences=data.get("preferences", {}),
            facts=data.get("facts", []),
            project_path=data.get("project_path", ""),
        )

    def as_context_block(self) -> str | None:
        """Return a compact context string to inject into the system prompt."""
        lines = []
        if self.preferences:
            lines.append("User preferences:")
            for k, v in self.preferences.items():
                lines.append(f"  - {k}: {v}")
        if self.facts:
            lines.append("Known facts about this project:")
            for f in self.facts[-10:]:  # last 10 facts max
                lines.append(f"  - {f}")
        return "\n".join(lines) if lines else None


def load_memory(project_dir: str) -> AgentMemory:
    """Load memory from project directory. Returns empty AgentMemory if not found."""
    path = Path(project_dir) / MEMORY_FILENAME
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return AgentMemory.from_dict(data)
        except Exception:
            pass
    return AgentMemory(project_path=str(Path(project_dir).resolve()))


def save_memory(memory: AgentMemory, project_dir: str) -> None:
    """Save memory to project directory."""
    path = Path(project_dir) / MEMORY_FILENAME
    # Only persist the most recent turns to keep file size sane
    trimmed = AgentMemory(
        history=memory.history[-MAX_HISTORY_PERSIST:],
        preferences=memory.preferences,
        facts=memory.facts,
        project_path=memory.project_path,
    )
    path.write_text(
        json.dumps(trimmed.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def add_preference(project_dir: str, key: str, value: str) -> str:
    """Add or update a user preference. Called by the save_preference tool."""
    mem = load_memory(project_dir)
    mem.preferences[key] = value
    save_memory(mem, project_dir)
    return f"[Saved preference: {key!r} = {value!r}]"


def add_fact(project_dir: str, fact: str) -> str:
    """Add a project fact. Called by the save_fact tool."""
    mem = load_memory(project_dir)
    if fact not in mem.facts:
        mem.facts.append(fact)
        save_memory(mem, project_dir)
        return f"[Saved fact: {fact!r}]"
    return f"[Fact already known: {fact!r}]"
