# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 7 contract — SqlPythonEmitter: source tree to Python recipe.

Law: emit -> exec -> create -> render produces the same normalized JSON the
source builder renders. Emission is byte-deterministic. The PG closure runs
the whole reverse pipeline against a live database.
"""
from __future__ import annotations

import pytest

from genro_sqlmigration import JsonStructureProducer, SqlMigrator
from genro_sqlmigration.structures import json_equal

from genro_sql import SqlMigrationRenderer, SqlModelReader, SqlPythonEmitter


HUMAN_FIXTURE = {
    "db": "recipes",
    "extensions": ["pg_trgm"],
    "schemas": [{
        "name": "wfp7",
        "tables": [
            {"name": "author", "pkey": "id", "comment": "Authors",
             "columns": [
                 {"name": "id", "dtype": "serial"},
                 {"name": "name", "dtype": "A", "size": "0:120",
                  "notnull": True},
             ]},
            {"name": "recipe", "pkey": "id",
             "columns": [
                 {"name": "id", "dtype": "serial"},
                 {"name": "title", "dtype": "A", "size": "0:160",
                  "notnull": True},
                 {"name": "author_id", "dtype": "L", "notnull": True},
             ],
             "relations": [
                 {"columns": ["author_id"], "related_schema": "wfp7",
                  "related_table": "author", "related_columns": ["id"],
                  "on_delete": "CASCADE"},
             ],
             "constraints": [
                 {"type": "UNIQUE", "columns": ["author_id", "title"]},
                 {"type": "CHECK", "name": "ck_title",
                  "check_clause": "(char_length(title) > 0)"},
             ],
             "indexes": [
                 {"columns": {"title": None, "id": "DESC"}},
                 {"columns": ["author_id"]},
             ]},
        ],
    }],
}


def _builder_from(human):
    normalized = JsonStructureProducer(human).get_json_struct()
    return SqlModelReader(normalized).to_builder(), normalized


def _exec_recipe(source_code, class_name="ImportedDatabase"):
    namespace = {}
    exec(compile(source_code, "<emitted>", "exec"), namespace)  # noqa: S102
    model = namespace[class_name]()
    model.create()
    return model


def test_emit_exec_render_closes_the_loop():
    builder, normalized = _builder_from(HUMAN_FIXTURE)
    source_code = SqlPythonEmitter(builder).emit()
    model = _exec_recipe(source_code)
    rendered = SqlMigrationRenderer(model).render()
    assert json_equal(normalized, rendered)


def test_emission_is_byte_deterministic():
    builder, _ = _builder_from(HUMAN_FIXTURE)
    first = SqlPythonEmitter(builder).emit()
    second = SqlPythonEmitter(builder).emit()
    assert first == second
    rebuilt, _ = _builder_from(HUMAN_FIXTURE)
    assert SqlPythonEmitter(rebuilt).emit() == first


def test_emitted_module_shape():
    builder, _ = _builder_from(HUMAN_FIXTURE)
    source_code = SqlPythonEmitter(builder).emit(class_name="MyDb")
    assert source_code.startswith("# ") or source_code.startswith('"""') or \
        source_code.startswith("from ")
    assert "from genro_sql import SqlBuilder" in source_code
    assert "class MyDb(SqlBuilder):" in source_code
    assert "def main(self, root):" in source_code
    # no structural hashes as names
    for prefix in ("fk_", "cst_"):
        assert f'name="{prefix}' not in source_code


def test_sql_names_that_are_not_python_identifiers():
    builder, normalized = _builder_from({
        "db": "odd",
        "schemas": [{"name": "s", "tables": [
            {"name": "order-line", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"},
                         {"name": "class", "dtype": "A", "size": "0:10"}]},
        ]}],
    })
    source_code = SqlPythonEmitter(builder).emit()
    model = _exec_recipe(source_code)
    assert json_equal(normalized, SqlMigrationRenderer(model).render())


@pytest.mark.postgresql
def test_pg_end_to_end_closure(pg_database):
    # wf:contract: full reverse pipeline on a live PG — apply a known desired
    # wf:contract: structure, introspect with the database reader
    # wf:contract: (pg_database.reader-equivalent get_json_struct on the
    # wf:contract: application schemas), feed SqlModelReader ->
    # wf:contract: SqlPythonEmitter -> exec -> render, and assert the result
    # wf:contract: is diff-empty against the live database (a fresh
    # wf:contract: SqlMigrator prepared with it reports no changes).
    builder, normalized = _builder_from(HUMAN_FIXTURE)
    migrator = SqlMigrator(pg_database)
    migrator.ormStructure = SqlMigrationRenderer(builder).render()
    migrator.prepareMigrationCommands()
    migrator.applyChanges()

    introspected = pg_database.get_json_struct()
    recovered = SqlModelReader(introspected).to_builder()
    source_code = SqlPythonEmitter(recovered).emit()
    model = _exec_recipe(source_code)

    check = SqlMigrator(pg_database)
    check.ormStructure = SqlMigrationRenderer(model).render()
    check.prepareMigrationCommands()
    assert not check.getChanges(), check.getChanges()
