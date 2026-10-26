"""The explicit adapter path executes the same V1 operations on PostgreSQL."""

import pytest

from asqueel import AsqueelDb
from asqueel.compiler import QueryCompiler
from asqueel.contracts import CompiledQuery
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from tests.unit_of_work import empty_database
from asqueel.write_compiler import WriteCompiler
from tests.native_integration.test_postgres_vertical import (
    native_database as native_database, recipe,
)

pytestmark = pytest.mark.postgresql


def test_explicit_pipeline(native_database):
    params, schema, connection = native_database
    adapter = PostgresAdapter(None)
    model = AsqueelDb(recipe(schema)).model
    compiler = QueryCompiler(model, adapter)
    writer = WriteCompiler(adapter)

    def scenario():
        db = empty_database(implementation='postgres', connect_kwargs=params).session()
        try:
            db.execute(writer.insert(model.table('crm.customer'), {'id': 1, 'name': "L'impresa 50%"},
                                     db.environment_snapshot()))
            # The adapter doubles every % outside a binding for psycopg.
            plan = compiler.plan_select(
                'crm.customer', columns="$name, '50%' AS percent",
                where='$id = :id', sqlparams={'id': 1},
            )
            prepared = compiler.compile_plan(plan)
            assert "'50%%'" in prepared.sql
            assert '%(id)s' in prepared.sql
            rows = (db.execute(prepared)).fetchall()
            assert [dict(row) for row in rows] == [{'name': "L'impresa 50%", 'percent': '50%'}]
            assert db.execute(CompiledQuery('SELECT 1 AS ok'))
        finally:
            db.closeConnection()
            db.shared.close()
    scenario()
