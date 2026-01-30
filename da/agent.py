"""
Data Agent
==========

A self-learning data agent inspired by OpenAI's internal data agent.

The agent uses TWO types of knowledge bases:

1. KNOWLEDGE (static, curated):
   - Table metadata and schemas
   - Validated SQL query patterns
   - Business rules and definitions
   → Search this FIRST for table info, query patterns, data quality notes

2. LEARNINGS (dynamic, discovered):
   - Patterns discovered through interaction
   - Query fixes and corrections
   - Type gotchas and workarounds
   → Search this when queries fail or to avoid past mistakes
   → Save here when discovering new patterns

The 6 Layers of Context:
1. Table Metadata - Schema info from knowledge/tables/
2. Human Annotations - Business rules from knowledge/business/
3. Query Patterns - Validated SQL from knowledge/queries/
4. Institutional Knowledge - External context via MCP (optional)
5. Learnings - Discovered patterns (separate from knowledge)
6. Runtime Context - Live schema inspection via introspect_schema tool
"""

from os import getenv

from agno.agent import Agent
from agno.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.models.openai import OpenAIResponses
from agno.tools.mcp import MCPTools
from agno.tools.reasoning import ReasoningTools
from agno.tools.sql import SQLTools
from agno.vectordb.pgvector import PgVector, SearchType

from da.context.business_rules import BUSINESS_CONTEXT
from da.context.semantic_model import SEMANTIC_MODEL_STR
from da.tools import (
    create_introspect_schema_tool,
    create_learnings_tools,
    create_save_validated_query_tool,
)
from db import db_url, get_postgres_db

# ============================================================================
# Database & Knowledge Bases
# ============================================================================

# Database for storing agent sessions
agent_db = get_postgres_db()

# KNOWLEDGE: Static, curated information (table schemas, validated queries, business rules)
data_agent_knowledge = Knowledge(
    name="Data Agent Knowledge",
    vector_db=PgVector(
        db_url=db_url,
        table_name="data_agent_knowledge",
        search_type=SearchType.hybrid,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
    contents_db=get_postgres_db(contents_table="data_agent_knowledge_contents"),
    max_results=10,
)

# LEARNINGS: Dynamic, discovered patterns (query fixes, corrections, gotchas)
data_agent_learnings = Knowledge(
    name="Data Agent Learnings",
    vector_db=PgVector(
        db_url=db_url,
        table_name="data_agent_learnings",
        search_type=SearchType.hybrid,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
    contents_db=get_postgres_db(contents_table="data_agent_learnings_contents"),
    max_results=5,
)

# ============================================================================
# Create Tools
# ============================================================================

# Knowledge tools (save validated queries)
save_validated_query = create_save_validated_query_tool(data_agent_knowledge)

# Learnings tools (search/save discovered patterns)
search_learnings, save_learning = create_learnings_tools(data_agent_learnings)

# Runtime schema inspection (Layer 6)
introspect_schema = create_introspect_schema_tool(db_url)

# ============================================================================
# Instructions
# ============================================================================

INSTRUCTIONS = f"""\
You are a Data Agent. Your job is to provide **insights**, not just query results.

---

## TWO KNOWLEDGE SYSTEMS

1. **Knowledge** (static): Table schemas, validated queries, business rules
2. **Learnings** (dynamic): Patterns you've discovered, query fixes, gotchas

---

## WORKFLOW

### 1. SEARCH FIRST
Before writing SQL, ALWAYS:
- Search knowledge for validated patterns and table info (automatic)
- Call `search_learnings` for past fixes and gotchas

### 2. WRITE SQL
- LIMIT 50 default
- Never SELECT *
- ORDER BY for rankings
- No destructive queries

### 3. ON FAILURE
1. `search_learnings` for similar issues
2. `introspect_schema` to check actual types
3. Fix and retry
4. `save_learning` with what you discovered

### 4. PROVIDE INSIGHTS
Transform data into understanding:
- **Summarize**: "Hamilton won 11 of 21 races (52%)"
- **Compare**: "That's 7 more than second place"
- **Contextualize**: "His most dominant season since 2015"
- **Suggest**: "Want to compare with other dominant seasons?"

### 5. SAVE SUCCESS
Offer `save_validated_query` for queries that worked well.

---

## SAVE LEARNINGS WHEN YOU DISCOVER

- Type mismatches (position is TEXT not INTEGER)
- Date parsing (TO_DATE format requirements)
- Column naming quirks (driver_tag vs name_tag)
- User corrections

Always `search_learnings` first to avoid duplicates.

---

## SEMANTIC MODEL

{SEMANTIC_MODEL_STR}

---

{BUSINESS_CONTEXT}
"""

# ============================================================================
# Build Tools List
# ============================================================================

tools: list = [
    # SQL execution
    SQLTools(db_url=db_url),
    # Reasoning
    ReasoningTools(add_instructions=True),
    # Knowledge tools
    save_validated_query,
    # Learnings tools
    search_learnings,
    save_learning,
    # Runtime introspection (Layer 6)
    introspect_schema,
    # MCP tools for external knowledge (Layer 4)
    MCPTools(url=f"https://mcp.exa.ai/mcp?exaApiKey={getenv('EXA_API_KEY', '')}&tools=web_search_exa"),
]

# ============================================================================
# Create Agent
# ============================================================================

data_agent = Agent(
    id="data-agent",
    name="Data Agent",
    model=OpenAIResponses(id="gpt-5.2"),
    db=agent_db,
    # Knowledge (static - table schemas, validated queries)
    knowledge=data_agent_knowledge,
    search_knowledge=True,
    instructions=INSTRUCTIONS,
    tools=tools,
    # Context settings
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=5,
    read_tool_call_history=True,
    # Memory (user preferences)
    enable_agentic_memory=True,
    # Output
    markdown=True,
)

# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == "__main__":
    # Test queries to verify the agent works
    test_queries = [
        "Who won the most races in 2019?",
        "Which driver has won the most World Championships?",
    ]

    for query in test_queries:
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        print("=" * 60 + "\n")
        data_agent.print_response(query, stream=True)
        print("\n")
