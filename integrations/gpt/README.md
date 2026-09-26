# GPT & OpenAI Tool Integrations

`agentic-readme` can be integrated into GPT-powered workflows through three primary methods:
1. **OpenAI Function Calling / Tools API** (Python / TypeScript SDK)
2. **ChatGPT Custom GPT Actions** (OpenAPI 3.1.0 schema)
3. **Model Context Protocol (MCP)** (Cursor, Claude, or MCP-enabled GPT clients)

---

## 1. OpenAI Function Calling (Tools API)

The tool definitions are specified in [`openai_tools.json`](openai_tools.json).

### Python Example

```python
import json
from pathlib import Path
from openai import OpenAI
from agentic_readme.mcp import execute_tool

client = OpenAI()

# Load verified tool schemas
tools_file = Path("integrations/gpt/openai_tools.json")
tools = json.loads(tools_file.read_text(encoding="utf-8"))

# Send message with tools enabled
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a technical documentation assistant. Use agentic-readme tools to verify all documentation claims against real facts."},
        {"role": "user", "content": "Audit our README.md against facts.json and report any fact drift or broken badges."}
    ],
    tools=tools,
    tool_choice="auto",
)

# Route and execute tool call
msg = response.choices[0].message
if msg.tool_calls:
    for tool_call in msg.tool_calls:
        func_name = tool_call.function.name
        func_args = json.loads(tool_call.function.arguments)
        
        # Execute tool via agentic-readme runner
        result = execute_tool(func_name, func_args)
        print(f"Tool {func_name} output:\n", result["content"][0]["text"])
```

---

## 2. ChatGPT Custom GPT Actions

If creating a Custom GPT in ChatGPT's GPT Builder:

1. Open your Custom GPT in the GPT Editor.
2. Under **Configure**, scroll down to **Actions** and click **Create new action**.
3. Import the OpenAPI specification from [`openapi.json`](openapi.json).
4. Point the server URL to your API gateway or local runner bridge.
5. In the GPT **Instructions**, add:
   > "You are an automated documentation verification engine. Before writing or editing any README, you must ground your claims in facts.json. Never invent numbers, test counts, or versions. Always run auditReadme to verify badges, test numbers, and evidence links."

---

## 3. Model Context Protocol (MCP)

For clients that connect via MCP (including ChatGPT Desktop MCP plugins, Cursor, and Claude Desktop), see the dedicated [MCP Configuration Guide](../mcp/README.md) or use [`mcp.json`](../mcp/mcp.json).
