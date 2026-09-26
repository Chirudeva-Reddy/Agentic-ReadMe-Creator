"""End-to-end pipeline integration tests for Agentic ReadMe Creator."""

from pathlib import Path
from agentic_readme.core.runner import PipelineRunner


def test_full_pipeline_run_on_sample_repo(tmp_path: Path):
    """Run full 3-phase pipeline on a mock repository."""
    # 1. Prepare sample repository
    repo_dir = tmp_path / "sample_service"
    repo_dir.mkdir()

    (repo_dir / "pyproject.toml").write_text("""[project]
name = "sample_service"
version = "1.0.0"
requires-python = ">=3.11"
""", encoding="utf-8")

    (repo_dir / "LICENSE").write_text("MIT License\nPermission is hereby granted...", encoding="utf-8")

    src_dir = repo_dir / "src" / "sample_service"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "main.py").write_text("def run(): return 42\n", encoding="utf-8")

    tests_dir = repo_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("""
def test_one():
    assert True

def test_two():
    assert 2 == 2
""", encoding="utf-8")

    # 2. Run pipeline
    runner = PipelineRunner(repo_dir, output_dir=repo_dir)
    res = runner.run_all(auto_approve_gate=True)

    # 3. Assert Phase 0 contracts
    assert (repo_dir / ".agentic-readme" / "story.yaml").exists()
    assert (repo_dir / ".agentic-readme" / "facts.json").exists()
    assert res["facts"].get_fact("test_count").value == 2
    assert res["facts"].get_fact("license").value == "MIT"

    # 4. Assert Phase 1 assets
    assert (repo_dir / "assets" / "diagrams" / "architecture.excalidraw").exists()
    assert (repo_dir / "assets" / "diagrams" / "architecture.svg").exists()
    assert (repo_dir / "assets" / "diagrams" / "architecture-dark.svg").exists()
    assert (repo_dir / "assets" / "diagrams" / "architecture-static.svg").exists()
    assert (repo_dir / "assets" / "demo" / "demo.tape").exists()

    assert (repo_dir / "assets" / "demo" / "hero-demo.svg").exists()
    assert (repo_dir / "assets" / "video" / "brag_spec.json").exists()
    assert (repo_dir / "README.md").exists()

    # 5. Assert Phase 2 verification
    assert res["passed"] is True
    report = res["verification_report"]
    assert report.fatal_count == 0

    # 6. Check content of generated README
    readme_text = (repo_dir / "README.md").read_text(encoding="utf-8")
    assert '<h1 align="center">sample_service</h1>' in readme_text
    assert "tests-2%20passed" in readme_text
    assert "architecture.excalidraw" in readme_text
    assert "## Evidence & Ground Truth" in readme_text

    # 7. Assert MCP server and Agentic Skill integrations
    import json
    import yaml
    from agentic_readme.mcp import handle_request, TOOLS

    # Test MCP initialize
    init_res = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init_res["result"]["protocolVersion"] == "2024-11-05"
    assert init_res["result"]["serverInfo"]["name"] == "agentic-readme"

    # Test MCP tools/list
    tools_res = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tool_names = [t["name"] for t in tools_res["result"]["tools"]]
    assert "agentic_readme_audit" in tool_names
    assert "agentic_readme_ground" in tool_names
    assert "agentic_readme_produce" in tool_names
    assert "agentic_readme_verify" in tool_names
    assert "agentic_readme_run" in tool_names

    # Test MCP tools/call audit on the generated sample repo
    audit_res = handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "agentic_readme_audit",
            "arguments": {
                "readme_path": str(repo_dir / "README.md"),
            },
        },
    })
    assert audit_res["result"]["isError"] is False
    assert "Audit Result: PASSED" in audit_res["result"]["content"][0]["text"]

    # Verify Claude skill definition file exists and has valid frontmatter
    skill_file = Path(__file__).resolve().parent.parent / "skills" / "agentic-readme" / "SKILL.md"
    assert skill_file.exists()
    content = skill_file.read_text(encoding="utf-8")
    parts = content.split("---")
    frontmatter = yaml.safe_load(parts[1])
    assert frontmatter["name"] == "agentic-readme"
    assert "facts.json" in frontmatter["description"]

    # Verify mcp.json configuration
    mcp_config_file = Path(__file__).resolve().parent.parent / "integrations" / "mcp" / "mcp.json"
    assert mcp_config_file.exists()
    mcp_cfg = json.loads(mcp_config_file.read_text(encoding="utf-8"))
    assert "agentic-readme" in mcp_cfg["mcpServers"]
    assert mcp_cfg["mcpServers"]["agentic-readme"]["args"] == ["mcp"]

    # Verify OpenAI tools schema
    openai_tools_file = Path(__file__).resolve().parent.parent / "integrations" / "gpt" / "openai_tools.json"
    assert openai_tools_file.exists()
    gpt_tools = json.loads(openai_tools_file.read_text(encoding="utf-8"))
    assert len(gpt_tools) == 5
    gpt_tool_names = [t["function"]["name"] for t in gpt_tools]
    assert "agentic_readme_audit" in gpt_tool_names


def test_mcp_notifications_and_errors():
    """Verify that JSON-RPC notifications receive no response and unknown methods return -32601."""
    from agentic_readme.mcp import handle_request

    # Notifications (no id) must return None
    assert handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert handle_request({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {}}) is None
    assert handle_request({"jsonrpc": "2.0", "method": "some_random_event"}) is None

    # Unknown method with id must return -32601 error
    err_res = handle_request({"jsonrpc": "2.0", "id": 99, "method": "unknown_tool"})
    assert err_res["id"] == 99
    assert err_res["error"]["code"] == -32601


def test_mcp_server_stdio_stream_isolation(tmp_path: Path):
    """Verify that run_mcp_server outputs strictly valid JSON-RPC and does not corrupt stdout."""
    import io
    import json
    from agentic_readme.mcp import run_mcp_server

    input_data = (
        '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}\n'
        '{"jsonrpc": "2.0", "method": "notifications/initialized"}\n'
        '{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}\n'
    )
    stdin_stream = io.StringIO(input_data)
    stdout_stream = io.StringIO()

    run_mcp_server(stdin_stream=stdin_stream, stdout_stream=stdout_stream)

    lines = [line.strip() for line in stdout_stream.getvalue().splitlines() if line.strip()]
    assert len(lines) == 2  # initialize response and tools/list response; notification ignored

    # Every single line must parse as valid JSON
    msg1 = json.loads(lines[0])
    assert msg1["id"] == 1
    assert "protocolVersion" in msg1["result"]

    msg2 = json.loads(lines[1])
    assert msg2["id"] == 2
    assert len(msg2["result"]["tools"]) == 5


def test_pipeline_runner_missing_readme_graceful_handling(tmp_path: Path):
    """Verify that phase_2_verify reports a fatal finding instead of crashing when README.md is missing."""
    from agentic_readme.core.models import FactsLedger
    from agentic_readme.core.runner import PipelineRunner

    ledger = FactsLedger(repo_name="empty-repo")
    runner = PipelineRunner(tmp_path, output_dir=tmp_path)

    report, passed = runner.phase_2_verify(None, ledger)
    assert passed is False
    assert report.fatal_count == 1
    assert "README.md does not exist" in report.findings[0].message




def test_contract_path_falls_back_to_legacy_root(tmp_path):
    from agentic_readme.core.runner import contract_path

    assert contract_path(tmp_path, "facts.json") == tmp_path / ".agentic-readme" / "facts.json"
    (tmp_path / "facts.json").write_text("{}")
    assert contract_path(tmp_path, "facts.json") == tmp_path / "facts.json"
    (tmp_path / ".agentic-readme").mkdir()
    (tmp_path / ".agentic-readme" / "facts.json").write_text("{}")
    assert contract_path(tmp_path, "facts.json") == tmp_path / ".agentic-readme" / "facts.json"
