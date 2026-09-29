# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for the real-database integration tests.

The migrator labels the database side of the diff with
``db.get_dbname()`` and crashes on any ``root.entity_name`` mismatch;
upstream keeps the two sides equal by producing the ORM JSON with
``OrmJsonProducer(model, db.get_dbname())``. ``SqlMigrationRenderer``
emits the recipe's ``db(name=...)`` instead, so here the *database*
facade is what carries the recipe name:

- SQLite: ``get_dbname()`` doubles as the sqlite file path, so the
  fixture uses the bare recipe name as a relative path and pins the
  working directory to ``tmp_path`` — label and file stay identical
  while every artifact lands in the temp directory.
- PostgreSQL: a facade subclass reports the recipe's own label and
  schemas while connections stay on the dedicated D10 test database
  (``test_genro_sql_*``), created empty here and dropped in teardown.
  Pre-creating it also keeps the migrator away from CREATE DATABASE,
  which targets the label name. The facade learns the label from the
  structure it is asked to migrate — one recipe per test, each with its
  own db name and schemas — instead of a constant every test would have
  to agree on.

``sqlite_reader`` reads an integer pkey back as ``I`` even when it was
created from ``serial`` (documented v1 limitation). The resulting dtype
diff event is absorbed by capability gating — SQLite declares no
``alter_column_type``, so the builder records a warning and emits no
SQL — and idempotence stays judged on the assembled commands.

PostgreSQL connection parameters come from ``GNR_TEST_PG_HOST``,
``GNR_TEST_PG_PORT``, ``GNR_TEST_PG_USER`` and ``GNR_TEST_PG_PASSWORD``,
defaulting to the local trust-authenticated server on 127.0.0.1:5432.
"""
from __future__ import annotations

import os
import json
from importlib.metadata import distribution

import psycopg
import pytest

from genro_sqlmigration import SqlMigrator
from genro_sqlmigration.adapters import PgDatabase, SqliteDatabase

APPLICATION_SCHEMAS = ["library_public"]
DB_PREFIX = "test_genro_sql_"
RECIPE_DB_NAME = "library"


def pytest_collection_modifyitems(items):
    """Keep known upstream regressions executable against the pinned public SHA.

    Only this exact revision has these expectations. Another revision, a local
    editable checkout, or ``pytest --runxfail`` runs the original assertions
    normally. Unexpected passes are failures so the expectations cannot linger
    unnoticed after an upstream repair.
    """
    direct_url = json.loads(
        distribution("genro-sqlmigration").read_text("direct_url.json") or "{}"
    )
    if direct_url.get("vcs_info", {}).get("commit_id") != (
        "e64fa00b22b304263f515765bb44e5b74d9e9534"
    ):
        return
    known = {
        "tests/test_wf_phase21_delivery.py::"
        "test_authored_index_names_are_dialect_quoted_at_the_writer_boundary": (
            pytest.RaisesExc(
                AttributeError, match="^'PgWriter' object has no attribute 'quote_identifier'$",
            ),
            "public migrator lacks writer.quote_identifier; docs/delivery.md",
        ),
        "tests/test_wf_phase16_genropy_oracles.py::"
        "test_live_inspection_preserves_descending_order_and_builds_a_recipe": (
            pytest.RaisesExc(AssertionError, match=r"^\{'idx_0419f7f4':"),
            "genro-sqlmigration#8: physical index names / DESC introspection",
        ),
    }
    for item in items:
        if item.nodeid in known:
            expected_error, reason = known[item.nodeid]
            item.add_marker(pytest.mark.xfail(reason=reason, raises=expected_error, strict=True))


@pytest.fixture
def sqlite_database(tmp_path, monkeypatch):
    """SqliteDatabase on a temp path, labeled with the recipe name."""
    monkeypatch.chdir(tmp_path)
    database = SqliteDatabase(
        {"dbname": RECIPE_DB_NAME},
        application_schemas=APPLICATION_SCHEMAS,
    )
    yield database
    database.closeConnection()


class RecipeNamedPgDatabase(PgDatabase):
    """Label the diff with the recipe's name; connect to the test database.

    ``adopt`` is called by :func:`pg_facade_follows_the_recipe` with the
    ORM structure the migrator is about to diff, so the database side of
    the diff carries the same ``entity_name`` and the introspection
    covers the schemas the recipe declares.
    """

    recipe_dbname = None
    recipe_schemas = ()

    def adopt(self, dbname, schemas):
        self.recipe_dbname = dbname
        self.recipe_schemas = schemas

    def get_dbname(self):
        return self.recipe_dbname or super().get_dbname()

    def getApplicationSchemas(self):
        declared = super().getApplicationSchemas()
        return declared + [schema for schema in self.recipe_schemas
                           if schema not in declared]

    def get_json_struct(self):
        """The live structure of the recipe's own schemas."""
        return self.adapter.reader.get_json_struct(
            self.get_dbname(), schemas=self.getApplicationSchemas(),
        )


@pytest.fixture(scope="session")
def pg_params():
    """psycopg connection kwargs for the test PostgreSQL server."""
    params = {
        "host": os.environ.get("GNR_TEST_PG_HOST", "127.0.0.1"),
        "port": os.environ.get("GNR_TEST_PG_PORT", "5432"),
        "user": os.environ.get("GNR_TEST_PG_USER", "postgres"),
    }
    password = os.environ.get("GNR_TEST_PG_PASSWORD")
    if password:
        params["password"] = password
    return params


def _drop_pg_database(pg_params, dbname):
    """Terminate leftover backends and drop the test database."""
    with psycopg.connect(dbname="postgres", autocommit=True, **pg_params) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
            " WHERE datname = %s AND pid <> pg_backend_pid()",
            (dbname,),
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


@pytest.fixture(autouse=True)
def pg_facade_follows_the_recipe(monkeypatch):
    """Teach the pg facade the label and schemas of the migrated recipe."""
    extract_orm = SqlMigrator.extractOrm
    added_db = SqlMigrator.added_db

    def extractOrm(self):
        extract_orm(self)
        root = (self.ormStructure or {}).get("root") or {}
        if isinstance(self.db, RecipeNamedPgDatabase) and root:
            self.db.adopt(root.get("entity_name"),
                          list(root.get("schemas") or {}))

    def refuse_added_db(self, item=None, **kwargs):
        if isinstance(self.db, RecipeNamedPgDatabase):
            logical_db = (item or {}).get("entity_name") or self.db.get_dbname()
            raise AssertionError(
                f"unsafe added_db/db_creation for PostgreSQL test recipe "
                f"{logical_db!r}",
            )
        return added_db(self, item=item, **kwargs)

    monkeypatch.setattr(SqlMigrator, "extractOrm", extractOrm)
    monkeypatch.setattr(SqlMigrator, "added_db", refuse_added_db)


@pytest.fixture
def pg_database(request, pg_params):
    """PgDatabase on a dedicated empty test database, dropped in teardown."""
    dbname = f"{DB_PREFIX}{request.function.__name__}"[:63]
    _drop_pg_database(pg_params, dbname)
    with psycopg.connect(dbname="postgres", autocommit=True, **pg_params) as conn:
        conn.execute(f'CREATE DATABASE "{dbname}"')
    database = RecipeNamedPgDatabase(
        dict(pg_params, dbname=dbname),
        application_schemas=APPLICATION_SCHEMAS,
    )
    yield database
    database.closeConnection()
    _drop_pg_database(pg_params, dbname)
