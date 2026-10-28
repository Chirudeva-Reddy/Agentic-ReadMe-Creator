"""Agentic ReadMe Creator: a README agent that can't invent numbers.

How the package fits together (read the files in this order):

    models.py        the data: FactsLedger (facts.json), StorySpec (story.yaml), VerificationReport
    pipeline.py      the deterministic steps on one page: ground -> produce -> verify
      ground/        step 1, read the repo
        project.py     what kind of project is it?          detect_project()
        facts.py       every number we can prove            collect_facts()
        story.py       first draft of story.yaml            build_story(), refresh_story()
      produce/       step 2, write the files
        readme.py      README.md                            write_readme()
        diagram.py     architecture diagrams                draw_diagrams()
        demo.py        terminal demo script + preview       make_demo()
        video.py       launch-video storyboard              make_storyboard()
      verify/        step 3, the guardrail
        claims.py      numbers vs facts.json, jargon        check_claims()
        rendering.py   will GitHub display it?              check_rendering()
        voice.py       wording and layout                   check_voice()
        fixer.py       fixes with one right answer          auto_fix()
    rules.py         the house-style word lists and limits the checks use
    cli.py           `agentic-readme` command (for humans and CI)
    mcp.py           MCP server (for AI assistants such as Claude Code or Cursor)
"""

__version__ = "0.1.0"
