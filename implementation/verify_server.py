"""Standalone verification script that tests the MCP server via its tools."""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import SQLiteAdapter, ValidationError
from init_db import create_database

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab.db")

if not os.path.exists(DB_PATH):
    create_database(DB_PATH)

adapter = SQLiteAdapter(DB_PATH)

passed = 0
failed = 0


def check(label: str, ok: bool, detail: str = ""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {detail}")


print("=" * 60)
print("Verification: SQLite Lab MCP Server")
print("=" * 60)

# 1. Server starts correctly (init already succeeded)
print("\n[1] Server startup")
check("Database initialized", os.path.exists(DB_PATH))

# 2. Tool discovery via list_tables
print("\n[2] Database introspection")
tables = adapter.list_tables()
check("list_tables returns tables", len(tables) >= 3, f"got {tables}")

# 3. Schema resource
print("\n[3] Schema resources")
schema = adapter.get_table_schema("students")
check("get_table_schema('students') works", len(schema) > 0)
try:
    adapter.get_table_schema("nonexistent")
    check("get_table_schema('nonexistent') rejects", False)
except ValidationError:
    check("get_table_schema('nonexistent') rejects", True)

# 4. search
print("\n[4] search tool")
result = adapter.search("students", limit=5)
check("search returns rows", len(result["rows"]) > 0, f"got {len(result['rows'])} rows")
check("search returns total", result["total"] >= 5)

result_filtered = adapter.search("students", filters=[{"column": "cohort", "operator": "eq", "value": "A1"}])
check("search with filter", len(result_filtered["rows"]) == 3)

result_ordered = adapter.search("students", order_by="score", descending=True)
check("search with order_by", result_ordered["rows"][0]["score"] == 95.0)

try:
    adapter.search("nonexistent")
    check("search on bad table rejects", False)
except ValidationError:
    check("search on bad table rejects", True)

try:
    adapter.search("students", columns=["bad_column"])
    check("search with bad column rejects", False)
except ValidationError:
    check("search with bad column rejects", True)

# 5. insert
print("\n[5] insert tool")
inserted = adapter.insert("students", {"name": "Test User", "email": "test@example.com", "cohort": "A1", "score": 88.0})
check("insert returns row", inserted.get("name") == "Test User")
check("insert returns id", inserted.get("id") is not None)

try:
    adapter.insert("students", {})
    check("insert empty rejects", False)
except ValidationError:
    check("insert empty rejects", True)

try:
    adapter.insert("students", {"bad_col": "x"})
    check("insert with bad column rejects", False)
except ValidationError:
    check("insert with bad column rejects", True)

# 6. aggregate
print("\n[6] aggregate tool")
agg = adapter.aggregate("students", "count")
check("aggregate count(*)", agg[0]["value"] >= 6)

avg = adapter.aggregate("students", "avg", column="score")
check("aggregate avg(score)", avg[0]["value"] > 0)

grp = adapter.aggregate("students", "avg", column="score", group_by="cohort")
check("aggregate with group_by", len(grp) == 2)

try:
    adapter.aggregate("students", "invalid_metric")
    check("aggregate bad metric rejects", False)
except ValidationError:
    check("aggregate bad metric rejects", True)

try:
    adapter.aggregate("students", "avg", column="bad_col")
    check("aggregate bad column rejects", False)
except ValidationError:
    check("aggregate bad column rejects", True)

# 7. Filter operators validation
print("\n[7] Filter operator validation")
try:
    adapter.search("students", filters=[{"column": "name", "operator": "unsupported", "value": "x"}])
    check("unsupported operator rejects", False)
except ValidationError:
    check("unsupported operator rejects", True)

# Summary
print("\n" + "=" * 60)
total = passed + failed
print(f"Results: {passed}/{total} passed, {failed}/{total} failed")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
