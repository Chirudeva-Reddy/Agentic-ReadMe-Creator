"""LangChain, LangGraph, and LangSmith layer on top of the deterministic pipeline.

- llm.py          the Claude chat model (langchain-anthropic) used by the optional LLM steps
- story_chain.py  LangChain chain: prompt | model | structured output, checked against facts.json
- tools.py        the five pipeline tools as LangChain tools, plus a tool-calling agent
- graph.py        LangGraph StateGraph: ground -> polish -> human gate -> produce -> verify <-> fix
- evaluation.py   LangSmith dataset, target, and evaluators over the committed examples

Needs the optional dependencies: pip install -e ".[langchain]"
"""
