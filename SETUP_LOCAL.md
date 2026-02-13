# Dash Local Setup — Ollama + SQL Server

This guide walks you through running Dash entirely on your local machine using Ollama for LLM inference and SQL Server for data queries. No data leaves your network.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Your Windows PC                 │
│                                                  │
│  ┌──────────┐   ┌───────────┐   ┌────────────┐ │
│  │  Ollama   │   │ SQL Server│   │  pgvector   │ │
│  │ qwen3:14b │   │  (mshist) │   │  (Docker)   │ │
│  │ :11434    │   │  :1433    │   │  :5532      │ │
│  └─────┬─────┘   └─────┬─────┘   └──────┬─────┘ │
│        │               │                │        │
│        └───────────┬────┘────────────────┘        │
│                    │                              │
│              ┌─────┴─────┐                        │
│              │   Dash    │                        │
│              │  Agent    │                        │
│              └───────────┘                        │
└─────────────────────────────────────────────────┘
```

**Three services:**

| Service | Purpose | Port |
|---------|---------|------|
| Ollama | LLM inference (qwen3:14b) | 11434 |
| SQL Server | Mining fleet data (mshist) | 1433 |
| PostgreSQL + pgvector | Agent state, knowledge, learnings | 5532 |

## Prerequisites

- **Docker Desktop** for Windows (runs pgvector)
- **Ollama** installed with models pulled
- **SQL Server** with mshist database accessible
- **Python 3.12+**
- **ODBC Driver 17 for SQL Server**

## Step 1: Start pgvector (Agent Database)

pgvector stores Dash's knowledge base, learnings, and chat history with vector embeddings for semantic search.

```powershell
cd desktop\dash
docker compose up -d
```

This starts a PostgreSQL + pgvector container on port **5532** (not 5432, to avoid conflicts with any existing PostgreSQL).

Verify it's running:
```powershell
docker ps
# Should show dash-db running on 0.0.0.0:5532->5432
```

## Step 2: Verify Ollama

Make sure Ollama is running and your models are available:

```powershell
# Check Ollama is responding
curl http://localhost:11434/api/tags

# Verify qwen3:14b is pulled
ollama list
```

You should see `qwen3:14b` in the list. If not:
```powershell
ollama pull qwen3:14b
```

## Step 3: Configure Environment

The `.env` file is pre-configured for your setup. Review it:

```
OLLAMA_HOST=http://desktop:11434
OLLAMA_MODEL=qwen3:14b

DATA_DB_DATABASE=mshist
DATA_DB_TRUSTED_CONNECTION=yes

AGENT_DB_PORT=5532
AGENT_DB_DATABASE=dash
```

**Key settings:**
- `OLLAMA_HOST`: Points to your Ollama instance. Use `http://localhost:11434` if running on the same machine.
- `DATA_DB_TRUSTED_CONNECTION=yes`: Uses Windows Authentication for SQL Server (no username/password needed).
- `AGENT_DB_PORT=5532`: Non-standard port to avoid conflicts.

## Step 4: Install Python Dependencies

```powershell
cd desktop\dash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

If `pyodbc` fails to install, ensure you have the ODBC Driver:
```powershell
# Check installed ODBC drivers
Get-OdbcDriver | Where-Object Name -like "*SQL Server*"
```

## Step 5: Load Knowledge Base

Load the table metadata, business rules, and validated queries into pgvector:

```powershell
python -m dash.scripts.load_knowledge
```

This populates the vector database with:
- Table metadata from `dash/knowledge/tables/`
- Business rules from `dash/knowledge/business/`
- Validated SQL queries from `dash/knowledge/queries/`

## Step 6: Run Dash

### CLI Mode (recommended for getting started)
```powershell
python -m dash
```

This starts an interactive chat where you can ask questions in plain English.

### Quick Test
```powershell
python -m dash.agents
```

Runs a single test query ("What tables are available?") to verify the full stack works.

### Web UI (AgentOS)
```powershell
python -m app.main
```

Then open `http://localhost:8000` in your browser for the AgentOS chat interface.

## Switching Models

To use a faster/smaller model, change `OLLAMA_MODEL` in `.env`:

```
OLLAMA_MODEL=qwen3:8b     # Faster, less accurate
OLLAMA_MODEL=qwen3:14b    # Best balance for your RTX 3060 12GB
```

Or set it at runtime:
```powershell
$env:OLLAMA_MODEL="qwen3:8b"
python -m dash
```

## Querying Other Databases

To query a different database (e.g., PAMS, PITRAMReporting):

```powershell
$env:DATA_DB_DATABASE="PAMS"
python -m dash
```

## Troubleshooting

**"Connection refused" to Ollama:**
- Check Ollama is running: `ollama list`
- Check the host in `.env` matches where Ollama is listening

**SQL Server connection fails:**
- Verify the instance name: `localhost\MSSQLSERVER01`
- If using a named instance, set `DATA_DB_HOST=localhost\MSSQLSERVER01` and remove `DATA_DB_PORT`
- Ensure Windows Authentication is enabled on the SQL Server instance

**pgvector connection fails:**
- Check Docker is running: `docker ps`
- Restart the container: `docker compose up -d`

**Ollama is slow / runs out of VRAM:**
- Switch to the 8B model: `OLLAMA_MODEL=qwen3:8b`
- Close other GPU-intensive applications
- Check GPU utilization: `nvidia-smi`

## What's Different from the Cloud Version

| Feature | Cloud (Claude) | Local (Ollama) |
|---------|---------------|----------------|
| LLM | Claude Sonnet 4 | qwen3:14b via Ollama |
| Data privacy | API calls to Anthropic | Everything on your machine |
| Web search | Exa MCP integration | Disabled (air-gapped) |
| Embeddings | FastEmbed (local) | FastEmbed (local) |
| Speed | Fast (cloud GPU) | Depends on your GPU |
| Cost | API usage fees | Free after hardware |
