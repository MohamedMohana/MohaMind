# CLI Research for MohaMind

## Executive Summary

After analyzing the top AI agent CLIs (Aider, OpenHands, OpenAI Codex, Claude Code, Cursor) and the leading Python terminal libraries (Rich, Textual, prompt_toolkit), here are the key findings for building MohaMind's CLI.

---

## 1. AIDER (Best Python CLI Reference)

**Repo**: `Aider-AI/aider` (43k stars)
**Language**: Python
**CLI Library Stack**: `prompt_toolkit` + `rich` + custom spinner

### Architecture

```
aider/
├── main.py          # Entry point, argparse-based
├── io.py            # InputOutput class (THE core UI layer)
├── waiting.py       # Custom spinner (WaitingSpinner)
├── mdstream.py      # Streaming markdown renderer
├── args.py          # CLI argument parsing
└── commands.py      # Slash commands (/help, /add, etc.)
```

### Key Patterns

#### InputOutput Class (`io.py`) - ~800 lines, single class handles ALL UI
- **Dual mode**: Fancy terminal (prompt_toolkit) vs plain fallback (input())
- **`prompt_toolkit.PromptSession`**: autocomplete, history, keybindings, Vi/Emacs modes
- **`rich.Console`**: for all output (markdown, styled text, colored output)
- **Smart fallback**: Detects dumb terminals and degrades gracefully
- **Configurable colors**: user_input_color, tool_output_color, tool_error_color, assistant_output_color
- **NO_COLOR env var support**: Respects terminal conventions
- **Rich Markdown rendering** for assistant responses

#### Spinner (`waiting.py`) - Custom implementation
- **NOT using rich.status or yaspin** - they wrote their own
- Pre-rendered animation frames with ASCII fallback
- Unicode block characters (░█) scanning back and forth
- Thread-based (`threading.Thread`, daemon=True)
- 0.5s delay before showing (avoids flash on fast operations)
- 20fps max refresh rate
- Context manager support: `with WaitingSpinner("text"):`
- Tracks last frame index as class variable (continuity across calls)

#### Streaming Markdown (`mdstream.py`) - Real innovation
- **`rich.live.Live`** for the "unstable" bottom window
- **`rich.console.Console.print()`** for "stable" scrolled content above
- Sliding window of `live_window=6` lines at bottom that can shift
- Auto-adjusts refresh rate based on render time (adaptive throttling)
- `NoInsetCodeBlock` - custom markdown code blocks with zero padding
- `LeftHeading` - h1 gets a HEAVY box border panel, h2+ stays left-aligned

#### Autocomplete System
- `AutoCompleter` class with file-aware completions
- Tokenizes source files using pygments for identifier completion
- Command-specific completions (`/` prefix)
- `ThreadedCompleter` wrapper for non-blocking completion
- 3-character minimum before showing completions

#### Keybindings
- `Ctrl+Z`: Suspend to background
- `Ctrl+X Ctrl+E`: Open in external editor (like bash)
- `Alt+Enter`: Multiline toggle (newline vs submit)
- `Ctrl+Up/Down`: Navigate history
- Multiline mode: `{` opens, `}` closes block input

#### Premium Feel Elements
- **File status display**: Columns showing editable vs readonly files
- **Rich rule dividers** between conversations
- **Chat history logging**: Markdown-formatted `.aider.chat.history.md`
- **Bell notifications**: Terminal bell + OS notifications when LLM finishes
- **Placeholder text**: Pre-fills input from interrupted state
- **Voice input**: `sounddevice` + Whisper for voice-to-code

---

## 2. OPENHANDS (formerly OpenDevin)

**Repo**: `All-Hands-AI/OpenHands` (70.8k stars)
**Language**: Python (backend) + TypeScript (frontend)
**CLI**: Separate repo `OpenHands/OpenHands-CLI`

### Key Patterns

#### CLI Features
- **Command palette**: `Ctrl+P` for settings, MCP status
- **Pause agent**: `Esc` to pause running agent
- **Confirmation modes**: `--always-approve`, `--llm-approve`
- **Resume conversations**: `--resume --last` or `--resume <id>`
- **Headless mode**: Non-interactive for automation
- **Task from file**: `openhands -f requirements.txt`

#### Startup Experience
- Quick splash showing agent status
- Model selection on first run
- MCP server connection status

#### Architecture
- `openhands/io/` - I/O abstraction layer
- SDK-based: `openhands/sdk/` - composable Python library
- REST API + React frontend for GUI mode
- CLI mode is a terminal-first experience

---

## 3. OPENAI CODEX CLI

**Repo**: `openai/codex` 
**Language**: Rust (TUI) + TypeScript (CLI wrapper)
**TUI Framework**: Custom Rust TUI (`codex-rs/tui/`)

### Key Patterns

#### Rust TUI Architecture (`codex-rs/`)
- **Full TUI application** - not just a CLI, an interactive terminal app
- Custom `tui/` crate with components: chat composer, streaming, status
- **Alternate screen**: Uses full terminal screen with its own buffer
- **Stream chunking**: Tuned for responsive streaming display
- **Sandbox integration**: Terminal detection + exec sandboxing
- **Chat composer widget**: Multi-line input with history

#### CLI Entry Points
- `codexcli/` - Node.js CLI wrapper for the Rust TUI
- `codex-rs/cli/` - Rust CLI binary

#### Premium Rust TUI Features
- Alternate screen buffer (like vim/htop)
- Streaming chunking with validation and tuning
- User input prompts inline
- Exit confirmation prompt
- Slash commands (`/` prefix)

> Note: Codex is Rust, so the implementation patterns differ from Python. But the UX patterns (alternate screen, streaming, chat composer) are worth emulating.

---

## 4. CLAUDE CODE (Anthropic)

**Not open source** - behavioral analysis only.

### Observed CLI Patterns
- **Node.js based** terminal application
- Uses **ink** (React for CLI) + custom terminal handling
- **No alternate screen** - works inline in the terminal
- **Streaming markdown** output with syntax highlighting
- **Tool use indicators**: Shows "Reading file...", "Editing...", "Running..."
- **Thinking indicator**: Animated dots or pulsing cursor
- **Cost/token tracking**: Shows tokens used and estimated cost
- **Permission prompts**: Colored yes/no prompts for file edits
- **Rich diff display**: Shows changes before applying
- **Session continuity**: Remembers context across runs

---

## 5. CURSOR AGENT MODE

**Not open source** - IDE-integrated, not standalone CLI.

### Patterns Worth Noting
- Status bar at bottom with agent state
- Inline diffs in editor pane
- Terminal panel for command execution
- Tool approval flow with visual indicators
- Error highlighting with suggested fixes

---

## 6. Python Terminal Libraries Deep Dive

### RICH (56k stars) - The Foundation

**`pip install rich`** | By Will McGugan (Textualize)

#### Core Components for AI Agent CLI

```python
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.status import Status
from rich.syntax import Syntax
from rich.rule import Rule
from rich.columns import Columns
from rich.tree import Tree
from rich.logging import RichHandler
```

#### Key Rich Features for Premium CLI

1. **`Console`** - Central output handler
   - Auto-detects terminal capabilities
   - Word wrapping, truncation
   - Color system detection (truecolor, 256, 16, none)
   - `Console(file=...)` for capturing output
   
2. **`Live`** - Real-time display updates
   - Auto-refreshing display area
   - `refresh_per_second` for frame rate control
   - Can print above the live area (scrollback-safe)
   - Perfect for streaming LLM output

3. **`Markdown`** - Markdown rendering
   - Renders headers, lists, code blocks
   - Syntax highlighting in code blocks
   - Customizable themes

4. **`Status`** - Spinner with message
   ```python
   with console.status("[bold green]Thinking...") as status:
       result = llm_call()
   ```
   - 40+ built-in spinner animations
   - Non-blocking: can still use console

5. **`Progress`** - Progress bars
   ```python
   with Progress() as progress:
       task = progress.add_task("Processing...", total=100)
   ```
   - Multiple simultaneous bars
   - File download style with speed/ETA

6. **`Panel`** - Bordered content blocks
   ```python
   console.print(Panel("Content", title="Title", border_style="blue"))
   ```

7. **`Syntax`** - Code highlighting
   ```python
   Syntax(code, "python", theme="monokai", line_numbers=True)
   ```

#### Best Practices from Rich
- Use `Console` singleton, not `print()` directly
- Respect `NO_COLOR` env var
- Use markup `[bold red]text[/bold red]` not ANSI codes
- Use `Live` for any dynamic content
- Use `Panel` for grouping related output

---

### TEXTUAL (35.3k stars) - Full TUI Framework

**`pip install textual`** | By Textualize

#### What It Provides
- **Full application framework** with widgets, layouts, events
- **CSS-based styling** for terminal UIs
- **Async-native** architecture
- **Widgets**: Button, Input, DataTable, TreeView, TextArea, ListView
- **Command palette** built-in (`Ctrl+P`)
- **Web serving**: `textual serve` runs in browser too
- **Dev console**: Separate terminal for debugging
- **Themes**: Predefined dark/light themes

#### When to Use Textual vs Rich

| Use Case | Rich | Textual |
|----------|------|---------|
| Simple CLI output | ✅ | ❌ overkill |
| Streaming markdown | ✅ | ✅ better |
| Full-screen TUI | ❌ | ✅ |
| Widget-based UI | ❌ | ✅ |
| Chat interface | ✅ works | ✅ better |
| Inline in terminal | ✅ | ❌ takes over |
| Quick to implement | ✅ | ❌ more setup |
| Multiple panels | ❌ | ✅ |

#### Textual AI Agent Example
```python
from textual.app import App
from textual.widgets import Header, Footer, TextArea, Static
from textual.containers import Vertical

class AgentApp(App):
    CSS = """
    Screen { layout: vertical; }
    #output { height: 1fr; }
    #input { height: 3; dock: bottom; }
    """
    
    def compose(self):
        yield Header()
        yield Static(id="output")
        yield TextArea(id="input")
        yield Footer()
```

#### Toad (mentioned on Rich README)
- "Unified interface for agentic coding" built with Rich + Textual
- Screenshot shows multi-panel agent UI with streaming

---

### PROMPT_TOOLKIT - Interactive Input

**`pip install prompt_toolkit`** | Used by Aider, IPython, pgcli

#### Key Features
- **Auto-completion**: Multi-column, fuzzy, custom completers
- **Syntax highlighting**: Via pygments lexers
- **Vi/Emacs editing modes**: Full modal editing
- **History**: Persistent file-based history with search
- **Multi-line input**: With continuation prompts
- **Custom keybindings**: Fine-grained control
- **Mouse support**: Click, scroll in terminal
- **Styling**: ANSI and custom style dicts

#### Aider's prompt_toolkit Usage (best reference)
```python
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.completion import ThreadedCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

session = PromptSession(
    lexer=PygmentsLexer(MarkdownLexer),
    history=FileHistory("~/.history"),
    editing_mode=EditingMode.EMACS,
)

kb = KeyBindings()
@kb.add("escape", "enter")
def _(event):
    event.current_buffer.insert_text("\n")

line = session.prompt(
    "input> ",
    completer=ThreadedCompleter(my_completer),
    complete_style=CompleteStyle.MULTI_COLUMN,
    style=Style.from_dict({"": "blue"}),
    key_bindings=kb,
)
```

---

### Other Notable Libraries

#### Halo / Yaspin / Spinner
- **yaspin**: `pip install yaspin` - Simple spinner with text
- **halo**: `pip install halo` - Spinner with checkmark/cross completion
- **rich.status**: Built into Rich, 40+ spinner animations

#### Click / Typer - CLI Framework
- **click**: Decorator-based CLI framework (Flask uses it)
- **typer**: Click wrapper with type hints, auto-docs
- Both handle argument parsing, not interactive UI

#### Python Inquirer / Questionary
- **questionary**: Interactive prompts (select, checkbox, confirm)
- Good for onboarding/setup wizards

---

## 7. Recommended Stack for MohaMind

### Primary Stack: `rich` + `prompt_toolkit`

This is what Aider uses and it's proven at scale (43k stars, millions of installs).

```python
# pyproject.toml dependencies
dependencies = [
    "rich>=13.0",
    "prompt_toolkit>=3.0",
    "pygments>=2.0",       # syntax highlighting
]
```

### Architecture Pattern

```
moha_mind/
├── cli/
│   ├── __init__.py
│   ├── app.py           # Main CLI entry (like aider/main.py)
│   ├── io.py            # InputOutput class (like aider/io.py)
│   ├── spinner.py       # Custom spinner (like aider/waiting.py)
│   ├── mdstream.py      # Streaming markdown (like aider/mdstream.py)
│   ├── theme.py         # Color theme definitions
│   ├── commands.py      # Slash commands
│   ├── completions.py   # Autocomplete logic
│   └── onboarding.py    # First-run setup wizard
```

### Implementation Blueprint

#### 1. Startup Sequence (Premium Feel)

```python
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
import time

console = Console()

def show_banner():
    banner = Text()
    banner.append("MohaMind", style="bold cyan")
    banner.append(" v0.1.0", style="dim")
    banner.append("\n")
    banner.append("Your personal AI agent", style="italic")
    
    console.print()
    console.print(Panel(
        Align.center(banner),
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()

def show_status_line(model, memory_files, calendar_events):
    status = Text()
    status.append("● ", style="green")
    status.append(f"Model: {model}", style="bold")
    status.append("  ")
    status.append(f"Memory: {memory_files} files", style="dim")
    status.append("  ")
    status.append(f"Calendar: {calendar_events} upcoming", style="dim")
    console.print(status)
    console.print(Rule(style="dim"))
```

#### 2. Streaming Markdown Output (Aider Pattern)

```python
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text
import io, time

class MarkdownStream:
    """Stream LLM output as live-updating markdown."""
    
    def __init__(self, style="cyan", code_theme="monokai"):
        self.style = style
        self.code_theme = code_theme
        self.printed = []
        self.live = None
        self.min_delay = 1.0 / 20  # 20fps
        self.live_window = 6
    
    def update(self, text, final=False):
        if not self.live:
            self.live = Live(Text(""), refresh_per_second=20)
            self.live.start()
        
        now = time.time()
        if not final and now - self.when < self.min_delay:
            return
        
        string_io = io.StringIO()
        console = Console(file=string_io, force_terminal=True)
        console.print(Markdown(text, style=self.style, code_theme=self.code_theme))
        lines = string_io.getvalue().splitlines(keepends=True)
        
        num_lines = len(lines)
        if not final:
            num_lines -= self.live_window
        
        if final or num_lines > 0:
            show = lines[len(self.printed):num_lines]
            self.live.console.print(Text.from_ansi("".join(show)))
            self.printed = lines[:num_lines]
        
        if final:
            self.live.update(Text(""))
            self.live.stop()
            return
        
        rest = Text.from_ansi("".join(lines[num_lines:]))
        self.live.update(rest)
```

#### 3. Custom Spinner (Aider Pattern)

```python
import sys, threading, time
from rich.console import Console

class Spinner:
    FRAMES_ASCII = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    
    def __init__(self, text="Thinking"):
        self.text = text
        self.idx = 0
        self.visible = False
        self.console = Console()
        self.start_time = time.time()
    
    def step(self):
        if not sys.stdout.isatty():
            return
        now = time.time()
        if not self.visible and now - self.start_time >= 0.5:
            self.visible = True
            self.console.show_cursor(False)
        if not self.visible or now - getattr(self, '_last', 0) < 0.08:
            return
        self._last = now
        frame = self.FRAMES_ASCII[self.idx % len(self.FRAMES_ASCII)]
        self.idx += 1
        line = f"\r  {frame} {self.text}"
        sys.stdout.write(f"\r{' ' * 50}\r{line}")
        sys.stdout.flush()
    
    def end(self):
        if self.visible and sys.stdout.isatty():
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()
            self.console.show_cursor(True)

class ThinkingSpinner:
    """Background spinner for LLM thinking."""
    
    def __init__(self, text="MohaMind is thinking..."):
        self.spinner = Spinner(text)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)
    
    def _spin(self):
        while not self._stop.is_set():
            self.spinner.step()
            time.sleep(0.08)
        self.spinner.end()
    
    def start(self):
        if not self._thread.is_alive():
            self._thread.start()
    
    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=0.2)
        self.spinner.end()
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, *args):
        self.stop()
```

#### 4. Interactive Input with Autocomplete (Aider Pattern)

```python
from prompt_toolkit.shortcuts import PromptSession, CompleteStyle
from prompt_toolkit.completion import Completer, Completion, ThreadedCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

class MohaMindCompleter(Completer):
    COMMANDS = ["/help", "/status", "/memory", "/calendar", "/briefing", "/quit"]
    
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            word = text.split()[-1] if text.split() else text
            for cmd in self.COMMANDS:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(word))

class MohaMindIO:
    def __init__(self):
        self.console = Console()
        self.session = PromptSession(
            history=FileHistory("~/.mohamind/history"),
            style=Style.from_dict({"": "cyan"}),
        )
        self.completer = ThreadedCompleter(MohaMindCompleter())
        self.kb = KeyBindings()
        
        @self.kb.add("escape", "enter")
        def _(event):
            event.current_buffer.insert_text("\n")
    
    def get_input(self, prompt="moha> "):
        return self.session.prompt(
            prompt,
            completer=self.completer,
            complete_style=CompleteStyle.MULTI_COLUMN,
            key_bindings=self.kb,
        )
    
    def tool_output(self, msg, bold=False):
        self.console.print(msg, style="bold" if bold else None)
    
    def tool_error(self, msg):
        self.console.print(msg, style="bold red")
    
    def assistant_output(self, msg):
        self.console.print(Markdown(msg, style="cyan", code_theme="monokai"))
    
    def confirm(self, question):
        return self.session.prompt(f"{question} [y/N] ").lower() == "y"
```

#### 5. Tool Status Indicators

```python
from rich.panel import Panel
from rich.text import Text

class ToolStatus:
    INDICATORS = {
        "reading": ("📖", "Reading"),
        "editing": ("✏️", "Editing"),
        "running": ("▶", "Running"),
        "thinking": ("🧠", "Thinking"),
        "calendar": ("📅", "Calendar"),
        "memory": ("💾", "Memory"),
        "telegram": ("📨", "Telegram"),
        "done": ("✓", "Done"),
        "error": ("✗", "Error"),
    }
    
    def __init__(self, console):
        self.console = console
    
    def show(self, tool, detail=""):
        icon, label = self.INDICATORS.get(tool, ("●", tool))
        text = Text()
        text.append(f"  {icon} ", style="bold")
        text.append(label, style="bold cyan")
        if detail:
            text.append(f"  {detail}", style="dim")
        self.console.print(text)
```

---

## 8. "Premium" Feel Checklist

### Must-Have
- [x] **Rich banner/splash** on startup
- [x] **Streaming markdown** for LLM responses (not line-by-line)
- [x] **Custom spinner** (braille dots or scanning bar)
- [x] **Color-coded output**: assistant=cyan, errors=red, tools=green
- [x] **Autocomplete** with slash commands
- [x] **History** persisted to file
- [x] **Graceful fallback** for dumb terminals
- [x] **NO_COLOR** support

### Nice-to-Have
- [ ] **Sound/bell** notification when LLM finishes
- [ ] **OS notifications** (terminal-notifier / notify-send)
- [ ] **Token/cost tracking** display
- [ ] **Rich panels** for grouped output
- [ ] **Syntax highlighting** for code blocks
- [ ] **File status display** (which memory files are loaded)
- [ ] **Multiline mode** toggle
- [ ] **External editor** integration (Ctrl+X Ctrl+E)

### Advanced (Textual TUI mode)
- [ ] **Full TUI mode** with split panes
- [ ] **Chat history sidebar**
- [ ] **Tool output in separate panel**
- [ ] **Command palette** (Ctrl+P)
- [ ] **Settings UI**

---

## 9. Comparison Summary

| Feature | Aider | OpenHands | Codex | Claude Code |
|---------|-------|-----------|-------|-------------|
| Language | Python | Python/TS | Rust | Node.js |
| CLI Framework | prompt_toolkit | Custom | Rust crossterm | ink (React) |
| Output Library | rich | rich | Custom | Custom |
| Spinner | Custom | rich.status | Custom | Custom |
| Streaming | rich.live | rich.live | Custom | Custom |
| Autocomplete | prompt_toolkit | Custom | Custom | Custom |
| Alternate Screen | No | No | Yes | No |
| Interactive Mode | Yes | Yes | Yes | Yes |
| Headless Mode | Yes (--yes) | Yes | Yes | Yes |
| Markdown Output | rich.markdown | rich.markdown | Custom | Custom |

---

## 10. Recommended Implementation Priority

### Phase 1: Core CLI (Week 1)
1. `cli/io.py` - InputOutput class with rich + prompt_toolkit
2. `cli/spinner.py` - Custom braille spinner
3. `cli/app.py` - Main entry with banner, input loop
4. `cli/theme.py` - Color definitions

### Phase 2: Streaming & Tools (Week 2)
5. `cli/mdstream.py` - Streaming markdown renderer
6. `cli/commands.py` - Slash commands (/help, /status, /memory)
7. `cli/completions.py` - Autocomplete
8. Tool status indicators

### Phase 3: Polish (Week 3)
9. Onboarding wizard (first-run setup)
10. Session history & resume
11. Notifications (bell + OS)
12. Headless/non-interactive mode
