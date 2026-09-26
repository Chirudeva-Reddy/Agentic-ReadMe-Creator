"""Model Context Protocol (MCP) server for Agentic ReadMe Creator.

Implements JSON-RPC 2.0 stdio transport (protocol version 2024-11-05) for seamless
integration with Claude Desktop, Claude Code, Cursor, ChatGPT, and MCP clients.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

from agentic_readme.core.models import (
    FactsLedger,
    FindingSeverity,
    StorySpec,
    VerificationReport,
)
from agentic_readme.core.runner import PipelineRunner, contract_path
from agentic_readme.verify.claim_auditor import ClaimAuditor
from agentic_readme.verify.render_checker import RenderChecker
from agentic_readme.verify.voice_editor import VoiceEditor

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {
    "name": "agentic-readme",
    "version": "0.1.0",
}

TOOLS: List[Dict[str, Any]] = [
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
                    "description": "Automatically approve Phase 0 contract gate (default: true)",
                    "default": True,
                },
            },
        },
    },
]


def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool by name and return text content and error status."""
    try:
        if name == "agentic_readme_audit":
            readme_path = Path(arguments.get("readme_path", "README.md"))
            facts_file = Path(arguments.get("facts_file") or contract_path(readme_path.parent, "facts.json"))

            if not readme_path.exists():
                return {"isError": True, "content": [{"type": "text", "text": f"Error: README file not found: {readme_path}"}]}
            if not facts_file.exists():
                return {"isError": True, "content": [{"type": "text", "text": f"Error: Facts file not found: {facts_file}"}]}

            ledger = FactsLedger.load(facts_file)
            auditor = ClaimAuditor(ledger)
            render_checker = RenderChecker(readme_path.parent)
            voice_editor = VoiceEditor()

            report = VerificationReport()
            auditor.audit(readme_path, report=report)
            render_checker.check(readme_path, report=report)
            voice_editor.check(readme_path, report=report)

            status = "PASSED" if report.passed else "FAILED"
            summary_lines = [
                f"Audit Result: {status}",
                f"Facts Checked: {report.facts_checked}",
                f"Fatal Errors: {report.fatal_count}",
                f"Warnings: {report.warning_count}",
            ]
            if report.findings:
                summary_lines.append("\nFindings:")
                for f in report.findings:
                    summary_lines.append(f"- [{f.severity.value}] {f.category.value}: {f.message} (Location: {f.location or 'general'})")

            return {"isError": not report.passed, "content": [{"type": "text", "text": "\n".join(summary_lines)}]}

        elif name == "agentic_readme_ground":
            repo_path = Path(arguments.get("repo_path", "."))
            audience = arguments.get("audience")
            hook = arguments.get("hook")

            runner = PipelineRunner(repo_path, output_dir=repo_path)
            story, ledger = runner.phase_0_ground(target_audience=audience, custom_hook=hook)

            out_text = (
                f"Phase 0 Grounding Complete:\n"
                f"- Repository: {story.repo_name}\n"
                f"- Facts Extracted: {len(ledger.facts)}\n"
                f"- Contracts Generated: {contract_path(repo_path, 'story.yaml')}, {contract_path(repo_path, 'facts.json')}\n"
                f"- Hook: {story.hook}"
            )
            return {"isError": False, "content": [{"type": "text", "text": out_text}]}

        elif name == "agentic_readme_produce":
            dir_path = Path(arguments.get("dir_path", "."))
            story_file = contract_path(dir_path, "story.yaml")
            facts_file = contract_path(dir_path, "facts.json")

            if not story_file.exists() or not facts_file.exists():
                return {"isError": True, "content": [{"type": "text", "text": f"Error: story.yaml or facts.json missing in directory: {dir_path}"}]}

            story = StorySpec.load_yaml(story_file)
            ledger = FactsLedger.load(facts_file)
            runner = PipelineRunner(dir_path, output_dir=dir_path)
            assets = runner.phase_1_produce(story, ledger)

            diagram_files = [str(p) for p in assets["diagrams"].values()]
            demo_files = [str(assets["demo"]["tape_file"]), str(assets["demo"]["hero_asset"])]
            video_files = [str(assets["video"]["spec_file"]), str(assets["video"]["scene_table"])]

            out_text = (
                f"Phase 1 Production Complete:\n"
                f"- Candidate README: {assets['readme']}\n"
                f"- Diagrams: {diagram_files}\n"
                f"- Demo Assets: {demo_files}\n"
                f"- Video Spec: {video_files}"
            )
            return {"isError": False, "content": [{"type": "text", "text": out_text}]}

        elif name == "agentic_readme_verify":
            dir_path = Path(arguments.get("dir_path", "."))
            facts_file = contract_path(dir_path, "facts.json")
            if not facts_file.exists():
                return {"isError": True, "content": [{"type": "text", "text": f"Error: facts.json missing in directory: {dir_path}"}]}

            story_file = contract_path(dir_path, "story.yaml")
            story = StorySpec.load_yaml(story_file) if story_file.exists() else None
            ledger = FactsLedger.load(facts_file)

            runner = PipelineRunner(dir_path, output_dir=dir_path)
            report, passed = runner.phase_2_verify(story, ledger)

            status = "PASSED" if passed else "FAILED"
            summary_lines = [
                f"Phase 2 Verification {status}: {report.facts_checked} facts checked, {report.fatal_count} fatal findings, {report.warning_count} warnings.",
            ]
            if report.findings:
                summary_lines.append("\nFindings:")
                for f in report.findings:
                    summary_lines.append(f"- [{f.severity.value}] {f.category.value}: {f.message} (Location: {f.location or 'general'})")

            return {"isError": not passed, "content": [{"type": "text", "text": "\n".join(summary_lines)}]}

        elif name == "agentic_readme_run":
            repo_path = Path(arguments.get("repo_path", "."))
            auto_approve = arguments.get("auto_approve", True)

            runner = PipelineRunner(repo_path, output_dir=repo_path)
            res = runner.run_all(auto_approve_gate=auto_approve)

            report = res["verification_report"]
            status = "PASSED" if res["passed"] else "FAILED"
            summary_lines = [
                f"Full Pipeline Execution {status}:",
                f"- Repository: {res['story'].repo_name}",
                f"- Facts Extracted: {len(res['facts'].facts)} facts recorded in facts.json",
                f"- Media Assets: Candidate README, .excalidraw diagrams, VHS demo script, /brag video spec",
                f"- Verification: {report.facts_checked} facts checked, {report.fatal_count} fatal errors, {report.warning_count} warnings",
            ]
            if report.findings:
                summary_lines.append("\nVerification Findings:")
                for f in report.findings:
                    summary_lines.append(f"- [{f.severity.value}] {f.category.value}: {f.message} (Location: {f.location or 'general'})")

            return {"isError": not res["passed"], "content": [{"type": "text", "text": "\n".join(summary_lines)}]}

        else:
            return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}

    except Exception as exc:
        return {"isError": True, "content": [{"type": "text", "text": f"Tool execution failed: {exc}"}]}


def handle_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process a single JSON-RPC 2.0 request and return the JSON-RPC response."""
    method = req.get("method")
    req_id = req.get("id")

    # In JSON-RPC 2.0, notifications (no id member or id is None) MUST NOT receive a response
    if req_id is None:
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": SERVER_INFO,
            },
        }

    if method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {},
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS,
            },
        }

    if method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name", "")
        args = params.get("arguments", {})
        result = execute_tool(tool_name, args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        }

    # Method not found
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}",
        },
    }


def run_mcp_server(
    stdin_stream: Optional[TextIO] = None,
    stdout_stream: Optional[TextIO] = None,
) -> None:
    """Run JSON-RPC 2.0 stdio server loop."""
    real_stdout = stdout_stream or sys.stdout
    saved_stdout = sys.stdout

    try:
        # Redirect sys.stdout to sys.stderr so any stray prints or rich console
        # output does not corrupt the JSON-RPC stdio protocol stream
        if stdout_stream is None:
            sys.stdout = sys.stderr

        input_io = stdin_stream or sys.stdin
        output_io = real_stdout

        for raw_line in input_io:
            line = raw_line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as err:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {err}",
                    },
                }
                output_io.write(json.dumps(err_resp) + "\n")
                output_io.flush()
                continue

            resp = handle_request(req)
            if resp is not None:
                output_io.write(json.dumps(resp) + "\n")
                output_io.flush()
    finally:
        sys.stdout = saved_stdout
