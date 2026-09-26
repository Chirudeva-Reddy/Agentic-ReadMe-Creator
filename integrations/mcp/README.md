# Model Context Protocol (MCP) Integration

`agentic-readme` includes a built-in Model Context Protocol (MCP) server operating over `stdio` using JSON-RPC 2.0 (specification `2024-11-05`).

Any MCP-compatible client (Claude Desktop, Cursor, ChatGPT Desktop, Zed, or agent harnesses) can invoke verification, grounding, asset production, and claim auditing directly as first-class tools.

---

## Exposed MCP Tools

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `agentic_readme_audit` | `readme_path` (str), `facts_file` (str) | Mechanically audit a README against a facts ledger for drift, broken badges, leaked jargon, and voice issues. |
| `agentic_readme_ground` | `repo_path` (str), `audience` (str), `hook` (str) | Phase 0 Grounding: Extract deterministic facts and generate `story.yaml` and `facts.json`. |
| `agentic_readme_produce` | `dir_path` (str) | Phase 1 Production: Generate diagrams, demo tape, video specs, and candidate README. |
| `agentic_readme_verify` | `dir_path` (str) | Phase 2 Verification: Run Evaluator-Optimizer loop on generated assets. |
| `agentic_readme_run` | `repo_path` (str), `auto_approve` (bool) | Full 3-phase automated pipeline execution (Ground -> Produce -> Verify). |

---

## Client Setup Guides

### 1. Claude Desktop

Add `agentic-readme` to your Claude Desktop configuration:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "agentic-readme": {
      "command": "agentic-readme",
      "args": ["mcp"]
    }
  }
}
```

> **Note**: If `agentic-readme` is installed in a virtual environment, specify the full path to the executable (e.g. `"/Users/yourname/.virtualenvs/readme/bin/agentic-readme"`).

### 2. Cursor IDE

In your project root, create or edit `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "agentic-readme": {
      "command": "agentic-readme",
      "args": ["mcp"]
    }
  }
}
```

Or configure via Cursor Settings -> Features -> MCP Servers.

### 3. Testing the MCP Server Directly

You can test stdio JSON-RPC interaction using `agentic-readme mcp`:

```bash
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}' | agentic-readme mcp
echo '{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}' | agentic-readme mcp
```
