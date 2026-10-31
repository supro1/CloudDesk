import re
from pathlib import Path

from backend.app.models.entities import Base

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "database"
TABLE_PATTERN = re.compile(
    r"CREATE TABLE public\.(\w+)\s*\((.*?)\n\);",
    re.IGNORECASE | re.DOTALL,
)
INDEX_PATTERN = re.compile(
    r"CREATE (UNIQUE )?INDEX (\w+)\s+ON public\.(\w+)\s+\(([^)]*)\);",
    re.IGNORECASE | re.DOTALL,
)


def _table_columns(schema: str) -> dict[str, set[str]]:
    tables: dict[str, set[str]] = {}
    for match in TABLE_PATTERN.finditer(schema):
        table_name, definition = match.groups()
        columns = {
            column_name
            for column_name in re.findall(
                r"^    ([a-z_]\w*)\s+",
                definition,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            if column_name.upper() != "CONSTRAINT"
        }
        tables[table_name] = columns
    return tables


def test_postgres_schema_matches_all_sqlalchemy_entities() -> None:
    schema = (DATABASE / "schema.sql").read_text(encoding="utf-8")
    sql_tables = _table_columns(schema)

    assert set(sql_tables) == set(Base.metadata.tables)
    for table_name, table in Base.metadata.tables.items():
        assert {column.name for column in table.columns} == sql_tables[table_name]


def test_postgres_indexes_match_sqlalchemy_entities() -> None:
    schema = (DATABASE / "schema.sql").read_text(encoding="utf-8")
    sql_indexes = {
        (table_name, index_name): (
            bool(unique),
            tuple(column.strip() for column in columns.split(",")),
        )
        for unique, index_name, table_name, columns in INDEX_PATTERN.findall(schema)
    }
    orm_indexes = {
        (table.name, index.name): (
            index.unique,
            tuple(column.name for column in index.columns),
        )
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }

    assert sql_indexes == orm_indexes


def test_postgres_schema_has_updated_at_triggers_for_every_entity() -> None:
    schema = (DATABASE / "schema.sql").read_text(encoding="utf-8")
    trigger_tables = set(
        re.findall(
            r"CREATE TRIGGER trg_(\w+)_updated_at BEFORE UPDATE ON public\.(\w+)",
            schema,
            flags=re.IGNORECASE,
        )
    )

    assert trigger_tables == {(name, name) for name in Base.metadata.tables}
    assert "CREATE OR REPLACE FUNCTION public.set_updated_at()" in schema


def test_migrations_mirror_the_supabase_sql_scripts() -> None:
    schema = (DATABASE / "schema.sql").read_text(encoding="utf-8")
    initial_migration = (
        DATABASE / "migrations" / "0001_initial_schema.sql"
    ).read_text(encoding="utf-8")
    policies = (DATABASE / "rls_policies.sql").read_text(encoding="utf-8")
    rls_migration = (
        DATABASE / "migrations" / "0002_row_level_security.sql"
    ).read_text(encoding="utf-8")

    def without_header(script: str) -> str:
        return re.sub(r"(?m)^\s*--.*(?:\n|$)", "", script).strip()

    assert without_header(schema) == without_header(initial_migration)
    assert without_header(policies) == without_header(rls_migration)


def test_every_entity_has_read_only_support_role_rls() -> None:
    policies = (DATABASE / "rls_policies.sql").read_text(encoding="utf-8")
    enabled_tables = set(
        re.findall(
            r"ALTER TABLE public\.(\w+) ENABLE ROW LEVEL SECURITY;",
            policies,
            flags=re.IGNORECASE,
        )
    )
    created_policies = re.findall(
        r"CREATE POLICY \w+ ON public\.(\w+)\s+FOR (\w+)",
        policies,
        flags=re.IGNORECASE,
    )

    assert enabled_tables == set(Base.metadata.tables)
    assert {table for table, command in created_policies if command.upper() == "SELECT"} == (
        set(Base.metadata.tables)
    )
    assert all(command.upper() == "SELECT" for _, command in created_policies)
    assert "public.current_support_role() IN ('viewer', 'agent', 'admin')" in policies
    assert "id = (SELECT auth.uid())::text" in policies
    assert "FROM PUBLIC, anon, authenticated" in policies
    assert "TO authenticated;" in policies
    assert "TO service_role;" in policies

    restricted_policies = {
        table: expression
        for table, expression in re.findall(
            r"CREATE POLICY \w+ ON public\.(\w+)\s+FOR SELECT TO authenticated\s+"
            r"USING \((.*?)\);",
            policies,
            flags=re.IGNORECASE | re.DOTALL,
        )
    }
    for table_name in (
        "workflow_runs",
        "workflow_events",
        "resolution_actions",
        "approval_requests",
        "escalations",
        "customer_memory",
    ):
        assert restricted_policies[table_name] == (
            "public.current_support_role() IN ('agent', 'admin')"
        )
    assert "AND is_internal = false" in restricted_policies["ticket_messages"]
    assert "public.current_support_role() IN ('agent', 'admin')" in (
        restricted_policies["ticket_messages"]
    )
