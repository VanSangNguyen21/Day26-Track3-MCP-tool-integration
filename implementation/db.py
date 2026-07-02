import sqlite3
import re
from typing import Any

_VALID_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_ALLOWED_METRICS = {"count", "avg", "sum", "min", "max"}
_ALLOWED_OPERATORS = {"eq", "neq", "gt", "gte", "lt", "lte", "like", "in"}


class ValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _validate_identifier(name: str, label: str = "identifier") -> None:
    if not _VALID_IDENTIFIER.match(name):
        raise ValidationError(f"Invalid {label}: '{name}'")


_SQL_OP_MAP = {
    "eq": "=",
    "neq": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "LIKE",
    "in": "IN",
}


class SQLiteAdapter:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def list_tables(self) -> list[str]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            return [r["name"] for r in rows]
        finally:
            conn.close()

    def get_table_schema(self, table: str) -> list[dict[str, Any]]:
        _validate_identifier(table, "table name")
        conn = self._connect()
        try:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            if not rows:
                raise ValidationError(f"Unknown table: '{table}'")
            return [
                {
                    "cid": r["cid"],
                    "name": r["name"],
                    "type": r["type"],
                    "notnull": bool(r["notnull"]),
                    "default_value": r["dflt_value"],
                    "primary_key": bool(r["pk"]),
                }
                for r in rows
            ]
        finally:
            conn.close()

    def _validate_columns(self, table: str, columns: list[str]) -> None:
        schema = self.get_table_schema(table)
        valid = {col["name"] for col in schema}
        for col in columns:
            if col not in valid:
                raise ValidationError(f"Unknown column '{col}' in table '{table}'")

    def _build_where(self, filters: list[dict] | None, params: list) -> str:
        if not filters:
            return ""
        clauses = []
        for i, f in enumerate(filters):
            col = f.get("column")
            op = f.get("operator", "eq")
            val = f.get("value")
            if not col:
                raise ValidationError(f"Filter #{i} is missing 'column'")
            _validate_identifier(col, "column name")
            if op not in _ALLOWED_OPERATORS:
                raise ValidationError(
                    f"Unsupported operator '{op}'. Allowed: {', '.join(sorted(_ALLOWED_OPERATORS))}"
                )
            sql_op = _SQL_OP_MAP[op]
            if op == "in":
                if not isinstance(val, list):
                    raise ValidationError(f"Filter #{i} with operator 'in' requires a list value")
                placeholders = ",".join(["?"] * len(val))
                clauses.append(f"{col} IN ({placeholders})")
                params.extend(val)
            else:
                clauses.append(f"{col} {sql_op} ?")
                params.append(val)
        return " WHERE " + " AND ".join(clauses)

    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: list[dict] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        _validate_identifier(table, "table name")
        schema = self.get_table_schema(table)
        valid_columns = {col["name"] for col in schema}

        if columns:
            for c in columns:
                if c not in valid_columns:
                    raise ValidationError(f"Unknown column '{c}' in table '{table}'")
            select_cols = ", ".join(columns)
        else:
            select_cols = "*"

        params: list = []
        where_clause = self._build_where(filters, params)

        order_clause = ""
        if order_by:
            if order_by not in valid_columns:
                raise ValidationError(f"Unknown column '{order_by}' in table '{table}'")
            direction = " DESC" if descending else " ASC"
            order_clause = f" ORDER BY {order_by}{direction}"

        limit = max(0, min(limit, 1000))
        offset = max(0, offset)

        sql = f"SELECT {select_cols} FROM {table}{where_clause}{order_clause} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            result = [dict(r) for r in rows]
            count_sql = f"SELECT COUNT(*) as total FROM {table}{where_clause}"
            count_params = params[:-2]
            total = conn.execute(count_sql, count_params).fetchone()["total"]
            return {
                "rows": result,
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        finally:
            conn.close()

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        _validate_identifier(table, "table name")
        if not values:
            raise ValidationError("Cannot insert empty record")

        schema = self.get_table_schema(table)
        valid_columns = {col["name"] for col in schema}
        for col in values:
            if col not in valid_columns:
                raise ValidationError(f"Unknown column '{col}' in table '{table}'")

        columns = list(values.keys())
        placeholders = ",".join(["?"] * len(columns))
        col_list = ",".join(columns)
        vals = [values[c] for c in columns]

        conn = self._connect()
        try:
            cur = conn.execute(
                f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})", vals
            )
            conn.commit()
            inserted_id = cur.lastrowid
            pk_cols = [c["name"] for c in schema if c["primary_key"]]
            if inserted_id is not None and pk_cols:
                pk_name = pk_cols[0]
                row = conn.execute(
                    f"SELECT * FROM {table} WHERE {pk_name} = ?", (inserted_id,)
                ).fetchone()
                if row:
                    return dict(row)
            return {"id": inserted_id, **values}
        finally:
            conn.close()

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict] | None = None,
        group_by: str | None = None,
    ) -> list[dict[str, Any]]:
        _validate_identifier(table, "table name")
        m = metric.lower()
        if m not in _ALLOWED_METRICS:
            raise ValidationError(
                f"Unsupported metric '{metric}'. Allowed: {', '.join(sorted(_ALLOWED_METRICS))}"
            )

        schema = self.get_table_schema(table)
        valid_columns = {col["name"] for col in schema}

        if column:
            if column not in valid_columns:
                raise ValidationError(f"Unknown column '{column}' in table '{table}'")

        if group_by:
            if group_by not in valid_columns:
                raise ValidationError(f"Unknown column '{group_by}' in table '{table}'")

        if m == "count" and column is None:
            expr = "COUNT(*) AS value"
        elif column:
            expr = f"{m.upper()}({column}) AS value"
        else:
            raise ValidationError(f"Metric '{metric}' requires a column name")

        params: list = []
        where_clause = self._build_where(filters, params)

        if group_by:
            sql = f"SELECT {group_by} AS group_key, {expr} FROM {table}{where_clause} GROUP BY {group_by} ORDER BY group_key"
        else:
            sql = f"SELECT {expr} FROM {table}{where_clause}"

        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
