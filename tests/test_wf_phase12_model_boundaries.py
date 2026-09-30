# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 12 contract — strict model and projection boundaries."""
from __future__ import annotations

import pytest

from asqueel import SqlBuilder, SqlMigrationRenderer
from asqueel.grammar_doc import generate_grammar_md
from asqueel.validators import SqlModelValidationError


class _Model(SqlBuilder):
    def main(self, root):
        pass


def _mount():
    model = _Model()
    model.create()
    return model


def _table(*, pkey="id"):
    model = _mount()
    tables = model.source.db(name="d").schemas().schema(name="s").tables()
    table = tables.table(
        name="t", pkey=pkey,
    )
    columns = table.columns()
    columns.column(name="id", dtype="serial")
    return model, table, columns


def test_second_database_and_orphan_elements_are_loud():
    model = _mount()
    model.source.db(name="first")
    with pytest.raises(ValueError, match="database|db|already"):
        model.source.db(name="second")
    with pytest.raises(ValueError, match="table|parent|schema"):
        model.source.table(name="orphan")


def test_constraint_and_index_names_do_not_share_the_column_namespace():
    model, table, columns = _table()
    columns.column(name="title", dtype="T")
    table.constraints().constraint(
        name="title", constraint_type="CHECK", check_clause="(title <> '')",
    )
    table.indexes().index(name="title", columns="title")
    rendered = SqlMigrationRenderer(model).render()
    item = rendered["root"]["schemas"]["s"]["tables"]["t"]
    assert item["constraints"] and item["indexes"]


def test_index_requires_a_name_and_columns():
    model, table, _columns = _table()
    indexes = table.indexes()
    with pytest.raises((TypeError, ValueError), match="name"):
        indexes.index(columns="id")
    indexes.index(name="empty")
    with pytest.raises(SqlModelValidationError, match="columns"):
        model.validate_model()


def test_multiple_relations_are_rejected_by_domain_validation():
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="s")
    tables = schema.tables()
    for name in ("a", "b"):
        target = tables.table(name=name, pkey="id")
        target.columns().column(name="id", dtype="serial")
    source = tables.table(name="source", pkey="id")
    source_columns = source.columns()
    source_columns.column(name="id", dtype="serial")
    owner = source_columns.column(name="target_id", dtype="L")
    owner.relation(to="s.a.id", foreign_key=True)
    owner.relation(to="s.b.id", foreign_key=True)
    with pytest.raises(SqlModelValidationError, match="at most one"):
        SqlMigrationRenderer(model).render()


def test_pkey_spacing_and_dtype_default_are_normalized():
    model, _table_node, columns = _table(pkey="id, code")
    columns.column(name="code", dtype="L")
    columns.column(name="description")
    rendered = SqlMigrationRenderer(model).render()
    item = rendered["root"]["schemas"]["s"]["tables"]["t"]
    assert item["attributes"]["pkeys"] == "id,code"
    assert item["columns"]["description"]["attributes"]["dtype"] == "T"


def test_auto_index_over_the_exact_pkey_is_suppressed():
    model = _mount()
    tables = model.source.db(name="d").schemas().schema(name="s").tables()
    table = tables.table(
        name="t", pkey="id",
    )
    table.columns().column(name="id", dtype="serial", indexed=True)
    rendered = SqlMigrationRenderer(model).render()
    item = rendered["root"]["schemas"]["s"]["tables"]["t"]
    assert not item["indexes"]


def test_sql_type_and_dotted_address_names_are_rejected():
    model, _table_node, columns = _table()
    columns.column(name="native", sql_type="geometry(Point,4326)")
    with pytest.raises(SqlModelValidationError, match="sql_type"):
        model.validate_model()
    dotted = _mount()
    db = dotted.source.db(name="d")
    with pytest.raises(ValueError, match="dot|separator|name"):
        db.schemas().schema(name="bad.name")


def test_generated_grammar_states_the_real_public_contract():
    text = generate_grammar_md()
    assert "sql_type" not in text
    assert "Child addressing" in text
    assert "| comment |" in text and "| physical |" in text
