"""Automated tests for the MCP server using the adapter directly."""

import os
import sys
import json
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import SQLiteAdapter, ValidationError
from init_db import SCHEMA_SQL, SEED_SQL


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.executescript(SEED_SQL)
    conn.commit()
    conn.close()
    return SQLiteAdapter(db_path)


class TestSearch:
    def test_search_all(self, db):
        result = db.search("students", limit=10)
        assert len(result["rows"]) == 5
        assert result["total"] == 5

    def test_search_with_filter(self, db):
        result = db.search("students", filters=[{"column": "cohort", "operator": "eq", "value": "A1"}])
        assert len(result["rows"]) == 3
        assert all(r["cohort"] == "A1" for r in result["rows"])

    def test_search_with_order(self, db):
        result = db.search("students", order_by="score", descending=True)
        assert result["rows"][0]["score"] == 95.0

    def test_search_with_columns(self, db):
        result = db.search("students", columns=["name", "score"])
        assert set(result["rows"][0].keys()) == {"name", "score"}

    def test_search_bad_table(self, db):
        with pytest.raises(ValidationError):
            db.search("nonexistent")

    def test_search_bad_column(self, db):
        with pytest.raises(ValidationError):
            db.search("students", columns=["bad_col"])

    def test_search_unsupported_operator(self, db):
        with pytest.raises(ValidationError):
            db.search("students", filters=[{"column": "name", "operator": "bad_op", "value": "x"}])


class TestInsert:
    def test_insert_valid(self, db):
        result = db.insert("students", {"name": "New", "email": "new@test.com", "cohort": "A1", "score": 80})
        assert result["name"] == "New"
        assert result["id"] is not None

    def test_insert_empty(self, db):
        with pytest.raises(ValidationError):
            db.insert("students", {})

    def test_insert_bad_column(self, db):
        with pytest.raises(ValidationError):
            db.insert("students", {"bad_col": "x"})

    def test_insert_bad_table(self, db):
        with pytest.raises(ValidationError):
            db.insert("nonexistent", {"name": "x"})


class TestAggregate:
    def test_count(self, db):
        result = db.aggregate("students", "count")
        assert result[0]["value"] == 5

    def test_avg(self, db):
        result = db.aggregate("students", "avg", column="score")
        assert 80 <= result[0]["value"] <= 83

    def test_min_max(self, db):
        min_r = db.aggregate("students", "min", column="score")
        max_r = db.aggregate("students", "max", column="score")
        assert min_r[0]["value"] == 68.5
        assert max_r[0]["value"] == 95.0

    def test_sum(self, db):
        result = db.aggregate("students", "sum", column="score")
        assert result[0]["value"] == 412.0

    def test_group_by(self, db):
        result = db.aggregate("students", "avg", column="score", group_by="cohort")
        assert len(result) == 2
        groups = {r["group_key"]: r["value"] for r in result}
        assert "A1" in groups
        assert "B2" in groups

    def test_bad_metric(self, db):
        with pytest.raises(ValidationError):
            db.aggregate("students", "invalid")

    def test_bad_column(self, db):
        with pytest.raises(ValidationError):
            db.aggregate("students", "avg", column="bad_col")


class TestSchema:
    def test_list_tables(self, db):
        tables = db.list_tables()
        assert "students" in tables
        assert "courses" in tables
        assert "enrollments" in tables

    def test_get_table_schema(self, db):
        schema = db.get_table_schema("students")
        col_names = {c["name"] for c in schema}
        assert "id" in col_names
        assert "name" in col_names
        assert "email" in col_names
        assert "cohort" in col_names
        assert "score" in col_names

    def test_get_bad_table(self, db):
        with pytest.raises(ValidationError):
            db.get_table_schema("nonexistent")
