"""
Database URL
============

Build database connection URLs from environment variables.

Supports two databases:
- DATA_DB_*: SQL Server for data queries (your business data)
- AGENT_DB_*: PostgreSQL for agent state and vector storage
"""

from os import getenv
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()


def build_data_db_url() -> str:
    """Build SQL Server connection URL for data queries.

    Supports both SQL Server Authentication and Windows Authentication.
    For Windows Auth, set DATA_DB_TRUSTED_CONNECTION=yes and leave USER/PASS empty.

    Environment variables:
        DATA_DB_DRIVER: SQLAlchemy driver (default: mssql+pyodbc)
        DATA_DB_HOST: Database host
        DATA_DB_PORT: Database port (default: 1433)
        DATA_DB_USER: Database user (leave empty for Windows Auth)
        DATA_DB_PASS: Database password (leave empty for Windows Auth)
        DATA_DB_DATABASE: Database name
        DATA_DB_ODBC_DRIVER: ODBC driver name (default: ODBC Driver 17 for SQL Server)
        DATA_DB_TRUSTED_CONNECTION: Set to 'yes' for Windows Authentication
    """
    driver = getenv("DATA_DB_DRIVER", "mssql+pyodbc")
    host = getenv("DATA_DB_HOST", "localhost")
    port = getenv("DATA_DB_PORT", "1433")
    user = getenv("DATA_DB_USER", "")
    password = quote(getenv("DATA_DB_PASS", ""), safe="")
    database = getenv("DATA_DB_DATABASE", "master")
    odbc_driver = getenv("DATA_DB_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
    trusted = getenv("DATA_DB_TRUSTED_CONNECTION", "").lower()

    if "pyodbc" in driver:
        odbc_driver_encoded = quote(odbc_driver, safe="")

        if trusted == "yes":
            # Windows Authentication — no user/pass in URL
            return (
                f"{driver}://@{host}:{port}/{database}"
                f"?driver={odbc_driver_encoded}"
                f"&Trusted_Connection=yes"
            )

        # SQL Server Authentication
        base_url = f"{driver}://{user}:{password}@{host}:{port}/{database}"
        return f"{base_url}?driver={odbc_driver_encoded}"

    # Non-pyodbc drivers
    base_url = f"{driver}://{user}:{password}@{host}:{port}/{database}"
    return base_url


def build_agent_db_url() -> str:
    """Build PostgreSQL connection URL for agent state and vector storage.

    Environment variables:
        AGENT_DB_DRIVER: SQLAlchemy driver (default: postgresql+psycopg)
        AGENT_DB_HOST: Database host (default: localhost)
        AGENT_DB_PORT: Database port (default: 5432)
        AGENT_DB_USER: Database user (default: ai)
        AGENT_DB_PASS: Database password (default: ai)
        AGENT_DB_DATABASE: Database name (default: ai)
    """
    driver = getenv("AGENT_DB_DRIVER", "postgresql+psycopg")
    host = getenv("AGENT_DB_HOST", "localhost")
    port = getenv("AGENT_DB_PORT", "5432")
    user = getenv("AGENT_DB_USER", "ai")
    password = quote(getenv("AGENT_DB_PASS", "ai"), safe="")
    database = getenv("AGENT_DB_DATABASE", "ai")

    return f"{driver}://{user}:{password}@{host}:{port}/{database}"


# Data database URL (SQL Server - for querying your data)
data_db_url = build_data_db_url()

# Agent database URL (PostgreSQL - for agent state and vector storage)
agent_db_url = build_agent_db_url()

# Legacy alias for backwards compatibility
db_url = agent_db_url
