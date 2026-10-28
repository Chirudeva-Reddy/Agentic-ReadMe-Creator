"""The LLM agent: a LangGraph tool loop on top of the deterministic pipeline.

    tools.py     what the model is allowed to do (and the guardrails)
    graph.py     the graph: ground -> agent <-> tools -> final_check
    evaluate.py  score the agent on examples/ with LangSmith
"""
