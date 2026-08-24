# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 3 contract — domain validators on the complete tree.

Executable where the API is fixed by the plan (SqlModelValidator,
builder.validate_model(), SqlModelValidationError listing every violation
with node paths); skeletons where the message wording is the phase's own.
"""
from __future__ import annotations

import pytest

from genro_sql import SqlBuilder
from genro_sql.validators import SqlModelValidationError, SqlModelValidator


def _build(main_fn):
    class Model(SqlBuilder):
        def main(self, root):
            main_fn(root)

    model = Model()
    model.create()
    return model


def _errors(main_fn) -> str:
    model = _build(main_fn)
    with pytest.raises(SqlModelValidationError) as exc:
        SqlModelValidator().validate(model)
    return str(exc.value)


def test_valid_model_passes_and_returns_builder():
    def main(root):
        tables = root.db(name="d").schemas().schema(name="s").tables()
        t = tables.table(name="t", pkey="id")
        t.columns().column(name="id", dtype="serial")

    model = _build(main)
    assert SqlModelValidator().validate(model) is model
    assert model.validate_model() is model


def test_pkey_must_name_existing_physical_columns():
    def main(root):
        tables = root.db(name="d").schemas().schema(name="s").tables()
        t = tables.table(name="t", pkey="ghost")
        t.columns().column(name="id", dtype="serial")

    msg = _errors(main)
    assert "ghost" in msg and "d.schemas.s.tables.t" in msg


def test_relation_target_must_exist():
    def main(root):
        tables = root.db(name="d").schemas().schema(name="s").tables()
        t = tables.table(name="t", pkey="id")
        c = t.columns().column(name="id", dtype="L")
        c.relation(to="s.missing.id", foreign_key=True)

    msg = _errors(main)
    assert "missing" in msg


def test_foreign_key_forbidden_on_virtual_columns():
    def main(root):
        tables = root.db(name="d").schemas().schema(name="s").tables()
        t = tables.table(name="t", pkey="id")
        t.columns().column(name="id", dtype="serial")
        t.virtual_columns().formulaColumn(name="calc", sql_formula="1+1")

    # grammar itself must forbid relation under formulaColumn (sub_tags="")
    model = _build(main)
    node = model.source["db.schemas.s.tables.t.virtual_columns.calc"]
    with pytest.raises(Exception):
        node.relation(to="s.t.id", foreign_key=True)


def test_composite_members_must_exist_and_be_physical():
    def main(root):
        tables = root.db(name="d").schemas().schema(name="s").tables()
        t = tables.table(name="t", pkey="a")
        t.columns().column(name="a", dtype="L")
        t.composites().compositeColumn(name="ab", columns="a,ghost")

    msg = _errors(main)
    assert "ghost" in msg


def test_composite_fk_column_counts_must_match():
    # wf:contract: a composite relation whose local member count differs from
    # wf:contract: the resolved target column count is a validation error
    # wf:contract: naming both sides' counts.
    def main(root):
        tables = root.db(name="d").schemas().schema(name="s").tables()
        target = tables.table(name="target", pkey="x")
        target.columns().column(name="x", dtype="L")
        t = tables.table(name="t", pkey="a")
        columns = t.columns()
        columns.column(name="a", dtype="L")
        columns.column(name="b", dtype="L")
        cc = t.composites().compositeColumn(name="ab", columns="a,b")
        cc.relation(to="s.target", foreign_key=True)

    msg = _errors(main)
    assert msg  # counts 2 vs 1


def test_constraint_and_index_columns_must_exist():
    def main(root):
        tables = root.db(name="d").schemas().schema(name="s").tables()
        t = tables.table(name="t", pkey="id")
        t.columns().column(name="id", dtype="serial")
        t.constraints().constraint(
            name="uq", constraint_type="UNIQUE", columns="id,ghost",
        )
        t.indexes().index(name="ix", columns="ghost2")

    msg = _errors(main)
    assert "ghost" in msg and "ghost2" in msg


def test_check_requires_clause_unique_requires_columns():
    def main(root):
        tables = root.db(name="d").schemas().schema(name="s").tables()
        t = tables.table(name="t", pkey="id")
        t.columns().column(name="id", dtype="serial")
        constraints = t.constraints()
        constraints.constraint(name="ck", constraint_type="CHECK")
        constraints.constraint(name="uq", constraint_type="UNIQUE")

    msg = _errors(main)
    assert "ck" in msg and "uq" in msg


def test_extra_attributes_must_be_x_prefixed():
    def main(root):
        tables = root.db(name="d").schemas().schema(name="s").tables()
        t = tables.table(name="t", pkey="id")
        t.columns().column(name="id", dtype="serial", dtypo="A")

    msg = _errors(main)
    assert "dtypo" in msg and "x_" in msg


def test_all_errors_reported_together():
    def main(root):
        tables = root.db(name="d").schemas().schema(name="s").tables()
        t = tables.table(name="t", pkey="ghost")
        t.columns().column(name="id", dtype="serial", dtypo="A")
        t.indexes().index(name="ix", columns="nope")

    msg = _errors(main)
    assert "ghost" in msg and "dtypo" in msg and "nope" in msg


def test_duplicate_back_reference_on_same_target():
    # wf:contract: two foreign_key relations from different columns whose
    # wf:contract: back_reference collide on the same target table are a
    # wf:contract: validation error naming the duplicated back_reference.
    def main(root):
        tables = root.db(name="d").schemas().schema(name="s").tables()
        target = tables.table(name="target", pkey="x")
        target.columns().column(name="x", dtype="L")
        t = tables.table(name="t", pkey="a")
        columns = t.columns()
        columns.column(name="a", dtype="serial")
        c1 = columns.column(name="one", dtype="L")
        c1.relation(to="s.target.x", foreign_key=True, back_reference="rows")
        c2 = columns.column(name="two", dtype="L")
        c2.relation(to="s.target.x", foreign_key=True, back_reference="rows")

    msg = _errors(main)
    assert "rows" in msg
