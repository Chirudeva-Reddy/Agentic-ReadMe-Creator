# Installation guide

Pick the track that fits you:

- **[Track A: never used a terminal](#track-a-never-used-a-terminal)**. Copy and paste, about 10 minutes.
- **[Track B: developers](#track-b-developers)**. One command.
- **[Track C: use it from an AI assistant](#track-c-use-it-from-an-ai-assistant)**. Claude Code, Claude Desktop, Cursor, or a Custom GPT.
- **[No install at all](#no-install-github-codespaces)**. Run it in your browser with GitHub Codespaces.

> [!WARNING]
> `agentic-readme run` and `agentic-readme produce` **overwrite `README.md`** in the folder you point them at. Commit or back up your current README first. `agentic-readme audit` only reads files and never changes them.

---

## Track A: never used a terminal

Every command below is one line. Copy it, paste it into the terminal, and press **Enter**.

### Step 1: Open a terminal

| Mac | Windows |
| :--- | :--- |
| Press <kbd>⌘ Cmd</kbd> + <kbd>Space</kbd>, type **Terminal**, press Enter. | Press the <kbd>⊞ Win</kbd> key, type **PowerShell**, press Enter. |

A window opens with a blinking cursor.

### Step 2: Install `uv`, a small helper that installs Python for you

**Mac:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Close the terminal window and open a new one** so it can find `uv`.

### Step 3: Install Agentic-ReadMe-Creator

```bash
uv tool install --python 3.12 git+https://github.com/Chirudeva-Reddy/Agentic-ReadMe-Creator.git
```

This downloads Python 3.12 if you don't have it. You don't need to install Python separately.

### Step 4: Check it worked

```bash
agentic-readme --help
```

You should see a list of commands (`ground`, `produce`, `verify`, `audit`, `run`, `mcp`). If you see `command not found`, close and reopen the terminal, then try again.

### Step 5: Run it on your project

Go into your project folder. The easiest way is to type `cd ` (with a space after it), drag the project folder from Finder or Explorer into the terminal window, and press Enter. Then:

```bash
agentic-readme run .
```

The `.` means "this folder". When it finishes, open `README.md` in the folder to see the result. `.agentic-readme/facts.json` lists every number the README uses and the file each one came from.

### Updating or uninstalling

```bash
uv tool upgrade agentic-readme-creator
```

```bash
uv tool uninstall agentic-readme-creator
```

---

## Track B: developers

Needs **Python 3.11+** and git.

```bash
pipx install git+https://github.com/Chirudeva-Reddy/Agentic-ReadMe-Creator.git
```

Or with uv: `uv tool install git+https://github.com/Chirudeva-Reddy/Agentic-ReadMe-Creator.git`.

### Hacking on it

```bash
git clone https://github.com/Chirudeva-Reddy/Agentic-ReadMe-Creator.git
cd Agentic-ReadMe-Creator
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

### Commands

| Command | What it does | Writes files? |
| :--- | :--- | :--- |
| `agentic-readme ground <repo> [--hook "..."] [--audience "..."]` | Reads the code, runs its tests, and writes `.agentic-readme/facts.json` + `story.yaml`. An existing `story.yaml` keeps your edits; only its numbers are refreshed. Delete it to start over. | Yes, contracts only |
| `agentic-readme produce <repo>` | Builds `README.md`, diagrams, demo tape, and video storyboard from those two files | Yes, overwrites `README.md` |
| `agentic-readme verify <repo>` | Checks every claim, link, and badge; auto-fixes drift; exits `1` on fatal findings | Only auto-fixes |
| `agentic-readme run <repo>` | `ground` → `produce` → `verify` in one go | Yes |
| `agentic-readme audit README.md --facts .agentic-readme/facts.json` | Read-only check of any README against a ledger | No |
| `agentic-readme mcp` | Starts the MCP stdio server | No |

The recommended loop is `ground`, then review `.agentic-readme/story.yaml` (especially `hook:`, which is the first line people read), then `produce`, then `verify`.

### Use it in CI

`audit` exits non-zero when the README drifts from the code, so it works as a pull-request gate:

```yaml
# .github/workflows/readme-audit.yml
name: README audit
on: [pull_request]
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install git+https://github.com/Chirudeva-Reddy/Agentic-ReadMe-Creator.git
      - run: agentic-readme audit README.md --facts .agentic-readme/facts.json
```

### Optional media tools

The pipeline writes scripts for these tools but doesn't need them installed:

- [VHS](https://github.com/charmbracelet/vhs) renders `assets/demo/demo.tape` into a real terminal GIF: `vhs assets/demo/demo.tape`.
- [/brag](https://github.com/latent-spaces/brag) turns `assets/video/brag_spec.json` into a launch video. It runs inside an AI agent, not the CLI. The Claude Code skill does this for you as Phase 3; see [LAUNCH_VIDEO.md](LAUNCH_VIDEO.md#making-one-for-your-own-repo).

---

## Track C: use it from an AI assistant

Install the CLI first (Track A or B), then connect it.

### Claude Code

Install it as a plugin, from inside Claude Code:

```text
/plugin marketplace add Chirudeva-Reddy/Agentic-ReadMe-Creator
/plugin install agentic-readme@agentic-readme
```

Or copy the skill file directly:

```bash
mkdir -p ~/.claude/skills/agentic-readme
curl -o ~/.claude/skills/agentic-readme/SKILL.md https://raw.githubusercontent.com/Chirudeva-Reddy/Agentic-ReadMe-Creator/main/skills/agentic-readme/SKILL.md
```

Restart Claude Code, open your project, and ask: *"Use agentic-readme to write and verify my README."*

### Claude Desktop or Cursor (MCP)

Add this to `claude_desktop_config.json` (Claude Desktop → Settings → Developer → Edit Config) or `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "agentic-readme": { "command": "agentic-readme", "args": ["mcp"] }
  }
}
```

The assistant gets five tools: `agentic_readme_ground`, `_produce`, `_verify`, `_run`, and `_audit`. More detail is in the [MCP guide](../integrations/mcp/README.md).

### ChatGPT / OpenAI

See the [GPT integration guide](../integrations/gpt/README.md) for function-calling schemas and a Custom GPT OpenAPI spec.

---

## No install: GitHub Codespaces

1. Open <https://codespaces.new/Chirudeva-Reddy/Agentic-ReadMe-Creator> and click **Create codespace**. You need a free GitHub account.
2. Once the editor loads, click in the terminal panel at the bottom and paste:

   ```bash
   pip install -e . && agentic-readme run examples/tip-splitter
   ```

3. Open `examples/tip-splitter/README.md` in the file tree and use the preview button (top right) to see the rendered result.

---

## Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| `command not found: agentic-readme` | Open a new terminal. With pipx, run `pipx ensurepath`; with uv, run `uv tool update-shell`. |
| `requires a different Python: 3.9.x` | Your Python is too old. Use the Track A command, which pulls Python 3.12 automatically. |
| Test count is `0` or missing | The tool looks for `tests/` or `test/` (pytest), `*.test.js` / `*.spec.js` (Node), or `#[test]` (Rust). |
| `Badge links to missing evidence target` | A badge points to a file that doesn't exist. Add the file (e.g. `LICENSE`) or remove the badge. |
| README came out generic | Edit `hook:` in `.agentic-readme/story.yaml` (or pass `--hook` to `ground`), then run `produce` again. |
