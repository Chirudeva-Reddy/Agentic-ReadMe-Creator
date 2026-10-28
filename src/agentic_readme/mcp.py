"""The front door for AI assistants: a Model Context Protocol (MCP) server.

An MCP client (Claude Desktop, Claude Code, Cursor, ...) starts `agentic-readme mcp` and
talks to it over stdin/stdout, one JSON-RPC 2.0 message per line:

    -> {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    <- {"jsonrpc": "2.0", "id": 1, "result": {"tools": [...]}}

The assistant is the agent here: it decides which tool to call, reads the result, and
calls the next one. Each tool is a thin wrapper around a function in pipeline.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

from agentic_readme import __version__, pipeline
from agentic_readme.models import FactsLedger

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "agentic-readme", "version": __version__}

# What the assistant sees: each tool's name, what it does, and its arguments (JSON Schema).
TOOLS: list[dict[str, Any]] = [
    {
        "name": "agentic_readme_audit",
        "description": "Mechanically audit a README against facts.json ground truth ledger to detect fact drift, broken badges, leaked internal jargon, and voice issues.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "readme_path": {
                    "type": "string",
                    "description": "Path to README.md to audit (default: 'README.md')",
                    "default": "README.md",
                },
                "facts_file": {
                    "type": "string",
                    "description": "Path to facts.json ground truth ledger (default: .agentic-readme/facts.json next to the README)",
                },
            },
            "required": ["readme_path"],
        },
    },
    {
        "name": "agentic_readme_ground",
        "description": "Phase 0 Grounding: Inspect codebase, extract deterministic facts, and create story.yaml and facts.json contracts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to target repository (default: '.')",
                    "default": ".",
                },
                "audience": {
                    "type": "string",
                    "description": "Target audience description (e.g. 'Developers, ML engineers')",
                },
                "hook": {
                    "type": "string",
                    "description": "Custom pain-first 1-line hook",
                },
            },
        },
    },
    {
        "name": "agentic_readme_produce",
        "description": "Phase 1 Produce: Generate media assets (diagrams, VHS demo, video specs) and candidate README from locked contracts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dir_path": {
                    "type": "string",
                    "description": "Project directory; contracts are read from its .agentic-readme/ (default: '.')",
                    "default": ".",
                },
            },
        },
    },
    {
        "name": "agentic_readme_verify",
        "description": "Phase 2 Verify: Run Evaluator-Optimizer loop on generated assets to eliminate drift, render bugs, and AI slop.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dir_path": {
                    "type": "string",
                    "description": "Project directory containing README.md and .agentic-readme/facts.json (default: '.')",
                    "default": ".",
                },
            },
        },
    },
    {
        "name": "agentic_readme_run",
        "description": "Run the complete end-to-end 3-phase pipeline (Ground -> Produce -> Verify) on a repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to target repository (default: '.')",
                    "default": ".",
                },
                "auto_approve": {
                    "type": "boolean",
                    "description": "Skip the review gate (default: true). false stops after grounding so you can review story.yaml before producing.",
                    "default": True,
                },
            },
        },
    },
]


# --- tools ---------------------------------------------------------------------------

def _result(text: str, is_error: bool = False) -> dict[str, Any]:
    """An MCP tool result: one block of text, and whether the call failed."""
    return {"isError": is_error, "content": [{"type": "text", "text": text}]}


def _audit(args: dict) -> dict:
    readme = Path(args.get("readme_path", "README.md"))
    facts_file = Path(args.get("facts_file") or pipeline.contract_path(readme.parent, "facts.json"))
    if not readme.exists():
        return _result(f"Error: README file not found: {readme}", is_error=True)
    if not facts_file.exists():
        return _result(f"Error: Facts file not found: {facts_file}", is_error=True)

    report = pipeline.check(readme, FactsLedger.load(facts_file))
    lines = [
        f"Audit Result: {'PASSED' if report.passed else 'FAILED'}",
        f"Facts Checked: {report.facts_checked}",
        f"Fatal Errors: {report.fatal_count}",
        f"Warnings: {report.warning_count}",
    ]
    if report.findings:
        lines += ["\nFindings:"] + report.finding_lines()
    return _result("\n".join(lines), is_error=not report.passed)


def _ground(args: dict) -> dict:
    repo = Path(args.get("repo_path", "."))
    story, facts = pipeline.ground(repo, repo, args.get("audience"), args.get("hook"))
    return _result(
        f"Phase 0 Grounding Complete:\n"
        f"- Repository: {story.repo_name}\n"
        f"- Facts Extracted: {len(facts.facts)}\n"
        f"- Contracts Generated: {pipeline.contract_path(repo, 'story.yaml')}, {pipeline.contract_path(repo, 'facts.json')}\n"
        f"- Hook: {story.hook}"
    )


def _produce(args: dict) -> dict:
    project_dir = Path(args.get("dir_path", "."))
    story, facts = pipeline.load_contracts(project_dir)
    if story is None or facts is None:
        return _result(f"Error: story.yaml or facts.json missing in directory: {project_dir}", is_error=True)

    assets = pipeline.produce(story, facts, project_dir)
    diagrams = [str(p) for p in assets["diagrams"].values()]
    demo = [str(assets["demo"]["tape_file"]), str(assets["demo"]["hero_asset"])]
    video = [str(assets["video"]["spec_file"]), str(assets["video"]["scene_table"])]
    return _result(
        f"Phase 1 Production Complete:\n"
        f"- Candidate README: {assets['readme']}\n"
        f"- Diagrams: {diagrams}\n"
        f"- Demo Assets: {demo}\n"
        f"- Video Spec: {video}"
    )


def _verify(args: dict) -> dict:
    project_dir = Path(args.get("dir_path", "."))
    _story, facts = pipeline.load_contracts(project_dir)
    if facts is None:
        return _result(f"Error: facts.json missing in directory: {project_dir}", is_error=True)

    report, passed = pipeline.verify(project_dir, facts)
    lines = [
        f"Phase 2 Verification {'PASSED' if passed else 'FAILED'}: {report.facts_checked} facts checked, "
        f"{report.fatal_count} fatal findings, {report.warning_count} warnings.",
    ]
    if report.findings:
        lines += ["\nFindings:"] + report.finding_lines()
    return _result("\n".join(lines), is_error=not passed)


def _run(args: dict) -> dict:
    repo = Path(args.get("repo_path", "."))
    if not args.get("auto_approve", True):
        # The gate: stop after ground so the caller can review and edit story.yaml first.
        story, facts = pipeline.ground(repo, repo)
        return _result(
            f"Stopped at the review gate after grounding {story.repo_name} ({len(facts.facts)} facts).\n"
            f"Review {pipeline.contract_path(repo, 'story.yaml')} (edit the hook, problem and solution if needed), "
            f"then call agentic_readme_produce and agentic_readme_verify."
        )
    result = pipeline.run(repo, repo)
    report = result["report"]
    lines = [
        f"Full Pipeline Execution {'PASSED' if result['passed'] else 'FAILED'}:",
        f"- Repository: {result['story'].repo_name}",
        f"- Facts Extracted: {len(result['facts'].facts)} facts recorded in facts.json",
        f"- Media Assets: Candidate README, .excalidraw diagrams, VHS demo script, /brag video spec",
        f"- Verification: {report.facts_checked} facts checked, {report.fatal_count} fatal errors, {report.warning_count} warnings",
    ]
    if report.findings:
        lines += ["\nVerification Findings:"] + report.finding_lines()
    return _result("\n".join(lines), is_error=not result["passed"])


HANDLERS = {
    "agentic_readme_audit": _audit,
    "agentic_readme_ground": _ground,
    "agentic_readme_produce": _produce,
    "agentic_readme_verify": _verify,
    "agentic_readme_run": _run,
}


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run one tool. Errors become an error result, so the server never crashes."""
    handler = HANDLERS.get(name)
    if handler is None:
        return _result(f"Unknown tool: {name}", is_error=True)
    try:
        return handler(arguments)
    except Exception as exc:
        return _result(f"Tool execution failed: {exc}", is_error=True)


# --- JSON-RPC ------------------------------------------------------------------------

def _reply(request_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    """Answer one JSON-RPC request. Notifications (no id) get no answer, as the spec says."""
    method = request.get("method")
    request_id = request.get("id")
    if request_id is None:
        return None

    if method == "initialize":
        return _reply(request_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
    if method == "ping":
        return _reply(request_id, {})
    if method == "tools/list":
        return _reply(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = request.get("params", {})
        return _reply(request_id, execute_tool(params.get("name", ""), params.get("arguments", {})))

    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def run_mcp_server(stdin_stream: TextIO | None = None, stdout_stream: TextIO | None = None) -> None:
    """Read requests line by line from stdin and write each answer as one line to stdout."""
    output = stdout_stream or sys.stdout
    saved_stdout = sys.stdout
    try:
        # Anything else that prints (e.g. progress messages) goes to stderr, so it can't
        # corrupt the protocol stream.
        if stdout_stream is None:
            sys.stdout = sys.stderr

        for raw_line in stdin_stream or sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError as err:
                response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {err}"}}
            else:
                response = handle_request(request)
            if response is not None:
                output.write(json.dumps(response) + "\n")
                output.flush()
    finally:
        sys.stdout = saved_stdout
