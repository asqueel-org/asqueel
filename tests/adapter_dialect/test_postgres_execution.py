"""Boundary regression: manual fragments cannot comment out DML guards."""
import uuid

import pytest

from asqueel.dialects.postgres import PostgresDialect
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.query_plan import Assignment, QueryPlan, TableRef, concat
from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


def test_manual_assignment_line_comment_cannot_remove_update_guard():
    import psycopg
    from psycopg import sql
    name = 'adapter_comment_' + uuid.uuid4().hex[:12]
    with psycopg.connect(postgres_dsn()) as connection:
        connection.execute(sql.SQL('CREATE TEMP TABLE {} (value integer)').format(sql.Identifier(name)))
        connection.execute(sql.SQL('INSERT INTO {} VALUES (10)').format(sql.Identifier(name)))
        plan = QueryPlan('update', TableRef('pg_temp', name), where=concat('FALSE'),
                         assignments=(Assignment('value', concat('99 -- trailing comment')),))
        driver = PsycopgDriver()
        result = driver.execute(connection, driver.prepare(PostgresDialect().render(plan)))
        assert result.rowcount == 0
        assert connection.execute(sql.SQL('SELECT value FROM {}').format(sql.Identifier(name))).fetchone() == (10,)
        connection.rollback()
