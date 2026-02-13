"""Runtime schema inspection (Layer 6).

Supports SQL Server (T-SQL) syntax: uses square brackets for identifiers,
TOP instead of LIMIT, and includes views in table listings.
"""

from agno.tools import tool
from agno.utils.log import logger
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DatabaseError, OperationalError


def _is_mssql(db_url: str) -> bool:
    """Check if the database URL points to SQL Server."""
    return "mssql" in db_url.lower()


def create_introspect_schema_tool(db_url: str):
    """Create introspect_schema tool with database connection."""
    engine = create_engine(db_url)
    mssql = _is_mssql(db_url)

    @tool
    def introspect_schema(
        table_name: str | None = None,
        include_sample_data: bool = False,
        sample_limit: int = 5,
    ) -> str:
        """Inspect database schema at runtime.

        Args:
            table_name: Table or view to inspect. If None, lists all tables and views.
            include_sample_data: Include sample rows.
            sample_limit: Number of sample rows.
        """
        try:
            insp = inspect(engine)

            if table_name is None:
                # List all tables AND views (mining DBs use V_ views extensively)
                tables = sorted(insp.get_table_names())
                views = sorted(insp.get_view_names())

                if not tables and not views:
                    return "No tables or views found."

                lines = ["## Tables", ""]
                for t in tables:
                    try:
                        with engine.connect() as conn:
                            quoted = f"[{t}]" if mssql else f'"{t}"'
                            count = conn.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar()
                            lines.append(f"- **{t}** ({count:,} rows)")
                    except (OperationalError, DatabaseError):
                        lines.append(f"- **{t}**")

                if views:
                    lines.extend(["", "## Views", ""])
                    for v in views:
                        lines.append(f"- **{v}**")

                return "\n".join(lines)

            # Inspect specific table or view
            all_tables = insp.get_table_names()
            all_views = insp.get_view_names()
            all_objects = all_tables + all_views

            if table_name not in all_objects:
                # Case-insensitive fallback (SQL Server is case-insensitive)
                match = next((o for o in all_objects if o.lower() == table_name.lower()), None)
                if match:
                    table_name = match
                else:
                    return f"Table/view '{table_name}' not found. Available: {', '.join(sorted(all_objects[:50]))}..."

            lines = [f"## {table_name}", ""]

            # Columns
            cols = insp.get_columns(table_name)
            if cols:
                lines.extend(["### Columns", "", "| Column | Type | Nullable |", "| --- | --- | --- |"])
                for c in cols:
                    nullable = "Yes" if c.get("nullable", True) else "No"
                    lines.append(f"| {c['name']} | {c['type']} | {nullable} |")
                lines.append("")

            # Primary key (tables only, views don't have PKs)
            if table_name in all_tables:
                pk = insp.get_pk_constraint(table_name)
                if pk and pk.get("constrained_columns"):
                    lines.append(f"**Primary Key:** {', '.join(pk['constrained_columns'])}")
                    lines.append("")

            # Sample data
            if include_sample_data:
                lines.append("### Sample")
                try:
                    with engine.connect() as conn:
                        quoted = f"[{table_name}]" if mssql else f'"{table_name}"'
                        if mssql:
                            sql = f"SELECT TOP {sample_limit} * FROM {quoted}"
                        else:
                            sql = f"SELECT * FROM {quoted} LIMIT {sample_limit}"
                        result = conn.execute(text(sql))
                        rows = result.fetchall()
                        col_names = list(result.keys())
                        if rows:
                            lines.append("| " + " | ".join(col_names) + " |")
                            lines.append("| " + " | ".join(["---"] * len(col_names)) + " |")
                            for row in rows:
                                vals = [str(v)[:30] if v else "NULL" for v in row]
                                lines.append("| " + " | ".join(vals) + " |")
                        else:
                            lines.append("_No data_")
                except (OperationalError, DatabaseError) as e:
                    lines.append(f"_Error: {e}_")

            return "\n".join(lines)

        except OperationalError as e:
            logger.error(f"Database connection failed: {e}")
            return f"Error: Database connection failed - {e}"
        except DatabaseError as e:
            logger.error(f"Database error: {e}")
            return f"Error: {e}"

    return introspect_schema
