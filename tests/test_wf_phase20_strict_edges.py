# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 20 contract — strict edges and typed public surface."""
from __future__ import annotations

import pytest

from genro_sqlmigration import JsonStructureProducer, StructureValidator

from genro_sql import (
    SqlBuilder,
    SqlMigrationRenderer,
    SqlModelReader,
    SqlPythonEmitter,
)
from genro_sql.grammar_doc import generate_grammar_md
from genro_sql.validators import SqlModelValidationError


class _Model(SqlBuilder):
    def main(self, root):
        pass


def _table(*, pkey: str = "id"):
    model = _Model()
    model.create()
    tables = model.source.db("d").schemas().schema("s").tables()
    table = tables.table("t", pkey=pkey)
    columns = table.columns()
    columns.column("id", dtype="serial")
    return model, table, columns


def _relation_model(**attributes):
    model = _Model()
    model.create()
    tables = model.source.db("d").schemas().schema("s").tables()
    target = tables.table("target", pkey="id")
    target.columns().column("id", dtype="serial")
    source = tables.table("source", pkey="id")
    columns = source.columns()
    columns.column("id", dtype="serial")
    owner = columns.column("target_id", dtype="L")
    owner.relation("s.target.id", foreign_key=False, **attributes)
    return model


def test_index_orders_and_repeated_structural_members_are_loud():
    # wf:contract: index order values are only None or DESC; duplicate members
    # wf:contract: in pkeys, composites, UNIQUE constraints and indexes raise one
    # wf:contract: pathful SqlModelValidationError before any projection.
    model, table, _columns = _table(pkey="id,id")
    table.composites().compositeColumn("pair", columns="id,id")
    table.constraints().constraint(
        "uq_pair", constraint_type="UNIQUE", columns="id,id",
    )
    indexes = table.indexes()
    indexes.index("ix_pair", columns="id,id")
    indexes.index("ix_order", columns={"id": "SIDEWAYS"})

    with pytest.raises(SqlModelValidationError) as caught:
        model.validate_model()

    message = str(caught.value)
    assert "pkey repeats member(s): id" in message
    assert "composites.pair: composite repeats member(s): id" in message
    assert "constraints.uq_pair: UNIQUE constraint repeats member(s): id" in message
    assert "indexes.ix_pair: index repeats member(s): id" in message
    assert "indexes.ix_order: index order for 'id' must be None or 'DESC'" in message


def test_schema_comment_is_explicitly_source_only():
    # wf:contract: schema.comment remains available in the source grammar but
    # wf:contract: documentation calls it semantic/source-only because the
    # wf:contract: structure-1.0 schema entity has no physical attribute slot.
    model = _Model()
    model.create()
    model.source.db("d").schemas().schema("s", comment="source description")
    model.validate_model()

    assert model.source["db.schemas.s"].get_attr("comment") == "source description"
    assert "comment" not in SqlMigrationRenderer(model).render()["root"]["schemas"]["s"]
    grammar = generate_grammar_md()
    assert "source-only free description" in grammar
    assert "| comment |" in grammar and "| semantic |" in grammar


def test_emitter_handles_empty_tuples_and_rejects_invalid_class_names():
    # wf:contract: validator-green x_* empty tuples emit as () and the complete
    # wf:contract: module compiles and executes; invalid/keyword class names raise
    # wf:contract: ValueError before any source is returned.
    model = _Model()
    model.create()
    model.source.db("d").schemas().schema("s", x_marker=())
    model.validate_model()

    emitted = SqlPythonEmitter(model).emit(class_name="TupleRecipe")
    assert "x_marker=()" in emitted
    namespace = {}
    exec(compile(emitted, "<phase20>", "exec"), namespace)  # noqa: S102
    rebuilt = namespace["TupleRecipe"]()
    rebuilt.create()
    assert rebuilt.source["db.schemas.s"].get_attr("x_marker") == ()

    for invalid in ("123Bad", "bad-name", "class"):
        with pytest.raises(ValueError, match="class name"):
            SqlPythonEmitter(model).emit(class_name=invalid)


def test_reader_falls_back_for_unnamed_normalized_indexes():
    # wf:contract: a StructureValidator-green index without attributes.index_name
    # wf:contract: is recovered under its structural entity name and re-renders.
    normalized = JsonStructureProducer({
        "db": "d",
        "schemas": [{
            "name": "s",
            "tables": [{
                "name": "t",
                "pkey": "id",
                "columns": [
                    {"name": "id", "dtype": "serial"},
                    {"name": "code", "dtype": "A", "size": "10"},
                ],
                "indexes": [{"name": "ix_code", "columns": ["code"]}],
            }],
        }],
    }).get_json_struct()
    indexes = normalized["root"]["schemas"]["s"]["tables"]["t"]["indexes"]
    structural_name, item = next(iter(indexes.items()))
    item["attributes"].pop("index_name")
    StructureValidator().validate(normalized)

    builder = SqlModelReader(normalized).to_builder()
    recovered = builder.source[
        f"db.schemas.s.tables.t.indexes.{structural_name}"
    ]
    assert recovered is not None
    rendered = SqlMigrationRenderer(builder).render()
    assert rendered["root"]["schemas"]["s"]["tables"]["t"]["indexes"][
        structural_name
    ]["attributes"]["index_name"] == structural_name


def test_nonphysical_relations_reject_physical_fk_options():
    # wf:contract: foreign_key=False relations retain semantic navigation fields
    # wf:contract: but reject explicit physical FK actions/deferral flags instead
    # wf:contract: of accepting configuration that the projection drops.
    semantic = _relation_model(
        back_reference="sources", one_name="Target", many_name="Sources",
        one_one=True, case_insensitive=True,
    )
    semantic.validate_model()
    table = SqlMigrationRenderer(semantic).render()["root"]["schemas"]["s"][
        "tables"
    ]["source"]
    assert table["relations"] == {}

    for option in (
        {"on_delete": "CASCADE"},
        {"deferrable": True},
        {"initially_deferred": True},
        {"indexed": False},
    ):
        with pytest.raises(SqlModelValidationError, match="physical option"):
            _relation_model(**option).validate_model()
