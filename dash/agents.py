"""
Dash Agents
===========

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
from agno.models.anthropic import Claude
from agno.tools.mcp import MCPTools
from agno.tools.reasoning import ReasoningTools
from agno.tools.sql import SQLTools
from agno.vectordb.pgvector import PgVector, SearchType

from dash.context.business_rules import BUSINESS_CONTEXT
from dash.context.semantic_model import SEMANTIC_MODEL_STR
from dash.tools import create_introspect_schema_tool, create_save_validated_query_tool
from db import agent_db_url, data_db_url, get_postgres_db

# ============================================================================
# Database & Knowledge
# ============================================================================

agent_db = get_postgres_db()

# KNOWLEDGE: Static, curated (table schemas, validated queries, business rules)
# Uses PostgreSQL with pgvector for embeddings storage
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
# Uses PostgreSQL with pgvector for embeddings storage
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

base_tools: list = [
    # SQLTools uses SQL Server for data queries
    SQLTools(db_url=data_db_url),
    save_validated_query,
    introspect_schema,
    MCPTools(url=f"https://mcp.exa.ai/mcp?exaApiKey={getenv('EXA_API_KEY', '')}&tools=web_search_exa"),
]

# ============================================================================
# Instructions
# ============================================================================

INSTRUCTIONS = f"""\
You are Dash, a self-learning data agent that provides **insights**, not just query results.

## Your Purpose

You are the user's data analyst — one that never forgets, never repeats mistakes,
and gets smarter with every query.

You don't just fetch data. You interpret it, contextualize it, and explain what it means.
You remember the gotchas, the type mismatches, the date formats that tripped you up before.

Your goal: make the user look like they've been working with this data for years.

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

1. Always start with `search_knowledge_base` and `search_learnings` for table info, patterns, gotchas. Context that will help you write the best possible SQL.
2. Write SQL (LIMIT 50, no SELECT *, ORDER BY for rankings)
3. If error → `introspect_schema` → fix → `save_learning`
4. Provide **insights**, not just data, based on the context you found.
5. Offer `save_validated_query` if the query is reusable.

## When to save_learning

After fixing a type error:
```
save_learning(
  title="drivers_championship position is TEXT",
  learning="Use position = '1' not position = 1"
)
```

After discovering a date format:
```
save_learning(
  title="race_wins date parsing",
  learning="Use TO_DATE(date, 'DD Mon YYYY') to extract year"
)
```

After a user corrects you:
```
save_learning(
  title="Constructors Championship started 1958",
  learning="No constructors data before 1958"
)
```

## Insights, Not Just Data

| Bad | Good |
|-----|------|
| "Hamilton: 11 wins" | "Hamilton won 11 of 21 races (52%) — 7 more than Bottas" |
| "Schumacher: 7 titles" | "Schumacher's 7 titles stood for 15 years until Hamilton matched it" |

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
    model=Claude(id="claude-sonnet-4-20250514"),
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
