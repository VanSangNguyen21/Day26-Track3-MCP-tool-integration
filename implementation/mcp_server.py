import json
import os
import sys
from typing import Any

from fastmcp import FastMCP

from db import SQLiteAdapter, ValidationError
from init_db import create_database

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab.db")

if not os.path.exists(DB_PATH):
    create_database(DB_PATH)

adapter = SQLiteAdapter(DB_PATH)

mcp = FastMCP("SQLite Lab MCP Server")


@mcp.tool(name="search")
def search(
    table: str,
    columns: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> str:
    """Search rows in a table with optional filters, ordering, and pagination.

    Args:
        table: Name of the table to search.
        columns: Optional list of column names to return. Defaults to all.
        filters: List of filter dicts with keys: column, operator, value.
                 Supported operators: eq, neq, gt, gte, lt, lte, like, in.
        limit: Maximum number of rows to return (max 1000).
        offset: Number of rows to skip.
        order_by: Column to order results by.
        descending: Sort in descending order if true.
    """
    try:
        result = adapter.search(table, columns, filters, limit, offset, order_by, descending)
        return json.dumps(result, indent=2, default=str)
    except ValidationError as e:
        return json.dumps({"error": e.message}, indent=2)


@mcp.tool(name="insert")
def insert(table: str, values: dict[str, Any]) -> str:
    """Insert a new row into a table.

    Args:
        table: Name of the table to insert into.
        values: Dict mapping column names to values for the new row.
    """
    try:
        result = adapter.insert(table, values)
        return json.dumps(result, indent=2, default=str)
    except ValidationError as e:
        return json.dumps({"error": e.message}, indent=2)


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: list[dict[str, Any]] | None = None,
    group_by: str | None = None,
) -> str:
    """Compute aggregate metrics on a table.

    Args:
        table: Name of the table.
        metric: Aggregate function. One of: count, avg, sum, min, max.
        column: Column to apply the metric on. Not required for count(*).
        filters: Optional list of filter dicts.
        group_by: Optional column to group results by.
    """
    try:
        result = adapter.aggregate(table, metric, column, filters, group_by)
        return json.dumps(result, indent=2, default=str)
    except ValidationError as e:
        return json.dumps({"error": e.message}, indent=2)


@mcp.resource("schema://database")
def database_schema() -> str:
    """Full database schema: tables and their columns."""
    tables = adapter.list_tables()
    result = {}
    for t in tables:
        result[t] = adapter.get_table_schema(t)
    return json.dumps(result, indent=2, default=str)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """Schema for a single table."""
    try:
        schema = adapter.get_table_schema(table_name)
        return json.dumps({table_name: schema}, indent=2, default=str)
    except ValidationError as e:
        return json.dumps({"error": e.message}, indent=2)


if __name__ == "__main__":
    transport = "stdio"
    if len(sys.argv) > 1:
        transport = sys.argv[1]
    mcp.run(transport=transport)
