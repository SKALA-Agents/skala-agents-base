# Agents

The core LangGraph logic now lives in Python modules so the notebook can stay thin and execution-focused.

Files:

- `models.py`: shared state and schema models
- `service.py`: retriever setup, agent nodes, policy node, graph assembly, and execution entrypoint
