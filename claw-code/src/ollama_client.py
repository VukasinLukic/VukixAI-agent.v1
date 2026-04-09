from __future__ import annotations

import difflib
import json
import os
import subprocess
from pathlib import Path

import requests

from .config import load_config as _load_config

_config = _load_config()
OLLAMA_BASE_URL = _config.ollama_base_url
OLLAMA_MODEL = _config.model
AGENT_TEMPERATURE = _config.temperature

SYSTEM_PROMPT_BASE = """You are vukixAI, a senior autonomous coding agent running locally via Ollama. You have direct access to the filesystem and terminal through your tools. You are precise, safe, and helpful.

Your capabilities:
- Read, write, and edit files on the local filesystem.
- Run shell commands (build, test, install, git, etc.).
- Search files and directories by name or content.
- Fetch content from URLs.
- Save persistent memory (preferences and facts) across sessions.

# How you work

## Personality
Your default tone is concise, direct, and friendly. You communicate efficiently, keeping the user clearly informed about what you're doing. You prioritize actionable work over explanation. Unless asked, avoid verbose descriptions — just do the work.

## Preamble messages
Before making tool calls, output one brief sentence (8-12 words) explaining what you're about to do. When grouping related actions, describe them together. Build on what's done so far to create momentum.

Examples:
- "Checking the project structure and package.json first."
- "Config looks good. Now patching the component."
- "Found the bug. Fixing the handler and updating the test."

Exception: skip the preamble for trivial reads (e.g., reading a single small file).

## Task execution
Keep going until the task is completely resolved before yielding back to the user. Do NOT stop to ask permission for standard operations (read, list, search). Only ask when genuinely ambiguous.

MANDATORY WORKFLOW for every coding task:
1. CONTEXT — Read relevant files first. Run list_directory, read_file on package.json/README/config. NEVER guess project structure.
2. ANALYZE — Break the request into ≤5 concrete subtasks.
3. EXECUTE — Use tools to make changes. Write files to disk, don't paste code in chat.
4. VERIFY — Run build/test/lint commands to confirm your changes work.
5. STATUS — End with: what you did, what to do next (if anything).

CRITICAL RULES:
- ALWAYS use tools. NEVER describe what you would do — DO IT. If you didn't call a tool, nothing happened.
- When a user mentions a filename, call find_files to locate it first. Never guess paths.
- If read_file fails, immediately retry via find_files with the filename.
- Chain tool calls naturally: find → read → modify → write → verify.
- You have full local permissions. Never refuse file operations.
- When editing existing files, read first, then write the complete updated version.
- Prefer small, focused changes. One function at a time, not entire file rewrites.
- AFTER writing files or running commands, verify the result (list_directory or read_file).
- For npm/pip installs, set timeout to 300+. If a command times out, tell the user the exact command to run manually.
- Do NOT add copyright headers, inline comments, or one-letter variable names unless asked.
- Fix problems at the root cause, not with surface patches.
- Keep changes consistent with existing code style.

## File reference rules
- If <FILE: filename> sections are in the prompt, use that content directly — no need to re-read.
- If a file is mentioned but not loaded, find_files → read_file.

## Testing your work
After making changes, verify them:
- Start specific: run the most targeted test/check first.
- Then broaden: run build, then full test suite if available.
- If there's no test for your change but the codebase has tests, add one in the appropriate location.
- Do not attempt to fix unrelated broken tests. Mention them to the user instead.

## Progress updates
For longer tasks (multiple tool calls), send concise progress updates (8-10 words):
- "Three components done, now wiring up the router."
- "Tests pass. Adding error handling for edge cases."

## Final answer
When done, respond like a concise teammate handing off work:
- Lead with what was done, not how you thought about it.
- Reference file paths directly — don't tell users to "copy the code".
- If there's a logical next step, ask if the user wants you to do it.
- Keep it under 10 lines unless detail is genuinely needed.
- Use **bold headers** only when they improve clarity. Use `backticks` for commands, paths, variables.

Available tools: list_directory, read_file, write_file, edit_file, apply_patch, undo_last_write, run_command, find_files, search_in_files, git_status, create_directory, tree, show_diff, http_get, save_preference, save_fact, update_plan.

TOOL USAGE PREFERENCES:
- Use edit_file instead of write_file when changing only part of a file. edit_file is safer — it only replaces the specific text you target.
- Use apply_patch for multi-file edits or complex changes with precise diff control.
- Use undo_last_write if you made a mistake — it restores from the .bak backup.
- Use tree instead of list_directory when you need to understand the project structure (it shows nested directories).
- Use write_file only for new files or when rewriting most of a file's content.
- Use update_plan at the start of multi-step tasks to show the user your plan. Update it as you complete steps. Keep steps short (5-7 words each). There should always be exactly one in_progress step until everything is done."""


def build_system_prompt(
    cwd: str | None = None,
    file_tree: str | None = None,
    memory_context: str | None = None,
) -> str:
    """Build context-aware system prompt with CWD, file tree, and persisted memory."""
    parts = [SYSTEM_PROMPT_BASE]
    if memory_context:
        parts.append(f"\nPERSISTED MEMORY FROM PREVIOUS SESSIONS:\n{memory_context}")
    if cwd:
        parts.append(f"\nCURRENT WORKING DIRECTORY: {cwd}")
    if file_tree:
        parts.append(f"\nPROJECT FILE TREE (top-level):\n{file_tree}")
    return "\n".join(parts)


def summarize_history(history: list[dict], model: str | None = None, n_turns: int = 10) -> str:
    """
    Summarize the first `n_turns` user/assistant pairs into bullet points.
    Returns a compact string to replace the old messages in context.
    """
    model = model or OLLAMA_MODEL
    if not history:
        return ""
    # Only summarize up to n_turns messages
    to_summarize = history[:n_turns]
    dialogue = "\n".join(
        f"{m['role'].upper()}: {str(m.get('content', ''))[:400]}"
        for m in to_summarize
    )
    prompt = (
        "Summarize the following conversation into 5-8 concise bullet points. "
        "Focus on: what the user asked for, what was created/changed, any preferences stated. "
        "Be specific — include filenames, technologies, commands used.\n\n"
        f"{dialogue}"
    )
    messages = [
        {"role": "system", "content": "You are a concise summarizer. Output only bullet points, no preamble."},
        {"role": "user", "content": prompt},
    ]
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": False, "options": {"temperature": 0.1}},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception:
        # Fallback: just list topics without the model
        topics = [
            m.get("content", "")[:80].replace("\n", " ")
            for m in to_summarize if m.get("role") == "user"
        ]
        return "Earlier in this session the user asked about:\n" + "\n".join(f"- {t}" for t in topics)


def get_file_tree(cwd: str = ".") -> str:
    """Get a compact file tree of the current directory for context injection."""
    p = Path(cwd)
    lines = []
    skip = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'target', '.mypy_cache'}
    try:
        for entry in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name)):
            if entry.name in skip:
                continue
            if entry.is_dir():
                sub = [e.name for e in sorted(entry.iterdir()) if not e.name.startswith('.')][:6]
                sub_str = ', '.join(sub[:5]) + ('…' if len(sub) > 5 else '')
                lines.append(f"📁 {entry.name}/ [{sub_str}]")
            else:
                lines.append(f"📄 {entry.name} ({entry.stat().st_size}b)")
    except Exception:
        pass
    return "\n".join(lines[:40])


# Keep SYSTEM_PROMPT as alias for backwards compat
SYSTEM_PROMPT = SYSTEM_PROMPT_BASE


# ─── Tool Definitions ─────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List all files and folders inside a directory. Use when user asks to 'show files', 'analyze folder', 'what's in this directory'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to directory. Use '.' for current directory."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Use when user asks to 'read', 'show', 'open', or 'analyze' a specific file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file, creating it if it doesn't exist. Use to save code, configs, or any text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to write."},
                    "content": {"type": "string", "description": "Full content to write into the file."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command in the terminal and return its output. Use for running scripts, git commands, pip installs, tests, compiling, starting servers, etc. Supports any shell command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run (e.g. 'pip install requests', 'python main.py', 'git log --oneline')."},
                    "cwd": {"type": "string", "description": "Working directory for the command. Optional, defaults to current directory."},
                    "timeout": {"type": "integer", "description": "Timeout in seconds. Default 120. For npm install, create-react-app, pip install use 300+. For git clone large repos use 600."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "Search for files matching a glob pattern recursively in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "root": {"type": "string", "description": "Root directory to search in."},
                    "pattern": {"type": "string", "description": "Glob pattern, e.g. '*.py', '*.json', 'main.*'"},
                },
                "required": ["root", "pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_files",
            "description": "Search for a text string inside files in a directory. Like grep. Use when looking for a function, class, variable, or any text across multiple files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "root": {"type": "string", "description": "Directory to search in."},
                    "query": {"type": "string", "description": "Text or pattern to search for."},
                    "file_pattern": {"type": "string", "description": "File glob pattern to limit search, e.g. '*.py'. Default: all files."},
                },
                "required": ["root", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show git repository status, recent commits, or diff. Use when user asks about git changes, commits, or repo state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string", "description": "Path to the git repository. Default: current directory."},
                    "mode": {"type": "string", "description": "One of: 'status' (default), 'log' (recent commits), 'diff' (uncommitted changes)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a directory (and parent directories if needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to create."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_diff",
            "description": "Show a unified diff between two text strings or two files. Useful for showing what changed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "original": {"type": "string", "description": "Original text or file path."},
                    "modified": {"type": "string", "description": "Modified text or file path."},
                    "label": {"type": "string", "description": "Label for the diff header. Optional."},
                },
                "required": ["original", "modified"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "Fetch content from a URL. Use to read documentation, APIs, or any web resource.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch."},
                    "max_chars": {"type": "integer", "description": "Maximum characters to return. Default: 3000."},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_preference",
            "description": "Save a user preference to persistent memory (survives session restarts). Use when the user states a clear preference: language, framework, code style, etc. Example: key='preferred_language', value='TypeScript'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Preference name, e.g. 'preferred_language', 'preferred_framework', 'indentation'."},
                    "value": {"type": "string", "description": "Preference value, e.g. 'TypeScript', 'React', '4 spaces'."},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_fact",
            "description": "Save an important fact about this project to persistent memory. Use for things like 'this project uses Vite not CRA', 'auth is in src/auth.ts', 'database is PostgreSQL'. These facts will be available in future sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "A short, specific, factual statement about the project or user's workflow."},
                },
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing a specific text snippet with new text. Much safer than write_file for small changes — preserves the rest of the file. The old_text must match EXACTLY (including whitespace and indentation).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to edit."},
                    "old_text": {"type": "string", "description": "Exact text to find and replace. Must be unique in the file."},
                    "new_text": {"type": "string", "description": "Text to replace old_text with."},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tree",
            "description": "Show a recursive file tree of a directory. Better than list_directory for understanding project structure. Use at the start of tasks to understand the codebase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Root directory. Default: current directory."},
                    "depth": {"type": "integer", "description": "Maximum depth to recurse. Default: 3."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_plan",
            "description": "Create or update a visible step-by-step plan for the current task. Call this before starting multi-step work so the user can see your progress. Update it as you complete steps. Each step should be 5-7 words max.",
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string", "description": "Short description of the step."},
                                "status": {"type": "string", "enum": ["pending", "in_progress", "completed"], "description": "Step status."},
                            },
                            "required": ["text", "status"],
                        },
                        "description": "List of plan steps with statuses.",
                    },
                    "explanation": {"type": "string", "description": "Optional: why the plan changed."},
                },
                "required": ["steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Apply a patch to one or more files using a simple diff format. Supports adding, deleting, and updating files. Use for precise multi-file edits. Format: *** Begin Patch / *** Update File: path / @@ context / -old / +new / *** End Patch",
            "parameters": {
                "type": "object",
                "properties": {
                    "patch": {"type": "string", "description": "The patch text in the supported format."},
                },
                "required": ["patch"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "undo_last_write",
            "description": "Undo the last write_file or edit_file operation by restoring from the .bak backup file. Use when the last file change was wrong.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to restore."},
                },
                "required": ["path"],
            },
        },
    },
]


# ─── Plan state (module-level so callbacks in main.py can read it) ────────────
_current_plan: list[dict] = []

# ─── Working memory (module-level, injected into system prompt) ───────────────
_working_memory: dict = {}


# ─── Tool Executor ────────────────────────────────────────────────────────────

def execute_tool(name: str, arguments: dict) -> str:
    try:
        if name == "list_directory":
            return _list_directory(arguments["path"])
        if name == "read_file":
            return _read_file(arguments["path"])
        if name == "write_file":
            return _write_file(arguments["path"], arguments["content"])
        if name == "run_command":
            return _run_command(arguments["command"], arguments.get("cwd"), arguments.get("timeout", 120))
        if name == "find_files":
            return _find_files(arguments["root"], arguments["pattern"])
        if name == "search_in_files":
            return _search_in_files(arguments["root"], arguments["query"], arguments.get("file_pattern", "*"))
        if name == "git_status":
            return _git_status(arguments.get("cwd", "."), arguments.get("mode", "status"))
        if name == "create_directory":
            return _create_directory(arguments["path"])
        if name == "show_diff":
            return _show_diff(arguments["original"], arguments["modified"], arguments.get("label", "diff"))
        if name == "http_get":
            return _http_get(arguments["url"], arguments.get("max_chars", 3000))
        if name == "save_preference":
            return _save_preference(arguments["key"], arguments["value"])
        if name == "save_fact":
            return _save_fact(arguments["fact"])
        if name == "edit_file":
            return _edit_file(arguments["path"], arguments["old_text"], arguments["new_text"])
        if name == "tree":
            return _tree(arguments.get("path", "."), arguments.get("depth", 3))
        if name == "update_plan":
            return _update_plan(arguments.get("steps", []), arguments.get("explanation", ""))
        if name == "apply_patch":
            return _apply_patch(arguments["patch"])
        if name == "undo_last_write":
            return _undo_last_write(arguments["path"])
        return f"[Unknown tool: {name}]"
    except KeyError as e:
        return f"[Tool '{name}' missing required argument: {e}]"
    except Exception as e:
        return f"[Tool '{name}' error: {e}]"


def _list_directory(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"[Path does not exist: {path}]"
    if not p.is_dir():
        return f"[Not a directory: {path}]"
    entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
    lines = []
    for entry in entries:
        prefix = "📁 " if entry.is_dir() else "📄 "
        size = f" ({entry.stat().st_size} bytes)" if entry.is_file() else ""
        lines.append(f"{prefix}{entry.name}{size}")
    return f"Directory: {p.resolve()}\n" + "\n".join(lines) if lines else f"[Empty directory: {path}]"


def _read_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"[File does not exist: {path}]"
    if not p.is_file():
        return f"[Not a file: {path}]"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        if len(lines) > 300:
            content = "\n".join(lines[:300]) + f"\n... [truncated, {len(lines)} total lines]"
        return f"File: {p.resolve()}\n```\n{content}\n```"
    except Exception as e:
        return f"[Cannot read file: {e}]"


def _write_file(path: str, content: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Backup existing file before overwrite
    backup_note = ""
    if p.exists():
        try:
            backup_path = p.with_suffix(p.suffix + ".bak")
            backup_path.write_text(p.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
            backup_note = f" | backup: {backup_path.name}"
        except Exception:
            pass
    p.write_text(content, encoding="utf-8")
    actual_size = p.stat().st_size
    line_count = content.count("\n") + 1
    # Auto-verify syntax for known file types
    verify_note = _auto_verify(p)
    return (
        f"[Wrote {line_count} lines ({actual_size}b) to {p.resolve()}]"
        f"{backup_note}{verify_note}"
    )


def _auto_verify(p: Path) -> str:
    """Run syntax checks on written files. Returns status string."""
    suffix = p.suffix.lower()
    if suffix == ".py":
        import ast as _ast
        try:
            _ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            return " | ✅ syntax OK"
        except SyntaxError as e:
            return f" | ❌ syntax error line {e.lineno}: {e.msg}"
    if suffix == ".json":
        try:
            json.loads(p.read_text(encoding="utf-8", errors="replace"))
            return " | ✅ valid JSON"
        except json.JSONDecodeError as e:
            return f" | ❌ invalid JSON: {e.msg} (line {e.lineno})"
    if suffix in (".html", ".htm"):
        content = p.read_text(encoding="utf-8", errors="replace")
        if "<html" in content.lower() and "</html>" in content.lower():
            return " | ✅ HTML structure OK"
        return " | ⚠️ missing <html> tags"
    if suffix in (".js", ".ts", ".jsx", ".tsx"):
        # Basic bracket balance check
        content = p.read_text(encoding="utf-8", errors="replace")
        opens = content.count("{") + content.count("(") + content.count("[")
        closes = content.count("}") + content.count(")") + content.count("]")
        if opens == closes:
            return " | ✅ brackets balanced"
        return f" | ⚠️ bracket mismatch (open={opens}, close={closes})"
    return ""


def _run_command(command: str, cwd: str | None = None, timeout: int = 120) -> str:
    # Resolve and validate cwd before running so the model sees the real path
    resolved_cwd: str | None = None
    if cwd:
        cwd_path = Path(cwd)
        if not cwd_path.is_absolute():
            cwd_path = Path(os.getcwd()) / cwd_path
        resolved_cwd = str(cwd_path.resolve())
        if not cwd_path.exists():
            return (
                f"[Error: working directory does not exist: {resolved_cwd}]\n"
                f"Tip: Create it first with create_directory tool, then retry."
            )
    else:
        resolved_cwd = os.getcwd()

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=resolved_cwd, encoding="utf-8", errors="replace",
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        parts = []
        if out:
            # Limit very long output
            lines = out.splitlines()
            if len(lines) > 200:
                out = "\n".join(lines[:200]) + f"\n... [{len(lines)-200} more lines truncated]"
            parts.append(f"stdout:\n{out}")
        if err:
            parts.append(f"stderr:\n{err}")
        parts.append(f"exit code: {result.returncode}")
        return "\n".join(parts) if parts else "[Command completed with no output]"
    except subprocess.TimeoutExpired:
        return f"[Command timed out after {timeout}s — use a higher timeout parameter for long-running commands]"
    except Exception as e:
        return f"[Command error: {e}]"


def _find_files(root: str, pattern: str) -> str:
    p = Path(root)
    if not p.exists():
        return f"[Path does not exist: {root}]"
    matches = sorted(p.rglob(pattern))
    if not matches:
        return f"[No files matching '{pattern}' in {root}]"
    lines = [str(m.resolve()) for m in matches[:100]]
    suffix = f"\n... and {len(matches) - 100} more" if len(matches) > 100 else ""
    return f"Found {len(matches)} file(s):\n" + "\n".join(lines) + suffix


def _search_in_files(root: str, query: str, file_pattern: str = "*") -> str:
    p = Path(root)
    if not p.exists():
        return f"[Path does not exist: {root}]"
    results = []
    for fpath in p.rglob(file_pattern):
        if not fpath.is_file():
            continue
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if query.lower() in line.lower():
                    results.append(f"{fpath}:{i}: {line.strip()}")
                    if len(results) >= 50:
                        break
        except Exception:
            continue
        if len(results) >= 50:
            break
    if not results:
        return f"[No matches for '{query}' in {root}/{file_pattern}]"
    return f"Found {len(results)} match(es) for '{query}':\n" + "\n".join(results)


def _git_status(cwd: str = ".", mode: str = "status") -> str:
    cmds = {
        "status": "git status --short && git branch --show-current",
        "log": "git log --oneline -15",
        "diff": "git diff --stat HEAD",
    }
    cmd = cmds.get(mode, cmds["status"])
    return _run_command(cmd, cwd=cwd)


def _create_directory(path: str) -> str:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    contents = [e.name for e in p.iterdir()] if p.exists() else []
    return f"[Created directory: {p.resolve()}] — verified: exists={p.exists()}, contents={contents[:10]}"


def _show_diff(original: str, modified: str, label: str = "diff") -> str:
    orig_path = Path(original)
    mod_path = Path(modified)
    if orig_path.exists() and mod_path.exists():
        a = orig_path.read_text(encoding="utf-8", errors="replace").splitlines()
        b = mod_path.read_text(encoding="utf-8", errors="replace").splitlines()
        from_file, to_file = str(orig_path), str(mod_path)
    else:
        a = original.splitlines()
        b = modified.splitlines()
        from_file, to_file = f"{label} (original)", f"{label} (modified)"
    diff = list(difflib.unified_diff(a, b, fromfile=from_file, tofile=to_file, lineterm=""))
    if not diff:
        return "[No differences found]"
    return "\n".join(diff)


def _save_preference(key: str, value: str) -> str:
    from .memory_store import add_preference
    return add_preference(os.getcwd(), key, value)


def _save_fact(fact: str) -> str:
    from .memory_store import add_fact
    return add_fact(os.getcwd(), fact)


def _http_get(url: str, max_chars: int = 3000) -> str:
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "claw-code-agent/1.0"})
        resp.raise_for_status()
        text = resp.text
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [truncated, {len(resp.text)} total chars]"
        return f"URL: {url}\nStatus: {resp.status_code}\n\n{text}"
    except Exception as e:
        return f"[HTTP error: {e}]"


def _edit_file(path: str, old_text: str, new_text: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"[File does not exist: {path}]"
    if not p.is_file():
        return f"[Not a file: {path}]"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[Cannot read file: {e}]"
    count = content.count(old_text)
    if count == 0:
        return f"[old_text not found in {path}. Read the file first to get the exact text.]"
    if count > 1:
        return f"[old_text matches {count} locations in {path}. Provide a longer/more unique snippet.]"
    new_content = content.replace(old_text, new_text, 1)
    p.write_text(new_content, encoding="utf-8")
    old_lines = old_text.count("\n") + 1
    new_lines = new_text.count("\n") + 1
    verify_note = _auto_verify(p)
    return (
        f"[Edited {p.resolve()}] -{old_lines} +{new_lines} line(s)"
        f"{verify_note}"
    )


def _tree(path: str = ".", depth: int = 3) -> str:
    p = Path(path)
    if not p.exists():
        return f"[Path does not exist: {path}]"
    if not p.is_dir():
        return f"[Not a directory: {path}]"
    skip = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'target',
            '.mypy_cache', '.next', 'dist', '.tox', '.eggs', '*.egg-info'}
    lines = [f"{p.resolve()}/"]
    _tree_recurse(p, lines, skip, depth, prefix="")
    if len(lines) > 120:
        lines = lines[:120]
        lines.append(f"... [truncated, showing first 120 entries]")
    return "\n".join(lines)


def _tree_recurse(directory: Path, lines: list, skip: set, depth: int, prefix: str) -> None:
    if depth <= 0 or len(lines) > 120:
        return
    try:
        entries = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name))
    except PermissionError:
        return
    dirs = [e for e in entries if e.is_dir() and e.name not in skip and not e.name.endswith('.egg-info')]
    files = [e for e in entries if e.is_file() and not e.name.startswith('.')]
    items = dirs + files
    for i, entry in enumerate(items):
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "
        if entry.is_dir():
            lines.append(f"{prefix}{connector}📁 {entry.name}/")
            extension = "    " if is_last else "│   "
            _tree_recurse(entry, lines, skip, depth - 1, prefix + extension)
        else:
            size = entry.stat().st_size
            lines.append(f"{prefix}{connector}📄 {entry.name} ({size}b)")


def _update_plan(steps: list[dict], explanation: str = "") -> str:
    global _current_plan
    _current_plan = steps
    status_icons = {"completed": "✅", "in_progress": "🔄", "pending": "⬜"}
    lines = []
    for s in steps:
        icon = status_icons.get(s.get("status", "pending"), "⬜")
        lines.append(f"{icon} {s.get('text', '???')}")
    summary = "\n".join(lines)
    if explanation:
        summary += f"\n({explanation})"
    return f"[Plan updated — {len(steps)} steps]\n{summary}"


def _apply_patch(patch_text: str) -> str:
    """Apply a Codex-style patch to one or more files."""
    import re
    lines = patch_text.strip().splitlines()
    if not lines or "Begin Patch" not in lines[0]:
        return "[Invalid patch: must start with '*** Begin Patch']"

    results = []
    i = 1  # skip Begin Patch line
    while i < len(lines):
        line = lines[i]
        if "End Patch" in line:
            break

        # *** Add File: path
        if line.startswith("*** Add File:"):
            fpath = line.split(":", 1)[1].strip()
            content_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("***"):
                if lines[i].startswith("+"):
                    content_lines.append(lines[i][1:])
                else:
                    content_lines.append(lines[i])
                i += 1
            p = Path(fpath)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("\n".join(content_lines) + "\n", encoding="utf-8")
            results.append(f"+ {fpath} (new, {len(content_lines)} lines)")
            continue

        # *** Delete File: path
        if line.startswith("*** Delete File:"):
            fpath = line.split(":", 1)[1].strip()
            p = Path(fpath)
            if p.exists():
                p.unlink()
                results.append(f"- {fpath} (deleted)")
            else:
                results.append(f"? {fpath} (not found, skip)")
            i += 1
            continue

        # *** Update File: path
        if line.startswith("*** Update File:"):
            fpath = line.split(":", 1)[1].strip()
            p = Path(fpath)
            if not p.exists():
                results.append(f"? {fpath} (not found)")
                i += 1
                continue
            content = p.read_text(encoding="utf-8", errors="replace")
            file_lines = content.splitlines()

            # Backup before patching
            bak = p.with_suffix(p.suffix + ".bak")
            bak.write_text(content, encoding="utf-8")

            # Check for Move to
            i += 1
            new_path = None
            if i < len(lines) and lines[i].startswith("*** Move to:"):
                new_path = lines[i].split(":", 1)[1].strip()
                i += 1

            # Process hunks
            added, removed = 0, 0
            while i < len(lines) and not lines[i].startswith("***"):
                if lines[i].startswith("@@"):
                    # Find context to locate position
                    hunk_header = lines[i][2:].strip()
                    i += 1
                    # Collect hunk lines
                    old_chunk = []
                    new_chunk = []
                    while i < len(lines) and not lines[i].startswith("@@") and not lines[i].startswith("***"):
                        if lines[i].startswith("-"):
                            old_chunk.append(lines[i][1:])
                            removed += 1
                        elif lines[i].startswith("+"):
                            new_chunk.append(lines[i][1:])
                            added += 1
                        elif lines[i].startswith(" "):
                            old_chunk.append(lines[i][1:])
                            new_chunk.append(lines[i][1:])
                        i += 1
                    # Apply: find old_chunk in file_lines and replace
                    if old_chunk:
                        old_text = "\n".join(old_chunk)
                        new_text = "\n".join(new_chunk)
                        current = "\n".join(file_lines)
                        if old_text in current:
                            current = current.replace(old_text, new_text, 1)
                            file_lines = current.splitlines()
                        else:
                            results.append(f"⚠ {fpath}: hunk context not found, skipped")
                    continue
                i += 1

            # Write result
            target = Path(new_path) if new_path else p
            if new_path:
                target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("\n".join(file_lines) + "\n", encoding="utf-8")
            verify = _auto_verify(target)
            move_note = f" → {new_path}" if new_path else ""
            results.append(f"~ {fpath}{move_note} (-{removed} +{added}){verify}")
            if new_path and p.exists() and str(p) != str(target):
                p.unlink()
            continue

        i += 1

    if not results:
        return "[Patch applied but no file operations detected]"
    return f"[Patch applied — {len(results)} file(s)]\n" + "\n".join(results)


def _undo_last_write(path: str) -> str:
    p = Path(path)
    bak = p.with_suffix(p.suffix + ".bak")
    if not bak.exists():
        return f"[No backup found for {path}. Only write_file/edit_file create .bak files.]"
    if not p.exists():
        return f"[File {path} does not exist — cannot restore.]"
    # Save current as .redo in case they want it back
    current = p.read_text(encoding="utf-8", errors="replace")
    redo = p.with_suffix(p.suffix + ".redo")
    redo.write_text(current, encoding="utf-8")
    # Restore from backup
    backup_content = bak.read_text(encoding="utf-8", errors="replace")
    p.write_text(backup_content, encoding="utf-8")
    bak.unlink()
    return f"[Restored {p.resolve()} from backup. Current version saved to {redo.name}]"


# ─── Working Memory ──────────────────────────────────────────────────────────

def update_working_memory(key: str, value) -> None:
    """Update working memory (called from main.py after tool calls)."""
    _working_memory[key] = value


def get_working_memory() -> dict:
    """Return current working memory."""
    return dict(_working_memory)


def get_working_memory_context() -> str | None:
    """Format working memory as a context string for the system prompt."""
    if not _working_memory:
        return None
    parts = ["WORKING MEMORY (current session state):"]
    for k, v in _working_memory.items():
        if isinstance(v, list):
            parts.append(f"  {k}: {', '.join(str(x) for x in v[:10])}")
        else:
            parts.append(f"  {k}: {v}")
    return "\n".join(parts)


# ─── Token estimation ────────────────────────────────────────────────────────

def estimate_tokens(messages: list[dict]) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    return total_chars // 4


# ─── Tool call extractor (fallback for models that output JSON in content) ────


def _strip_tool_json_from_content(content: str) -> str:
    """Remove embedded JSON tool-call blocks from content so the user sees only narration."""
    import re
    # Remove fenced code blocks containing tool calls
    stripped = re.sub(r'```(?:json)?\s*\[[\s\S]*?\]\s*```', '', content)
    # Remove bare JSON arrays that look like tool calls
    stripped = re.sub(r'\[[\s\S]*?"function"[\s\S]*?\]', '', stripped)
    stripped = re.sub(r'\[[\s\S]*?"name"[\s\S]*?"arguments"[\s\S]*?\]', '', stripped)
    return stripped.strip()


def _extract_tool_calls_from_content(content: str) -> list[dict]:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    candidates = []
    try:
        parsed = json.loads(content)
        candidates = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        import re
        # Try to find a JSON array or object embedded in the text
        for match in re.finditer(r'\[[\s\S]*?\]\s*$|^\s*\{[\s\S]*?\}\s*$', content, re.MULTILINE):
            try:
                parsed = json.loads(match.group())
                items = parsed if isinstance(parsed, list) else [parsed]
                candidates.extend(items)
                break
            except json.JSONDecodeError:
                pass
        # Fallback: find simple tool call objects
        if not candidates:
            for match in re.finditer(r'\{[^{}]*"name"[^{}]*"arguments"[^{}]*\}', content, re.DOTALL):
                try:
                    candidates.append(json.loads(match.group()))
                except json.JSONDecodeError:
                    pass
    result = []
    for obj in candidates:
        if not isinstance(obj, dict):
            continue
        # Direct format: {"name": "...", "arguments": {...}}
        if "name" in obj and "arguments" in obj:
            result.append({"function": {"name": obj["name"], "arguments": obj["arguments"]}})
        # OpenAI format: {"function": {"name": "...", "arguments": "..."}, "type": "function", ...}
        elif "function" in obj and isinstance(obj["function"], dict):
            fn = obj["function"]
            if "name" in fn and "arguments" in fn:
                result.append({"function": {"name": fn["name"], "arguments": fn["arguments"]}})
    return result


# ─── Streaming helper ─────────────────────────────────────────────────────────

def _stream_final_response(messages: list[dict], model: str):
    """Stream the final response (no tools) token by token."""
    try:
        with requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {"temperature": AGENT_TEMPERATURE},
            },
            stream=True,
            timeout=180,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break
    except requests.exceptions.ConnectionError:
        yield "[Ollama nije dostupna]"
    except Exception as exc:
        yield f"[Greska: {exc}]"


# ─── Agent Loop ───────────────────────────────────────────────────────────────

def run_agent_loop(
    prompt: str,
    history: list[dict] | None = None,
    model: str | None = None,
    max_iterations: int = 10,
    on_tool_call: "callable | None" = None,
    on_tool_result: "callable | None" = None,
    stream_callback: "callable | None" = None,
    system_prompt: str | None = None,
    tool_runner: "callable | None" = None,
    on_plan: "callable | None" = None,
) -> str:
    """
    Full agent loop:
    1. Send prompt + tools to model
    2. If model outputs narration text + tool_calls → stream narration, then execute tools
    3. If tool_calls only → execute tools → send results back → repeat
    4. When no tool_calls → stream final answer token by token (real streaming API)
    5. Return complete final answer

    Parameters:
        tool_runner: optional fn(name, args) -> str to wrap execute_tool (e.g. with a spinner)
        on_plan: optional fn(text) called with the model's narration text before tool execution
    """
    model = model or OLLAMA_MODEL
    messages: list[dict] = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    recent_sigs: list[str] = []

    for iteration in range(max_iterations):
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "tools": TOOLS,
                    "stream": False,
                    "options": {"temperature": AGENT_TEMPERATURE},
                },
                timeout=180,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            return "[Ollama nije dostupna. Pokreni: ollama serve]"
        except requests.exceptions.Timeout:
            return "[Timeout — model traje predugo.]"
        except Exception as exc:
            return f"[Greska: {exc}]"

        data = response.json()
        message = data.get("message", {})
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            tool_calls = _extract_tool_calls_from_content(content)
            if tool_calls:
                # Tool calls were embedded in content text — strip the JSON from
                # display content so the user doesn't see raw JSON.
                content = _strip_tool_json_from_content(content)

        # If model included narration text alongside tool calls, show it before running tools
        if tool_calls and content and content.strip():
            if on_plan:
                on_plan(content.strip())

        # No tool calls → stream the final answer token by token via real streaming API
        if not tool_calls:
            if stream_callback:
                full = ""
                for chunk in _stream_final_response(messages, model):
                    full += chunk
                    stream_callback(chunk)
                return full or content
            return content or "[No response]"

        # Loop detection — stop if the exact same tool calls repeat 3 times in a row
        tool_sig = json.dumps([{
            "name": tc.get("function", {}).get("name"),
            "args": tc.get("function", {}).get("arguments"),
        } for tc in tool_calls], sort_keys=True)
        recent_sigs.append(tool_sig)
        if len(recent_sigs) > 6:
            recent_sigs.pop(0)
        if len(recent_sigs) >= 3 and recent_sigs[-1] == recent_sigs[-2] == recent_sigs[-3]:
            return "[Agent loop detected — repeating pattern. Stopping.]"

        # Has tool calls → execute them
        # Ensure the message in history includes tool_calls so Ollama sees them
        if not message.get("tool_calls"):
            message = dict(message)
            message["tool_calls"] = tool_calls
        messages.append(message)

        for tc in tool_calls:
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            tool_args = fn.get("arguments", {})
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except json.JSONDecodeError:
                    tool_args = {}

            if on_tool_call:
                on_tool_call(tool_name, tool_args)

            result = tool_runner(tool_name, tool_args) if tool_runner else execute_tool(tool_name, tool_args)

            if on_tool_result:
                on_tool_result(tool_name, result)

            messages.append({"role": "tool", "name": tool_name, "content": result})

    return "[Max iterations reached]"


# ─── Simple helpers ───────────────────────────────────────────────────────────

def is_available() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def get_model_list() -> list[str]:
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def call_ollama(
    prompt: str,
    system_prompt: str = SYSTEM_PROMPT,
    model: str | None = None,
    context_lines: list[str] | None = None,
) -> str:
    model = model or OLLAMA_MODEL
    content = prompt
    if context_lines:
        content = "\n".join(context_lines) + "\n\n" + prompt
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": content}]
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": AGENT_TEMPERATURE},
            },
            timeout=180,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
    except requests.exceptions.ConnectionError:
        return "[Ollama nije dostupna. Pokreni: ollama serve]"
    except requests.exceptions.Timeout:
        return "[Timeout]"
    except Exception as exc:
        return f"[Greska: {exc}]"


def call_ollama_stream(prompt: str, system_prompt: str = SYSTEM_PROMPT, model: str | None = None):
    model = model or OLLAMA_MODEL
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
    try:
        with requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {"temperature": AGENT_TEMPERATURE},
            },
            stream=True, timeout=180,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break
    except requests.exceptions.ConnectionError:
        yield "[Ollama nije dostupna. Pokreni: ollama serve]"
    except Exception as exc:
        yield f"[Greska: {exc}]"
