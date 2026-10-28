"""The LangGraph pipeline and the LangChain layer around it.

- graph.py        LangGraph: the pipeline graph (ground -> polish -> human gate -> parallel
                  producers -> evaluate <-> fix) and the produce / verify graphs
- llm.py          the Claude chat model (langchain-anthropic) used by polish and the agent
- story_chain.py  LangChain chain: prompt | model | structured output, checked against facts.json
- tools.py        the five pipeline tools as LangChain tools, plus a tool-calling agent
- evaluation.py   dataset, target, and evaluators, run locally, in LangSmith, or in Langfuse

Tracing to LangSmith and Langfuse lives in core/observability.py.
"""
