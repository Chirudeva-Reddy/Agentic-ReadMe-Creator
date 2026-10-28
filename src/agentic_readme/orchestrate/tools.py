"""The pipeline's five tools as LangChain tools, and a Claude agent that calls them.

The tools are built from the MCP server's TOOLS list and run through the same
execute_tool(), so MCP clients, OpenAI function calling, and LangChain agents all share
one name, description, input schema, and implementation per tool.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from langchain_core.tools import BaseTool, StructuredTool, ToolException

from agentic_readme.mcp import TOOLS, execute_tool

AGENT_SYSTEM_PROMPT = """You write and check README files with the agentic-readme tools.

To create or refresh a README, call agentic_readme_run on the repository (or ground, produce, and verify one at a time when the user wants to review story.yaml in between). To check an existing README, call agentic_readme_audit. Report the verification result as the tool returned it, including fatal findings; never claim a README passed when the tool said it failed."""


def _tool_func(name: str) -> Callable[..., str]:
    def run(**arguments: Any) -> str:
        result = execute_tool(name, {k: v for k, v in arguments.items() if v is not None})
        text = "\n".join(block["text"] for block in result["content"])
        if result["isError"]:
            raise ToolException(text)
        return text

    return run


def build_tools() -> List[BaseTool]:
    """One StructuredTool per MCP tool. Errors go back to the model as the tool result."""
    return [
        StructuredTool.from_function(
            func=_tool_func(spec["name"]),
            name=spec["name"],
            description=spec["description"],
            args_schema=spec["inputSchema"],
            handle_tool_error=True,
        )
        for spec in TOOLS
    ]


def build_agent(model: Optional[Any] = None):
    """A LangChain tool-calling agent (compiled LangGraph graph) over the five tools."""
    from langchain.agents import create_agent

    if model is None:
        from agentic_readme.orchestrate.llm import default_chat_model
        model = default_chat_model()
    return create_agent(model, tools=build_tools(), system_prompt=AGENT_SYSTEM_PROMPT, name="readme-tools-agent")
