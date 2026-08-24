# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 19 contract — canonical package and modular invoice model."""

from importlib import import_module
from pathlib import Path

import pytest
from genro_sqlmigration import SqlMigrator
from genro_sqlmigration.structures import json_equal

import genro_sql
from genro_sql import (
    SqlBuilder,
    SqlMigrationRenderer,
    SqlModelReader,
    SqlPythonEmitter,
)

from tests.invc_model.schema import InvoiceModel


def _model():
    model = InvoiceModel()
    model.create()
    model.validate_model()
    return model


def _exec(source):
    namespace = {}
    exec(compile(source, "<phase-19-invoice>", "exec"), namespace)
    model = namespace["ImportedDatabase"]()
    model.create()
    return model


def test_only_the_canonical_top_level_dialect_remains():
    # wf:contract: SqlBuilder, SqlMigrationRenderer, SqlModelReader and
    # wf:contract: SqlPythonEmitter import from genro_sql; LegacySqlBuilder and
    # wf:contract: executable genro_sql.legacy/genro_sql.modern packages do not.
    assert all((SqlBuilder, SqlMigrationRenderer, SqlModelReader, SqlPythonEmitter))
    assert not hasattr(genro_sql, "LegacySqlBuilder")
    package = Path(genro_sql.__file__).resolve().parent
    assert not (package / "legacy").exists()
    assert not (package / "modern").exists()
    with pytest.raises(ModuleNotFoundError):
        import_module("genro_sql.legacy")
    with pytest.raises(ModuleNotFoundError):
        import_module("genro_sql.modern")


def test_modular_invoice_model_closes_the_complete_pipeline():
    # wf:contract: tests/model/invc/schema.py imports customer, invoice and
    # wf:contract: invoice_row, creates one explicit tables collection and passes
    # wf:contract: it to each module's config_db(tables) without circular imports.
    # wf:contract: build -> validate -> render -> emit -> compile -> exec -> render
    # wf:contract: is strict-equal, with no sysFields or generated system columns.
    model = _model()
    expected = SqlMigrationRenderer(model).render()
    source = SqlPythonEmitter(model).emit()
    assert "sysFields" not in source
    assert json_equal(expected, SqlMigrationRenderer(_exec(source)).render())


@pytest.mark.postgresql
def test_modular_invoice_model_closes_against_live_postgresql(pg_database):
    # wf:contract: apply -> inspect -> reader -> emitter -> compile -> exec ->
    # wf:contract: render is migration-equivalent over the application schema,
    # wf:contract: reusing the established safe PostgreSQL facade.
    desired = SqlMigrationRenderer(_model()).render()
    migrator = SqlMigrator(pg_database)
    migrator.ormStructure = desired
    migrator.prepareMigrationCommands()
    migrator.applyChanges()

    inspected = pg_database.get_json_struct()
    recovered = SqlModelReader(inspected).to_builder()
    rebuilt = _exec(SqlPythonEmitter(recovered).emit())
    check = SqlMigrator(pg_database)
    check.ormStructure = SqlMigrationRenderer(rebuilt).render()
    check.prepareMigrationCommands()
    assert not check.getChanges(), check.getChanges()
