# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This repository is a Streamlit demo for a扫地机器人/扫拖机器人智能客服 agent. The core runtime combines:

- a LangChain agent (`create_agent`)
- a Chroma-backed RAG pipeline over local PDF/TXT knowledge files
- middleware-driven prompt switching for report-generation requests
- CSV-backed mock user usage data for monthly reports

## Common commands

There is no committed `requirements.txt`, `pyproject.toml`, lint config, or test framework config in this repository. Use the commands below for the entry points that do exist.

- Run the Streamlit chat UI:
  - `streamlit run app.py`
- Run the CLI smoke test harness:
  - `python test.py`
  - `python test.py "给我生成我的使用报告"`
- Stream directly from the agent layer without Streamlit:
  - `python agent/react_agent.py`
- Load/rebuild the vector store from local knowledge files:
  - `python -c "from rag.vector_store import VectorStoreService; VectorStoreService().load_document()"`
- Inspect retrieval behavior from the vector store module:
  - `python rag/vector_store.py`

## High-level architecture

### UI and execution flow

- `app.py` is the Streamlit entry point. It stores a single `ReactAgent` instance in `st.session_state` and streams responses into the chat UI.
- `agent/react_agent.py` is the orchestration hub. It builds the agent with:
  - model: `model.factor.chat_model`
  - system prompt: loaded from `prompts/main_prompt.txt`
  - tools: RAG + mock environment/report tools
  - middleware: logging and prompt switching

### Tooling and prompt switching

- `agent/tools/agent_tools.py` defines all agent-facing tools.
  - `rag_summarize(query)` delegates to the RAG service.
  - `fetch_external_data(user_id, month)` reads mock report data from `data/external/records.csv`.
  - `get_weather`, `get_user_location`, `get_user_id`, and `get_current_month` are demo stubs/randomizers, not real integrations.
  - `fill_context_for_report()` exists only to flip the runtime into report mode.
- `agent/tools/middleware.py` is what makes report generation special:
  - `monitor_tool` watches tool calls and sets `request.runtime.context["report"] = True` when `fill_context_for_report` is called.
  - `report_prompt_switch` is a `@dynamic_prompt` hook that swaps the agent prompt from the main prompt to `prompts/report_prompt.txt` when report mode is active.
- The prompt files themselves encode important behavior:
  - `prompts/main_prompt.txt` instructs the agent to use a ReAct-like tool workflow and requires a fixed tool order for report requests.
  - `prompts/report_prompt.txt` turns the agent into a report writer once report mode has been activated.
  - `prompts/rag_summarize.txt` constrains RAG answers to retrieved context only.

### RAG pipeline

- `rag/rag_service.py` constructs a singleton `RagSummarizeService` at import time.
- The RAG chain is:
  - retrieve documents from Chroma
  - format them into a single context string
  - pass through `PromptTemplate -> chat model -> StrOutputParser`
- `rag/vector_store.py` owns ingestion and retrieval.
  - Chroma persistence path comes from `config/chroma.yml` and currently points to `rag/chroma_db`.
  - Knowledge files are loaded from `data/`.
  - Only `.pdf` and `.txt` are accepted.
  - Duplicate ingestion is prevented with MD5 hashes stored in `md5.text`.
  - Retrieval count `k`, chunk size, overlap, and separators all come from `config/chroma.yml`.

### Config and model bootstrap

- `utils/config_handler.py` loads all YAML config files into module-level globals at import time:
  - `config/agent.yml`
  - `config/rag.yml`
  - `config/chroma.yml`
  - `config/prompts.yml`
- `model/factor.py` also initializes global model singletons at import time.
  - Chat model name preference is `config/agent.yml` first, then `config/rag.yml` fallback.
  - Embedding model follows the same pattern.
  - The error messages mention an environment variable fallback for `DASHSCOPE_API_KEY`, but the current code only reads the key from `config/agent.yml`.
- Because config and model objects are created during import, config changes generally require a fresh process to take effect.

### Utility layer

- `utils/path_tool.py` resolves project-root-relative paths; most modules depend on it.
- `utils/prompt_loader.py` reads raw prompt text using the YAML-configured prompt paths.
- `utils/file_handler.py` handles PDF/TXT loading, top-level file enumeration, and MD5 calculation.
- `utils/logger_handler.py` creates the shared logger and writes dated log files under `logs/`.

## Important repository-specific constraints

- Run Python commands from the repository root. The codebase relies on root-relative imports and has no package `__init__.py` files.
- The knowledge-file scan is non-recursive: `listdir_with_allowed_type()` only reads files directly inside `data/`, not nested folders.
- The active vector-store directory is the one configured in `config/chroma.yml` (`rag/chroma_db`), even though other `chroma_db` folders also exist in the repo.
- Monthly report data is cached in-process as a global dict after first load from `data/external/records.csv`.
- This is a demo-style codebase: weather, location, user ID, and current month are simulated rather than real external services.
