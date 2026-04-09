"""
vukixAI configuration system.

Config is loaded from (in order of priority, later wins):
1. Built-in defaults
2. Global config: ~/.vukixai/config.json
3. Project config: .vukixai.json in the project root
4. Environment variables (OLLAMA_MODEL, AGENT_TEMPERATURE, etc.)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILENAME = ".vukixai.json"
GLOBAL_CONFIG_DIR = Path.home() / ".vukixai"
GLOBAL_CONFIG_PATH = GLOBAL_CONFIG_DIR / "config.json"

DEFAULTS = {
    "model": "qwen3-coder:30b",
    "temperature": 0.15,
    "max_iterations": 15,
    "ollama_base_url": "http://localhost:11434",
    "auto_verify": True,
    "show_thinking": True,
    "result_preview_lines": 4,
    "result_preview_chars": 200,
    "max_history_persist": 30,
    "history_summarize_threshold": 20,
}


@dataclass
class AgentConfig:
    model: str = DEFAULTS["model"]
    temperature: float = DEFAULTS["temperature"]
    max_iterations: int = DEFAULTS["max_iterations"]
    ollama_base_url: str = DEFAULTS["ollama_base_url"]
    auto_verify: bool = DEFAULTS["auto_verify"]
    show_thinking: bool = DEFAULTS["show_thinking"]
    result_preview_lines: int = DEFAULTS["result_preview_lines"]
    result_preview_chars: int = DEFAULTS["result_preview_chars"]
    max_history_persist: int = DEFAULTS["max_history_persist"]
    history_summarize_threshold: int = DEFAULTS["history_summarize_threshold"]
    _source: str = "defaults"

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def apply_dict(self, data: dict) -> None:
        for key, value in data.items():
            if hasattr(self, key) and not key.startswith("_"):
                expected_type = type(getattr(self, key))
                try:
                    setattr(self, key, expected_type(value))
                except (ValueError, TypeError):
                    pass

    def apply_env(self) -> None:
        env_map = {
            "OLLAMA_MODEL": "model",
            "AGENT_TEMPERATURE": "temperature",
            "OLLAMA_BASE_URL": "ollama_base_url",
            "MAX_ITERATIONS": "max_iterations",
        }
        for env_key, config_key in env_map.items():
            val = os.environ.get(env_key)
            if val is not None:
                expected_type = type(getattr(self, config_key))
                try:
                    setattr(self, config_key, expected_type(val))
                except (ValueError, TypeError):
                    pass


def load_config(project_dir: str | None = None) -> AgentConfig:
    """Load config with priority: defaults < global < project < env."""
    config = AgentConfig()

    # Global config
    if GLOBAL_CONFIG_PATH.exists():
        try:
            data = json.loads(GLOBAL_CONFIG_PATH.read_text(encoding="utf-8"))
            config.apply_dict(data)
            config._source = "global"
        except Exception:
            pass

    # Project config
    if project_dir:
        project_config = Path(project_dir) / CONFIG_FILENAME
        if project_config.exists():
            try:
                data = json.loads(project_config.read_text(encoding="utf-8"))
                config.apply_dict(data)
                config._source = "project"
            except Exception:
                pass

    # Environment overrides
    config.apply_env()

    return config


def save_project_config(config: AgentConfig, project_dir: str) -> str:
    """Save current config as project-level .vukixai.json."""
    path = Path(project_dir) / CONFIG_FILENAME
    path.write_text(
        json.dumps(config.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(path)


def save_global_config(config: AgentConfig) -> str:
    """Save current config as global ~/.vukixai/config.json."""
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    GLOBAL_CONFIG_PATH.write_text(
        json.dumps(config.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(GLOBAL_CONFIG_PATH)
