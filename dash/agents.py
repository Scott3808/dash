"""
Dash Agents (Local Ollama Edition)
===================================

Connects to a local Ollama instance for LLM inference and SQL Server for data.
No API keys required — everything runs on your machine.

Test: python -m dash.agents
"""

from os import getenv

from agno.agent import Agent
from agno.knowledge import Knowledge
from agno.knowledge.embedder.fastembed import FastEmbedEmbedder
from agno.learn import (
    LearnedKnowledgeConfig,
    LearningMachine,
    LearningMode,
    UserMemoryConfig,
    UserProfileConfig,
)
from agno.models.ollama import Ollama
from agno.tools.reasoning import ReasoningTools
from agno.tools.sql import SQLTools
from agno.vectordb.pgvector import PgVector, SearchType

from dash.context.business_rules import BUSINESS_CONTEXT
from dash.context.semantic_model import SEMANTIC_MODEL_STR
from dash.tools import create_introspect_schema_tool, create_save_validated_query_tool
from db import agent_db_url, data_db_url, get_postgres_db

# ============================================================================
# Configuration
# ============================================================================

OLLAMA_HOST = getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = getenv("OLLAMA_MODEL", "qwen3:14b")

# ============================================================================
# Database & Knowledge
# ============================================================================

agent_db = get_postgres_db()

# KNOWLEDGE: Static, curated (table schemas, validated queries, business rules)
dash_knowledge = Knowledge(
    name="Dash Knowledge",
    vector_db=PgVector(
        db_url=agent_db_url,
        table_name="dash_knowledge",
        search_type=SearchType.hybrid,
        embedder=FastEmbedEmbedder(),
    ),
    contents_db=get_postgres_db(contents_table="dash_knowledge_contents"),
)

# LEARNINGS: Dynamic, discovered (error patterns, gotchas, user corrections)
dash_learnings = Knowledge(
    name="Dash Learnings",
    vector_db=PgVector(
        db_url=agent_db_url,
        table_name="dash_learnings",
        search_type=SearchType.hybrid,
        embedder=FastEmbedEmbedder(),
    ),
    contents_db=get_postgres_db(contents_table="dash_learnings_contents"),
)

# ============================================================================
# Tools
# ============================================================================

save_validated_query = create_save_validated_query_tool(dash_knowledge)
introspect_schema = create_introspect_schema_tool(data_db_url)

# MCP/Exa web search is excluded — this is a local-only, air-gapped setup.
# Add it back by uncommenting if you later want web research capability:
# from agno.tools.mcp import MCPTools
# MCPTools(url=f"https://mcp.exa.ai/mcp?exaApiKey={getenv('EXA_API_KEY', '')}&tools=web_search_exa"),

base_tools: list = [
    SQLTools(db_url=data_db_url),
    save_validated_query,
    introspect_schema,
]

# ============================================================================
# Instructions
# ============================================================================

INSTRUCTIONS = f"""\
You are Dash, a self-learning data agent for mining fleet operations.
You provide **insights**, not just query results.

## Your Purpose

You are the user's mining data analyst — one that never forgets, never repeats mistakes,
and gets smarter with every query.

You don't just fetch data. You interpret it, contextualize it, and explain what it means.
You remember the gotchas, the type mismatches, the column quirks that tripped you up before.

The database is a Caterpillar MineStar/Fleet database ("mshist") containing haul truck cycles,
delays, production events, equipment health/VIMS data, operator shifts, and fleet management data.

## Two Knowledge Systems

**Knowledge** (static, curated):
- Table schemas, validated queries, business rules
- Searched automatically before each response
- Add successful queries here with `save_validated_query`

**Learnings** (dynamic, discovered):
- Patterns YOU discover through errors and fixes
- Type gotchas, date formats, column quirks
- Search with `search_learnings`, save with `save_learning`

## Workflow

1. Always start with `search_knowledge_base` and `search_learnings` for table info, patterns, gotchas.
2. If unsure about a table's structure, use `introspect_schema` to check columns and types.
3. Write SQL (TOP 50, no SELECT *, ORDER BY for rankings).
4. If error → `introspect_schema` → fix → `save_learning`.
5. Provide **insights**, not just data.
6. Offer `save_validated_query` if the query is reusable.

## Key Tables in mshist

**Fact Tables:** CYCLE, CYCLEDELAY, DELAY, PRODUCTION_EVENT, HEALTH_EVENT, ALARM, OPERATORSHIFT
**Reference Views (V_ prefix):** V_MACHINE, V_PERSON, V_DESTINATION, V_MATERIAL, etc.

When exploring an unfamiliar table, always `introspect_schema` first to check column names and types.

## When to save_learning

After fixing any error — type mismatches, column name corrections, join patterns, date formats.
After a user corrects you — business logic, terminology, preferred metrics.
After discovering table relationships — how fact tables join to reference views.

## Insights, Not Just Data

| Bad | Good |
|-----|------|
| "Truck 301: 45 cycles" | "Truck 301 completed 45 cycles — 12% above fleet average, with 0 unplanned delays" |
| "Average load: 180t" | "Average payload 180t against a 200t target (90% fill factor) — possible loading issue" |

## SQL Rules (SQL Server / T-SQL)

- Use TOP 50 instead of LIMIT (e.g., SELECT TOP 50 column FROM table)
- Never SELECT * — specify columns
- ORDER BY for top-N queries
- No DROP, DELETE, UPDATE, INSERT
- Use CONVERT() or CAST() for date conversions, not TO_DATE()
- Use DATEPART() or YEAR()/MONTH()/DAY() for date extraction, not EXTRACT()
- Use + for string concatenation, not ||
- Use ISNULL() instead of COALESCE() when possible
- Use square brackets [column] for reserved words
- Use schema-qualified names if needed (e.g., dbo.CYCLE)

---

## SEMANTIC MODEL

{SEMANTIC_MODEL_STR}
---

{BUSINESS_CONTEXT}\
"""

# ============================================================================
# Create Agent
# ============================================================================

dash = Agent(
    name="Dash",
    model=Ollama(id=OLLAMA_MODEL, host=OLLAMA_HOST),
    db=agent_db,
    instructions=INSTRUCTIONS,
    # Knowledge (static)
    knowledge=dash_knowledge,
    search_knowledge=True,
    # Learning (provides search_learnings, save_learning, user profile, user memory)
    learning=LearningMachine(
        knowledge=dash_learnings,
        user_profile=UserProfileConfig(mode=LearningMode.AGENTIC),
        user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    ),
    tools=base_tools,
    # Context
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=5,
    markdown=True,
)

# Reasoning variant - adds multi-step reasoning capabilities
reasoning_dash = dash.deep_copy(
    update={
        "name": "Reasoning Dash",
        "tools": base_tools + [ReasoningTools(add_instructions=True)],
    }
)

if __name__ == "__main__":
    dash.print_response("What tables are available and what data do they contain?", stream=True)
