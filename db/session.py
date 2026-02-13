"""
Database Session
================

Database connection factories for AgentOS.

Uses two separate databases:
- PostgreSQL for agent state and vector storage (requires pgvector)
- SQL Server (or other) for data queries
"""

from agno.db.postgres import PostgresDb

from db.url import agent_db_url

DB_ID = "dash-db"


def get_postgres_db(contents_table: str | None = None) -> PostgresDb:
    """Create a PostgresDb instance for agent state/vector storage.

    Args:
        contents_table: Optional table name for storing knowledge contents.

    Returns:
        Configured PostgresDb instance.
    """
    if contents_table is not None:
        return PostgresDb(id=DB_ID, db_url=agent_db_url, knowledge_table=contents_table)
    return PostgresDb(id=DB_ID, db_url=agent_db_url)
