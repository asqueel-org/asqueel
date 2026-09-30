# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 14 contract — public imports, emitter and PG harness are safe."""
from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

import pytest

import asqueel
from asqueel import (
    SqlBuilder,
    SqlMigrationRenderer,
    SqlModelReader,
    SqlPythonEmitter,
)
from asqueel_migration import JsonStructureProducer
from asqueel_migration.structures import json_equal


def test_internal_import_errors_are_not_rewritten(monkeypatch):
    def broken_import(_name, _package):
        raise ImportError("internal reader defect")

    monkeypatch.setattr(asqueel, "import_module", broken_import)
    with pytest.raises(ImportError, match="internal reader defect"):
        asqueel.__getattr__("SqlModelReader")


def test_base_install_star_import_does_not_resolve_optional_names():
    script = """
import builtins
original = builtins.__import__
def without_migration(name, *args, **kwargs):
    if name.startswith('asqueel_migration'):
        raise ModuleNotFoundError(name=name)
    return original(name, *args, **kwargs)
builtins.__import__ = without_migration
namespace = {}
exec('from asqueel import *', namespace)
assert 'SqlBuilder' in namespace
assert 'SqlModelReader' not in namespace
assert 'SqlMigrationRenderer' not in namespace
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_empty_model_is_refused_before_invalid_python_is_emitted():
    model = SqlBuilder()
    model.create()
    with pytest.raises(ValueError, match="db|database|empty"):
        SqlPythonEmitter(model).emit()


def test_emitter_handles_identifiers_and_real_string_escaping():
    normalized = JsonStructureProducer({
        "db": "odd", "schemas": [{"name": "class", "tables": [
            {"name": "1-order", "pkey": "id", "comment": "a \\\"quote\\\" \\\\ path",
             "columns": [{"name": "id", "dtype": "serial"},
                         {"name": "a-b", "dtype": "T"},
                         {"name": "a_b", "dtype": "T"}]},
        ]}],
    }).get_json_struct()
    builder = SqlModelReader(normalized).to_builder()
    source = SqlPythonEmitter(builder).emit()
    namespace = {}
    exec(compile(source, "<emitted>", "exec"), namespace)
    rebuilt = namespace["ImportedDatabase"]()
    rebuilt.create()
    assert json_equal(normalized, SqlMigrationRenderer(rebuilt).render())


def test_package_sources_contain_no_print_calls():
    package_root = Path(asqueel.__file__).resolve().parent
    for path in package_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
            for node in ast.walk(tree)
        ), path


def test_pg_db_creation_path_is_guarded_before_external_mutation():
    # wf:contract: the PostgreSQL integration fixture fails immediately if
    # wf:contract: SqlMigrator dispatches added_db/db_creation; the assertion
    # wf:contract: runs before any CREATE DATABASE SQL and names the logical db.
    database_type = sys.modules["tests.conftest"].RecipeNamedPgDatabase
    database = database_type({"dbname": "test_asqueel_guard"})
    database.adopt("outside_recipe", ())
    migrator = sys.modules["asqueel_migration"].SqlMigrator(database)
    with pytest.raises(AssertionError, match="outside_recipe"):
        migrator.added_db(item={"entity_name": "outside_recipe", "schemas": {}})
    assert migrator.commands == {}
