# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 5 contract — real-database integration via SqlMigrator.

recipe -> SqlMigrationRenderer -> SqlMigrator -> applyChanges, on SQLite
and on the local PostgreSQL (D10). Idempotence: after apply, a fresh
preparation reports no changes. Evolution: a v2 recipe produces only the
incremental commands.

The pg fixtures (connection params, test-database lifecycle) come from
tests/conftest.py — the phase writes them following
../genro-sqlmigration/tests/conftest.py.
"""
from __future__ import annotations

import pytest

from genro_sqlmigration import SqlMigrator

from genro_sql import SqlBuilder, SqlMigrationRenderer


class LibraryV1(SqlBuilder):
    def main(self, root):
        db = root.db(name="library")
        public = db.schemas().schema(name="library_public")
        book = public.tables().table(name="book", pkey="id")
        columns = book.columns()
        columns.column(name="id", dtype="serial")
        columns.column(name="title", dtype="A", size="0:160", notnull=True)
        columns.column(name="isbn", dtype="A", size="0:13", unique=True)


class LibraryV2(SqlBuilder):
    """V1 plus: wider title, a new indexed column, a CHECK."""

    def main(self, root):
        db = root.db(name="library")
        public = db.schemas().schema(name="library_public")
        book = public.tables().table(name="book", pkey="id")
        columns = book.columns()
        columns.column(name="id", dtype="serial")
        columns.column(name="title", dtype="A", size="0:240", notnull=True)
        columns.column(name="isbn", dtype="A", size="0:13", unique=True)
        columns.column(name="year", dtype="I", indexed=True)
        book.constraints().constraint(
            name="ck_year", constraint_type="CHECK", check_clause="(year > 0)",
        )


def _desired(recipe_cls):
    model = recipe_cls()
    model.create()
    return SqlMigrationRenderer(model).render()


def _prepare(database, structure):
    migrator = SqlMigrator(database)
    migrator.ormStructure = structure
    migrator.prepareMigrationCommands()
    return migrator


def test_sqlite_create_apply_idempotent(sqlite_database):
    # wf:contract: sqlite_database is a conftest fixture yielding a
    # wf:contract: genro_sqlmigration SqliteDatabase on a temp path with
    # wf:contract: application_schemas=["library_public"].
    migrator = _prepare(sqlite_database, _desired(LibraryV1))
    assert migrator.getChanges()
    migrator.applyChanges()
    second = _prepare(sqlite_database, _desired(LibraryV1))
    assert not second.getChanges(), second.getChanges()


@pytest.mark.postgresql
def test_pg_create_apply_idempotent(pg_database):
    # wf:contract: pg_database is a conftest fixture yielding a PgDatabase on
    # wf:contract: a dedicated test db (test_genro_sql_*), created for the
    # wf:contract: test and dropped in teardown, connection from
    # wf:contract: GNR_TEST_PG_* env with D10 defaults.
    migrator = _prepare(pg_database, _desired(LibraryV1))
    assert migrator.getChanges()
    migrator.applyChanges()
    second = _prepare(pg_database, _desired(LibraryV1))
    assert not second.getChanges(), second.getChanges()


@pytest.mark.postgresql
def test_pg_evolution_is_incremental_and_idempotent(pg_database):
    migrator = _prepare(pg_database, _desired(LibraryV1))
    migrator.applyChanges()

    evolved = _prepare(pg_database, _desired(LibraryV2))
    changes = evolved.getChanges()
    assert changes
    assert "CREATE SCHEMA" not in changes  # incremental, not from scratch
    evolved.applyChanges()

    third = _prepare(pg_database, _desired(LibraryV2))
    assert not third.getChanges(), third.getChanges()


@pytest.mark.postgresql
def test_pg_introspection_matches_desired(pg_database):
    # wf:contract: after apply, the database reader's get_json_struct for the
    # wf:contract: application schema is diff-empty against the rendered
    # wf:contract: recipe (the migrator itself is the judge: prepare on a
    # wf:contract: fresh migrator and assert no commands).
    migrator = _prepare(pg_database, _desired(LibraryV2))
    migrator.applyChanges()
    check = _prepare(pg_database, _desired(LibraryV2))
    assert not check.getChanges()
