from __future__ import annotations

import argparse
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[attr-defined]

from .bootstrap_graph import build_bootstrap_graph
from .command_graph import build_command_graph
from .commands import execute_command, get_command, get_commands, render_command_index
from .direct_modes import run_deep_link, run_direct_connect
from .parity_audit import run_parity_audit
from .permissions import ToolPermissionContext
from .port_manifest import build_port_manifest
from .query_engine import QueryEnginePort
from .ollama_client import TOOLS, is_available, get_model_list, run_agent_loop, build_system_prompt, get_file_tree
from .remote_runtime import run_remote_mode, run_ssh_mode, run_teleport_mode
from .runtime import PortRuntime
from .session_store import load_session
from .setup import run_setup
from .tool_pool import assemble_tool_pool
from .tools import execute_tool, get_tool, get_tools, render_tool_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Python porting workspace for the Claw Code rewrite effort')
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('summary', help='render a Markdown summary of the Python porting workspace')
    subparsers.add_parser('manifest', help='print the current Python workspace manifest')
    subparsers.add_parser('parity-audit', help='compare the Python workspace against the local ignored TypeScript archive when available')
    subparsers.add_parser('setup-report', help='render the startup/prefetch setup report')
    subparsers.add_parser('command-graph', help='show command graph segmentation')
    subparsers.add_parser('tool-pool', help='show assembled tool pool with default settings')
    subparsers.add_parser('bootstrap-graph', help='show the mirrored bootstrap/runtime graph stages')
    list_parser = subparsers.add_parser('subsystems', help='list the current Python modules in the workspace')
    list_parser.add_argument('--limit', type=int, default=32)

    commands_parser = subparsers.add_parser('commands', help='list mirrored command entries from the archived snapshot')
    commands_parser.add_argument('--limit', type=int, default=20)
    commands_parser.add_argument('--query')
    commands_parser.add_argument('--no-plugin-commands', action='store_true')
    commands_parser.add_argument('--no-skill-commands', action='store_true')

    tools_parser = subparsers.add_parser('tools', help='list mirrored tool entries from the archived snapshot')
    tools_parser.add_argument('--limit', type=int, default=20)
    tools_parser.add_argument('--query')
    tools_parser.add_argument('--simple-mode', action='store_true')
    tools_parser.add_argument('--no-mcp', action='store_true')
    tools_parser.add_argument('--deny-tool', action='append', default=[])
    tools_parser.add_argument('--deny-prefix', action='append', default=[])

    route_parser = subparsers.add_parser('route', help='route a prompt across mirrored command/tool inventories')
    route_parser.add_argument('prompt')
    route_parser.add_argument('--limit', type=int, default=5)

    bootstrap_parser = subparsers.add_parser('bootstrap', help='build a runtime-style session report from the mirrored inventories')
    bootstrap_parser.add_argument('prompt')
    bootstrap_parser.add_argument('--limit', type=int, default=5)

    loop_parser = subparsers.add_parser('turn-loop', help='run a small stateful turn loop for the mirrored runtime')
    loop_parser.add_argument('prompt')
    loop_parser.add_argument('--limit', type=int, default=5)
    loop_parser.add_argument('--max-turns', type=int, default=3)
    loop_parser.add_argument('--structured-output', action='store_true')

    flush_parser = subparsers.add_parser('flush-transcript', help='persist and flush a temporary session transcript')
    flush_parser.add_argument('prompt')

    load_session_parser = subparsers.add_parser('load-session', help='load a previously persisted session')
    load_session_parser.add_argument('session_id')

    remote_parser = subparsers.add_parser('remote-mode', help='simulate remote-control runtime branching')
    remote_parser.add_argument('target')
    ssh_parser = subparsers.add_parser('ssh-mode', help='simulate SSH runtime branching')
    ssh_parser.add_argument('target')
    teleport_parser = subparsers.add_parser('teleport-mode', help='simulate teleport runtime branching')
    teleport_parser.add_argument('target')
    direct_parser = subparsers.add_parser('direct-connect-mode', help='simulate direct-connect runtime branching')
    direct_parser.add_argument('target')
    deep_link_parser = subparsers.add_parser('deep-link-mode', help='simulate deep-link runtime branching')
    deep_link_parser.add_argument('target')

    show_command = subparsers.add_parser('show-command', help='show one mirrored command entry by exact name')
    show_command.add_argument('name')
    show_tool = subparsers.add_parser('show-tool', help='show one mirrored tool entry by exact name')
    show_tool.add_argument('name')

    exec_command_parser = subparsers.add_parser('exec-command', help='execute a mirrored command shim by exact name')
    exec_command_parser.add_argument('name')
    exec_command_parser.add_argument('prompt')

    exec_tool_parser = subparsers.add_parser('exec-tool', help='execute a mirrored tool shim by exact name')
    exec_tool_parser.add_argument('name')
    exec_tool_parser.add_argument('payload')

    chat_parser = subparsers.add_parser('chat', help='interactive chat with local Ollama model')
    chat_parser.add_argument('--model', default=None, help='Ollama model name (default: from OLLAMA_MODEL env or qwen2.5-coder:14b)')
    chat_parser.add_argument('prompt', nargs='?', default=None, help='single prompt (non-interactive)')
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    manifest = build_port_manifest()
    if args.command == 'summary':
        print(QueryEnginePort(manifest).render_summary())
        return 0
    if args.command == 'manifest':
        print(manifest.to_markdown())
        return 0
    if args.command == 'parity-audit':
        print(run_parity_audit().to_markdown())
        return 0
    if args.command == 'setup-report':
        print(run_setup().as_markdown())
        return 0
    if args.command == 'command-graph':
        print(build_command_graph().as_markdown())
        return 0
    if args.command == 'tool-pool':
        print(assemble_tool_pool().as_markdown())
        return 0
    if args.command == 'bootstrap-graph':
        print(build_bootstrap_graph().as_markdown())
        return 0
    if args.command == 'subsystems':
        for subsystem in manifest.top_level_modules[: args.limit]:
            print(f'{subsystem.name}\t{subsystem.file_count}\t{subsystem.notes}')
        return 0
    if args.command == 'commands':
        if args.query:
            print(render_command_index(limit=args.limit, query=args.query))
        else:
            commands = get_commands(include_plugin_commands=not args.no_plugin_commands, include_skill_commands=not args.no_skill_commands)
            output_lines = [f'Command entries: {len(commands)}', '']
            output_lines.extend(f'- {module.name} — {module.source_hint}' for module in commands[: args.limit])
            print('\n'.join(output_lines))
        return 0
    if args.command == 'tools':
        if args.query:
            print(render_tool_index(limit=args.limit, query=args.query))
        else:
            permission_context = ToolPermissionContext.from_iterables(args.deny_tool, args.deny_prefix)
            tools = get_tools(simple_mode=args.simple_mode, include_mcp=not args.no_mcp, permission_context=permission_context)
            output_lines = [f'Tool entries: {len(tools)}', '']
            output_lines.extend(f'- {module.name} — {module.source_hint}' for module in tools[: args.limit])
            print('\n'.join(output_lines))
        return 0
    if args.command == 'route':
        matches = PortRuntime().route_prompt(args.prompt, limit=args.limit)
        if not matches:
            print('No mirrored command/tool matches found.')
            return 0
        for match in matches:
            print(f'{match.kind}\t{match.name}\t{match.score}\t{match.source_hint}')
        return 0
    if args.command == 'bootstrap':
        print(PortRuntime().bootstrap_session(args.prompt, limit=args.limit).as_markdown())
        return 0
    if args.command == 'turn-loop':
        results = PortRuntime().run_turn_loop(args.prompt, limit=args.limit, max_turns=args.max_turns, structured_output=args.structured_output)
        for idx, result in enumerate(results, start=1):
            print(f'## Turn {idx}')
            print(result.output)
            print(f'stop_reason={result.stop_reason}')
        return 0
    if args.command == 'flush-transcript':
        engine = QueryEnginePort.from_workspace()
        engine.submit_message(args.prompt)
        path = engine.persist_session()
        print(path)
        print(f'flushed={engine.transcript_store.flushed}')
        return 0
    if args.command == 'load-session':
        session = load_session(args.session_id)
        print(f'{session.session_id}\n{len(session.messages)} messages\nin={session.input_tokens} out={session.output_tokens}')
        return 0
    if args.command == 'remote-mode':
        print(run_remote_mode(args.target).as_text())
        return 0
    if args.command == 'ssh-mode':
        print(run_ssh_mode(args.target).as_text())
        return 0
    if args.command == 'teleport-mode':
        print(run_teleport_mode(args.target).as_text())
        return 0
    if args.command == 'direct-connect-mode':
        print(run_direct_connect(args.target).as_text())
        return 0
    if args.command == 'deep-link-mode':
        print(run_deep_link(args.target).as_text())
        return 0
    if args.command == 'show-command':
        module = get_command(args.name)
        if module is None:
            print(f'Command not found: {args.name}')
            return 1
        print('\n'.join([module.name, module.source_hint, module.responsibility]))
        return 0
    if args.command == 'show-tool':
        module = get_tool(args.name)
        if module is None:
            print(f'Tool not found: {args.name}')
            return 1
        print('\n'.join([module.name, module.source_hint, module.responsibility]))
        return 0
    if args.command == 'exec-command':
        result = execute_command(args.name, args.prompt)
        print(result.message)
        return 0 if result.handled else 1
    if args.command == 'exec-tool':
        result = execute_tool(args.name, args.payload)
        print(result.message)
        return 0 if result.handled else 1
    if args.command == 'chat':
        from rich.console import Console
        from rich.live import Live
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.table import Table
        from rich import box
        from .memory_store import load_memory, save_memory, AgentMemory
        from .ollama_client import summarize_history

        console = Console()

        if not is_available():
            console.print(Panel('[bold red]Ollama nije dostupna.[/]\nPokreni: [cyan]ollama serve[/]', border_style='red'))
            return 1

        # ── startup banner ────────────────────────────────────────────────
        import os as _os
        from .config import load_config as _load_config, save_project_config as _save_project_config
        _cwd_init = _os.getcwd()
        _cfg = _load_config(_cwd_init)
        _mem: AgentMemory = load_memory(_cwd_init)

        state = {
            'model': args.model or _cfg.model,
            'history': list(_mem.history),  # restore history from last session
            'cwd': _cwd_init,
            'last_answer': '',
            'memory': _mem,
            'config': _cfg,
        }
        tool_names = [t['function']['name'] for t in TOOLS]
        models = get_model_list()
        current_model = state['model']
        model_display = current_model if current_model in models else f'{current_model} [dim](not pulled)[/]'
        _mem_summary = (
            f'Memory: [green]{len(_mem.history)} turns[/]  •  '
            f'[cyan]{len(_mem.preferences)} prefs[/]  •  '
            f'[magenta]{len(_mem.facts)} facts[/]'
            if (_mem.history or _mem.preferences or _mem.facts)
            else '[dim]Memory: empty (new session)[/]'
        )

        console.print(Panel(
            f'[bold cyan]vukixAI Agent[/]  •  [dim]Local AI Coding Agent[/]\n'
            f'Model: [green]{model_display}[/]  •  Temp: [yellow]{_cfg.temperature}[/]\n'
            f'Ollama: [green]✓ online[/]  •  Tools: [yellow]{len(tool_names)}[/]  •  Config: [dim]{_cfg._source}[/]\n'
            f'{_mem_summary}\n'
            f'[dim]Type /help for commands  •  /config for settings  •  Ctrl+C to exit[/]',
            border_style='cyan',
            title='[bold]🐆 vukixAI[/]',
        ))
        console.print(f'[dim]📁 {state["cwd"]}[/]\n')

        # ── rich callbacks ────────────────────────────────────────────────
        from rich.status import Status as _Status
        from .ollama_client import execute_tool as _execute_tool
        import time as _time

        # Holds the active spinner so tool_runner can stop it before printing result
        _active_spinner: list[_Status | None] = [None]

        # ── session stats ─────────────────────────────────────────────────
        _session_stats = {
            'tool_calls': 0,
            'api_calls': 0,
            'changes': [],       # list of {path, action, lines_added, lines_removed}
            'start_time': _time.time(),
            'total_tokens_in': 0,
            'total_tokens_out': 0,
        }

        # ── tool icons ────────────────────────────────────────────────────
        _TOOL_ICONS = {
            'list_directory': '📂', 'read_file': '📖', 'write_file': '📝',
            'edit_file': '✏️', 'run_command': '⚡', 'find_files': '🔍',
            'search_in_files': '🔎', 'git_status': '🔀', 'create_directory': '📁',
            'show_diff': '📊', 'http_get': '🌐', 'save_preference': '💾',
            'save_fact': '💾', 'update_plan': '📋', 'tree': '🌳',
            'apply_patch': '🩹', 'undo_last_write': '↩️',
        }

        def _compact_tool_summary(name: str, arguments: dict) -> str:
            """One-line compact summary of a tool call."""
            icon = _TOOL_ICONS.get(name, '⚙')
            if name == 'write_file':
                path = arguments.get('path', '?')
                content = arguments.get('content', '')
                lines = content.count('\n') + 1 if content else 0
                return f'{icon} [bold cyan]write_file[/] → [green]{_Path(path).name}[/] ({lines} lines)'
            if name == 'edit_file':
                path = arguments.get('path', '?')
                return f'{icon} [bold cyan]edit_file[/] → [green]{_Path(path).name}[/]'
            if name == 'read_file':
                path = arguments.get('path', '?')
                return f'{icon} [bold cyan]read_file[/] → [green]{_Path(path).name}[/]'
            if name == 'run_command':
                cmd = arguments.get('command', '?')
                if len(cmd) > 60:
                    cmd = cmd[:57] + '…'
                return f'{icon} [bold cyan]run_command[/] → [yellow]{cmd}[/]'
            if name == 'list_directory':
                path = arguments.get('path', '.')
                return f'{icon} [bold cyan]list_directory[/] → [green]{path}[/]'
            if name in ('find_files', 'search_in_files'):
                query = arguments.get('pattern', arguments.get('query', '?'))
                return f'{icon} [bold cyan]{name}[/] → [yellow]{query}[/]'
            if name == 'apply_patch':
                patch = arguments.get('patch', '')
                n_files = patch.count('*** Update File:') + patch.count('*** Add File:') + patch.count('*** Delete File:')
                return f'{icon} [bold cyan]apply_patch[/] → [yellow]{n_files} file(s)[/]'
            if name == 'undo_last_write':
                path = arguments.get('path', '?')
                return f'{icon} [bold cyan]undo_last_write[/] → [green]{_Path(path).name}[/]'
            if name == 'update_plan':
                steps = arguments.get('steps', [])
                done = sum(1 for s in steps if s.get('status') == 'completed')
                return f'{icon} [bold cyan]update_plan[/] → [yellow]{done}/{len(steps)} steps[/]'
            # fallback: compact args
            args_short = ', '.join(f'{k}={str(v)[:30]}' for k, v in arguments.items())
            return f'{icon} [bold cyan]{name}[/]({args_short})'

        def on_tool_call(name: str, arguments: dict) -> None:
            console.print(_compact_tool_summary(name, arguments))

        def tool_runner(name: str, arguments: dict) -> str:
            """Wrap tool execution with a live spinner and timing."""
            from .ollama_client import update_working_memory
            _session_stats['tool_calls'] += 1
            t0 = _time.time()
            spinner = console.status(f'[yellow]Running [bold]{name}[/]…[/]', spinner='dots')
            _active_spinner[0] = spinner
            spinner.start()
            try:
                result = _execute_tool(name, arguments)
            finally:
                spinner.stop()
                _active_spinner[0] = None
            elapsed = _time.time() - t0
            # Track file changes + update working memory
            if name == 'write_file':
                content = arguments.get('content', '')
                _session_stats['changes'].append({
                    'path': arguments.get('path', '?'),
                    'action': 'write',
                    'lines': content.count('\n') + 1,
                })
                update_working_memory('last_action', f'wrote {_Path(arguments.get("path","?")).name}')
            elif name == 'edit_file':
                _session_stats['changes'].append({
                    'path': arguments.get('path', '?'),
                    'action': 'edit',
                })
                update_working_memory('last_action', f'edited {_Path(arguments.get("path","?")).name}')
            elif name == 'create_directory':
                _session_stats['changes'].append({
                    'path': arguments.get('path', '?'),
                    'action': 'mkdir',
                })
            elif name == 'read_file':
                # Track files we've read in working memory
                files_read = _session_stats.get('_files_read', [])
                fname = _Path(arguments.get('path', '?')).name
                if fname not in files_read:
                    files_read.append(fname)
                _session_stats['_files_read'] = files_read
                update_working_memory('files_read', files_read[-10:])
            elif name == 'apply_patch':
                update_working_memory('last_action', 'applied patch')
            # Update total tool calls in working memory
            update_working_memory('tool_calls', _session_stats['tool_calls'])
            update_working_memory('files_changed', len(_session_stats['changes']))
            console.print(f'  [dim]└─ done ({elapsed:.1f}s)[/]')
            return result

        def on_tool_result(_name: str, result: str) -> None:
            # Special render for update_plan — show as checkbox list
            if _name == 'update_plan':
                from .ollama_client import _current_plan
                if _current_plan:
                    _icons = {'completed': '[green]☑[/]', 'in_progress': '[yellow]▶[/]', 'pending': '[dim]☐[/]'}
                    plan_lines = []
                    for s in _current_plan:
                        icon = _icons.get(s.get('status', 'pending'), '[dim]☐[/]')
                        text = s.get('text', '?')
                        if s.get('status') == 'in_progress':
                            text = f'[bold yellow]{text}[/]'
                        elif s.get('status') == 'completed':
                            text = f'[green]{text}[/]'
                        else:
                            text = f'[dim]{text}[/]'
                        plan_lines.append(f'  {icon} {text}')
                    console.print(Panel(
                        '\n'.join(plan_lines),
                        title='[cyan]📋 Plan[/]',
                        border_style='cyan',
                        padding=(0, 1),
                    ))
                return
            # Compact preview — max 200 chars, 4 lines
            lines = result.splitlines()
            if len(lines) > 4:
                preview = '\n'.join(lines[:4]) + f'\n[dim]… +{len(lines)-4} more lines[/]'
            elif len(result) > 200:
                preview = result[:200] + '\n[dim]… truncated[/]'
            else:
                preview = result
            console.print(Panel(
                preview,
                title='[green]✓ Result[/]',
                border_style='green',
                padding=(0, 1),
            ))

        def on_plan(text: str) -> None:
            """Show the model's narration/thinking before it executes tools."""
            # Strip <think>...</think> tags from Qwen3 and show separately
            import re
            think_match = re.search(r'<think>(.*?)</think>', text, re.DOTALL)
            if think_match:
                thinking = think_match.group(1).strip()
                remaining = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
                if thinking:
                    # Show first 300 chars of thinking
                    if len(thinking) > 300:
                        thinking = thinking[:300] + '…'
                    console.print(Panel(
                        f'[dim italic]{thinking}[/]',
                        title='[blue]💭 Thinking[/]',
                        border_style='blue',
                        padding=(0, 1),
                    ))
                if remaining:
                    console.print(Panel(
                        f'{remaining}',
                        title='[cyan]📋 Plan[/]',
                        border_style='cyan',
                        padding=(0, 1),
                    ))
            else:
                console.print(Panel(
                    f'[dim]{text}[/]',
                    title='[cyan]📋 Plan[/]',
                    border_style='cyan',
                    padding=(0, 1),
                ))

        # ── @filename expander ────────────────────────────────────────────
        from pathlib import Path as _Path

        def expand_at_refs(text: str) -> str:
            """Replace @filename with file contents inline before sending to model."""
            import re
            def replace_ref(match: re.Match) -> str:
                fname = match.group(1)
                p = _Path(state['cwd']) / fname
                if not p.exists():
                    hits = list(_Path(state['cwd']).rglob(fname))
                    p = hits[0] if hits else p
                if p.exists() and p.is_file():
                    try:
                        content = p.read_text(encoding='utf-8', errors='replace')
                        if len(content) > 8000:
                            content = content[:8000] + '\n... [truncated]'
                        console.print(f'[dim]📎 Loaded: {p}[/]')
                        # Use angle brackets so Rich doesn't parse as markup
                        return f'<FILE: {p.name}>\n```\n{content}\n```\n</FILE>'
                    except Exception:
                        pass
                console.print(f'[yellow]⚠ @{fname} not found — will use find_files[/]')
                return match.group(0)
            return re.sub(r'@([\w./_\\-]+)', replace_ref, text)

        # ── slash command handler ─────────────────────────────────────────
        def handle_slash(cmd: str) -> bool:
            """Returns True if handled."""
            parts = cmd.strip().split(None, 1)
            slash = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ''

            if slash == '/help':
                t = Table(box=box.SIMPLE, show_header=True, header_style='bold cyan')
                t.add_column('Command', style='cyan')
                t.add_column('Description')
                for c, d in [
                    ('/help', 'Show this help'),
                    ('/tools', 'List available tools'),
                    ('/model <name>', 'Switch model (e.g. /model qwen2.5-coder:14b)'),
                    ('/models', 'List available Ollama models'),
                    ('/open <path>', 'Open a project folder as working directory'),
                    ('/clear', 'Clear conversation history (memory preserved)'),
                    ('/history', 'Show conversation history'),
                    ('/undo', 'Remove last exchange from history'),
                    ('/memory', 'Show persistent memory (preferences + facts)'),
                    ('/memory clear', 'Wipe all persistent memory for this project'),
                    ('/remember <fact>', 'Manually save a fact to persistent memory'),
                    ('/run <cmd>', 'Run a shell command directly'),
                    ('/save <file>', 'Save last AI answer to a file'),
                    ('/cwd', 'Show or change working directory'),
                    ('/changes', 'Show files changed this session'),
                    ('/stats', 'Show session statistics'),
                    ('/config', 'Show current configuration'),
                    ('/set <key> <value>', 'Change a setting (e.g. /set temperature 0.2)'),
                    ('/commit [msg]', 'Git commit all changes (auto-generates message if omitted)'),
                    ('/diff', 'Show git diff of uncommitted changes'),
                    ('/tokens', 'Show estimated context token usage'),
                    ('/exit', 'Exit the agent'),
                    ('', ''),
                    ('@filename', 'Inline-load a file into your prompt (e.g. @main.py)'),
                ]:
                    t.add_row(c, d)
                console.print(t)
                return True

            if slash == '/tools':
                t = Table(box=box.SIMPLE, show_header=True, header_style='bold cyan')
                t.add_column('Tool', style='cyan')
                t.add_column('Description')
                for tool in TOOLS:
                    fn = tool['function']
                    t.add_row(fn['name'], fn['description'][:80])
                console.print(t)
                return True

            if slash == '/models':
                ml = get_model_list()
                if ml:
                    console.print('[bold]Available Ollama models:[/]')
                    for m in ml:
                        marker = ' [green]← current[/]' if m == state['model'] else ''
                        console.print(f'  [cyan]{m}[/]{marker}')
                else:
                    console.print('[yellow]No models found.[/]')
                return True

            if slash == '/model':
                if not arg:
                    console.print(f'Current model: [green]{state["model"]}[/]')
                else:
                    state['model'] = arg.strip()
                    console.print(f'[green]Model switched to: {state["model"]}[/]')
                return True

            if slash == '/clear':
                state['history'] = []
                console.print('[green]Conversation history cleared.[/]')
                return True

            if slash == '/memory':
                mem: AgentMemory = state['memory']
                if arg.strip() == 'clear':
                    state['memory'] = AgentMemory(project_path=state['cwd'])
                    state['history'] = []
                    save_memory(state['memory'], state['cwd'])
                    console.print('[green]Memory cleared (history, preferences, facts).[/]')
                    return True
                t = Table(box=box.SIMPLE, show_header=True, header_style='bold cyan')
                t.add_column('Type', style='cyan')
                t.add_column('Content')
                for k, v in mem.preferences.items():
                    t.add_row('preference', f'[bold]{k}[/] = {v}')
                for f in mem.facts:
                    t.add_row('fact', f)
                t.add_row('history', f'{len(mem.history)} turns persisted from last session')
                console.print(Panel(t, title='[cyan]Persistent Memory[/]', border_style='cyan'))
                return True

            if slash == '/remember':
                if not arg:
                    console.print('[yellow]Usage: /remember <fact>[/]')
                    return True
                mem = state['memory']
                mem.facts.append(arg.strip())
                save_memory(mem, state['cwd'])
                console.print(f'[green]Fact saved: {arg.strip()!r}[/]')
                return True

            if slash == '/history':
                if not state['history']:
                    console.print('[dim]No history.[/]')
                else:
                    for msg in state['history']:
                        role = '[cyan]You[/]' if msg['role'] == 'user' else '[green]AI[/]'
                        console.print(f'{role}: {msg["content"][:120]}')
                return True

            if slash == '/cwd':
                import os
                if arg:
                    try:
                        os.chdir(arg)
                        state['cwd'] = os.getcwd()
                        console.print(f'[green]Working directory: {state["cwd"]}[/]')
                    except Exception as e:
                        console.print(f'[red]Error: {e}[/]')
                else:
                    console.print(f'[cyan]Current directory: {state["cwd"]}[/]')
                return True

            if slash == '/open':
                import os
                if not arg:
                    console.print('[yellow]Usage: /open <path>[/]')
                    return True
                target = Path(arg)
                if not target.exists():
                    console.print(f'[red]Path does not exist: {arg}[/]')
                    return True
                if target.is_file():
                    target = target.parent
                os.chdir(target)
                state['cwd'] = str(target.resolve())
                # Save old project memory before switching
                save_memory(state['memory'], state['cwd'])
                # Load memory for new project
                new_mem = load_memory(state['cwd'])
                state['memory'] = new_mem
                state['history'] = list(new_mem.history)
                tree = get_file_tree(state['cwd'])
                mem_info = f'{len(new_mem.history)} turns, {len(new_mem.preferences)} prefs, {len(new_mem.facts)} facts' if (new_mem.history or new_mem.preferences or new_mem.facts) else 'no previous memory'
                console.print(Panel(
                    f'[bold]📁 {state["cwd"]}[/]\n\n{tree}\n\n[dim]Memory: {mem_info}[/]',
                    title='[cyan]Project opened[/]',
                    border_style='cyan',
                ))
                return True

            if slash == '/undo':
                if len(state['history']) >= 2:
                    state['history'] = state['history'][:-2]
                    console.print('[green]Last exchange removed from history.[/]')
                else:
                    state['history'] = []
                    console.print('[yellow]History is now empty.[/]')
                return True

            if slash == '/run':
                if not arg:
                    console.print('[yellow]Usage: /run <command>[/]')
                    return True
                import subprocess
                try:
                    result = subprocess.run(arg, shell=True, capture_output=True, text=True, timeout=30, cwd=state['cwd'])
                    out = result.stdout.strip()
                    err = result.stderr.strip()
                    content = '\n'.join(filter(None, [out, f'stderr: {err}' if err else '', f'exit: {result.returncode}']))
                    console.print(Panel(content or '[No output]', title=f'[cyan]$ {arg}[/]', border_style='dim'))
                except Exception as e:
                    console.print(f'[red]{e}[/]')
                return True

            if slash == '/save':
                if not state['last_answer']:
                    console.print('[yellow]No answer to save yet.[/]')
                    return True
                fname = arg.strip() if arg else 'agent_output.md'
                Path(fname).write_text(state['last_answer'], encoding='utf-8')
                console.print(f'[green]Saved to {fname}[/]')
                return True

            if slash == '/changes':
                changes = _session_stats['changes']
                if not changes:
                    console.print('[dim]No files changed this session.[/]')
                    return True
                t = Table(box=box.SIMPLE, show_header=True, header_style='bold cyan')
                t.add_column('Action', style='yellow')
                t.add_column('File', style='green')
                t.add_column('Lines')
                for c in changes:
                    t.add_row(c.get('action', '?'), c.get('path', '?'), str(c.get('lines', '-')))
                console.print(Panel(t, title=f'[cyan]Files changed: {len(changes)}[/]', border_style='cyan'))
                return True

            if slash == '/stats':
                elapsed = _time.time() - _session_stats['start_time']
                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                console.print(Panel(
                    f'[bold]Session duration:[/] {mins}m {secs}s\n'
                    f'[bold]API calls:[/] {_session_stats["api_calls"]}\n'
                    f'[bold]Tool calls:[/] {_session_stats["tool_calls"]}\n'
                    f'[bold]Files changed:[/] {len(_session_stats["changes"])}\n'
                    f'[bold]History turns:[/] {len(state["history"])}',
                    title='[cyan]📊 Session Stats[/]',
                    border_style='cyan',
                ))
                return True

            if slash == '/config':
                cfg = state['config']
                t = Table(box=box.SIMPLE, show_header=True, header_style='bold cyan')
                t.add_column('Setting', style='cyan')
                t.add_column('Value', style='green')
                for k, v in cfg.to_dict().items():
                    t.add_row(k, str(v))
                t.add_row('[dim]source[/]', f'[dim]{cfg._source}[/]')
                console.print(Panel(t, title='[cyan]⚙ Configuration[/]', border_style='cyan'))
                return True

            if slash == '/set':
                if not arg or ' ' not in arg.strip():
                    console.print('[yellow]Usage: /set <key> <value>  (e.g. /set temperature 0.2)[/]')
                    return True
                key, value = arg.strip().split(None, 1)
                cfg = state['config']
                if not hasattr(cfg, key) or key.startswith('_'):
                    console.print(f'[red]Unknown setting: {key}[/]  Use /config to see available settings.')
                    return True
                old_val = getattr(cfg, key)
                expected_type = type(old_val)
                try:
                    if expected_type == bool:
                        new_val = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        new_val = expected_type(value)
                    setattr(cfg, key, new_val)
                    # Sync model to state
                    if key == 'model':
                        state['model'] = new_val
                    console.print(f'[green]{key}: {old_val} → {new_val}[/]')
                except (ValueError, TypeError) as e:
                    console.print(f'[red]Invalid value for {key}: {e}[/]')
                return True

            if slash == '/commit':
                import subprocess as _sp
                # Show what would be committed
                diff_result = _sp.run(
                    'git diff --stat', shell=True, capture_output=True,
                    text=True, timeout=10, cwd=state['cwd'],
                )
                status_result = _sp.run(
                    'git status --short', shell=True, capture_output=True,
                    text=True, timeout=10, cwd=state['cwd'],
                )
                if not diff_result.stdout.strip() and not status_result.stdout.strip():
                    console.print('[yellow]Nothing to commit — working tree clean.[/]')
                    return True
                console.print(Panel(
                    status_result.stdout.strip() or '[no changes]',
                    title='[cyan]Files to commit[/]', border_style='cyan',
                ))
                msg = arg.strip() if arg else None
                if not msg:
                    # Auto-generate from changes
                    changes = _session_stats['changes']
                    if changes:
                        files = [_Path(c['path']).name for c in changes[:5]]
                        msg = f"vukixAI: update {', '.join(files)}"
                    else:
                        msg = "vukixAI: auto-commit session changes"
                _sp.run('git add -A', shell=True, cwd=state['cwd'], timeout=10)
                commit_result = _sp.run(
                    f'git commit -m "{msg}"', shell=True, capture_output=True,
                    text=True, timeout=10, cwd=state['cwd'],
                )
                if commit_result.returncode == 0:
                    console.print(f'[green]✅ Committed: {msg}[/]')
                else:
                    console.print(f'[red]Commit failed: {commit_result.stderr.strip()}[/]')
                return True

            if slash == '/diff':
                import subprocess as _sp
                result = _sp.run(
                    'git diff --stat HEAD', shell=True, capture_output=True,
                    text=True, timeout=10, cwd=state['cwd'],
                )
                output = result.stdout.strip() or '[No uncommitted changes]'
                console.print(Panel(output, title='[cyan]Git Diff[/]', border_style='cyan'))
                return True

            if slash == '/tokens':
                from .ollama_client import estimate_tokens
                sys_prompt = _build_sys_prompt()
                all_messages = [{'role': 'system', 'content': sys_prompt}] + state['history']
                est = estimate_tokens(all_messages)
                console.print(Panel(
                    f'[bold]System prompt:[/] ~{len(sys_prompt)//4} tokens\n'
                    f'[bold]History:[/] {len(state["history"])} messages\n'
                    f'[bold]Estimated total:[/] ~{est:,} tokens\n'
                    f'[dim]Model context window varies by model (Qwen3: 32k-128k)[/]',
                    title='[cyan]🔢 Token Estimate[/]', border_style='cyan',
                ))
                return True

            if slash in ('/exit', '/quit'):
                raise KeyboardInterrupt

            console.print(f'[red]Unknown command: {slash}[/]  Type /help for list.')
            return True

        def _get_git_branch() -> str:
            """Get current git branch, or '' if not in a repo."""
            import subprocess as _sp
            try:
                result = _sp.run(
                    'git branch --show-current', shell=True,
                    capture_output=True, text=True, timeout=5, cwd=state['cwd'],
                )
                return result.stdout.strip() if result.returncode == 0 else ''
            except Exception:
                return ''

        def _build_sys_prompt() -> str:
            """Build system prompt including persisted memory, working memory, and token estimate."""
            from .ollama_client import get_working_memory_context, estimate_tokens
            mem_ctx = state['memory'].as_context_block()
            wm_ctx = get_working_memory_context()
            extra_context = '\n'.join(filter(None, [mem_ctx, wm_ctx]))
            return build_system_prompt(
                cwd=state['cwd'],
                file_tree=get_file_tree(state['cwd']),
                memory_context=extra_context or None,
            )

        def _maybe_summarize_history() -> None:
            """When history exceeds 20 messages, summarize the oldest 10 and replace them."""
            if len(state['history']) <= 20:
                return
            console.print('[dim]📝 Summarizing older conversation turns…[/]')
            summary_text = summarize_history(
                state['history'], model=state['model'], n_turns=10
            )
            # Replace the oldest 10 turns with a single summary pair
            remaining = state['history'][10:]
            state['history'] = [
                {'role': 'user', 'content': '[Summary of earlier conversation — treat as established context]'},
                {'role': 'assistant', 'content': summary_text},
            ] + remaining

        def _save_session() -> None:
            """Persist history and memory to disk."""
            mem: AgentMemory = state['memory']
            mem.history = state['history']
            save_memory(mem, state['cwd'])

        # ── single-prompt mode ────────────────────────────────────────────
        if args.prompt:
            expanded_prompt = expand_at_refs(args.prompt)
            buf = ['']
            with Live(console=console, refresh_per_second=15) as live:
                def _stream_single(chunk: str) -> None:
                    buf[0] += chunk
                    live.update(Markdown(buf[0]))
                run_agent_loop(
                    expanded_prompt, model=state['model'],
                    on_tool_call=on_tool_call, on_tool_result=on_tool_result,
                    stream_callback=_stream_single,
                    system_prompt=_build_sys_prompt(),
                    tool_runner=tool_runner,
                    on_plan=on_plan,
                )
            console.print()
            return 0

        # ── interactive loop ──────────────────────────────────────────────
        try:
            while True:
                # show short cwd + git branch in prompt
                cwd_short = _Path(state['cwd']).name or state['cwd']
                _branch = _get_git_branch()
                _branch_display = f' [magenta]{_branch}[/]' if _branch else ''
                try:
                    user_input = console.input(f'[dim]{cwd_short}[/]{_branch_display} [bold cyan]You>[/] ').strip()
                except (KeyboardInterrupt, EOFError):
                    console.print('\n[dim]Doviđenja![/]')
                    break

                if not user_input:
                    continue
                if user_input.lower() in ('exit', 'quit', 'q', '/exit', '/quit'):
                    console.print('[dim]Doviđenja![/]')
                    break
                if user_input.startswith('/'):
                    handle_slash(user_input)
                    continue

                # expand @filename references
                expanded = expand_at_refs(user_input)

                # Live thinking timer
                _think_start = _time.time()
                _thinking_spinner = console.status(
                    '[blue]💭 thinking…[/] [dim]0.0s[/]', spinner='dots'
                )
                _thinking_spinner.start()
                _session_stats['api_calls'] += 1

                buf = ['']
                _first_token = [True]

                def _stream_chat(chunk: str) -> None:
                    if _first_token[0]:
                        _thinking_spinner.stop()
                        elapsed = _time.time() - _think_start
                        console.print(f'[dim]💭 thought for {elapsed:.1f}s[/]')
                        _first_token[0] = False
                    buf[0] += chunk

                # We need Live for markdown rendering but only after thinking stops
                full_answer = run_agent_loop(
                    expanded,
                    history=state['history'],
                    model=state['model'],
                    on_tool_call=on_tool_call,
                    on_tool_result=on_tool_result,
                    stream_callback=_stream_chat,
                    system_prompt=_build_sys_prompt(),
                    tool_runner=tool_runner,
                    on_plan=on_plan,
                )

                # Stop spinner if no streaming happened (all tool calls, no final text)
                if _first_token[0]:
                    _thinking_spinner.stop()
                    elapsed = _time.time() - _think_start
                    console.print(f'[dim]💭 done in {elapsed:.1f}s[/]')

                # Render the final answer as markdown
                if buf[0]:
                    console.print(Markdown(buf[0]))

                # Show session stats after each answer
                from .ollama_client import estimate_tokens
                n_changes = len(_session_stats['changes'])
                sys_prompt = _build_sys_prompt()
                all_msgs = [{'role': 'system', 'content': sys_prompt}] + state['history']
                token_est = estimate_tokens(all_msgs)
                stats_parts = [f'{_session_stats["tool_calls"]} tools']
                if n_changes > 0:
                    stats_parts.append(f'{n_changes} file(s) changed')
                stats_parts.append(f'~{token_est:,} tokens')
                console.print(f'[dim]📊 {" • ".join(stats_parts)}[/]')

                console.print()
                state['last_answer'] = full_answer
                state['history'].append({'role': 'user', 'content': user_input})
                state['history'].append({'role': 'assistant', 'content': full_answer})
                # Summarize when history gets long (replaces the old hard-slice to last 40)
                _maybe_summarize_history()
        finally:
            # Always save on exit, even on Ctrl+C or crash
            _save_session()
            console.print('[dim]💾 Session saved.[/]')
        return 0
    parser.error(f'unknown command: {args.command}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
