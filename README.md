# Investment Analysis Report Service

This project builds an investment analysis report service that starts from a user-provided company list.
The service researches each company on the web, builds a company-specific RAG context, and generates Korean-language investment reports.
The current workflow is designed to produce Korean-language outputs.

## Project Structure

```text
.
├── agents/                 # Agent module notes and future extracted logic
├── notebooks/              # Main implementation notebook
├── outputs/                # Generated reports
├── prompts/                # Prompt templates
├── app.py                  # Thin entry helper
└── README.md
```

## Runtime

- Preferred Python: `3.11`
- Virtual environment: `.venv`
- Main implementation: `notebooks/investment_report_service.ipynb`

## Current Environment Note

The project is set up to run with the local `.venv` environment using Python 3.11.

## Suggested Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m ensurepip --upgrade
python -m pip install -U pip
python -m pip install jupyter notebook langchain langgraph langchain-community langchain-openai faiss-cpu sentence-transformers pydantic python-dotenv
```

## Workflow

1. Set one of `OPENAI_API_KEY`, `OPEN_AI_API_KEY`, or `OPEN_AI_API` in `.env` or the shell environment.
2. Activate the project virtual environment.
3. Run `python app.py "NVIDIA" "Groq" "SambaNova Systems"`.
4. Review generated Korean Markdown and JSON reports in `outputs/`.

## Current Graph

- Input company loading
- Market analysis
- Company web research and company-specific RAG context generation
- Investment supervisor orchestration node
- Technology evaluation agent
- Market evaluation agent
- Business evaluation agent
- Team evaluation agent
- Risk evaluation agent
- Competition evaluation agent
- Ranking node
- Policy node for `60점 이상 Top3 추천` vs `전체 보류`
- Final report or hold report generation

Architecture diagrams are documented in [architecture_mermaid.md](/Users/angj/AngJ/SKALA_Project/rag_project/docs/architecture_mermaid.md).
