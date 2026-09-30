# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Grammar tests: the element vocabulary, its signatures and containment.

Outcome-based: the tests mutate only through the canonical builder API and
assert observable results (a model built with every element mounts; illegal
placements and undeclared attributes raise), never auto-generated labels or
node internals.
"""

from copy import deepcopy

import pytest
from asqueel_migration import JsonStructureProducer, SqlMigrator
from asqueel_migration.structures import json_equal, nested_defaultdict

from asqueel import (
    SqlBuilder,
    SqlMigrationRenderer,
    SqlModelReader,
    SqlPythonEmitter,
)
from asqueel.grammar_doc import generate_grammar_md
from asqueel.reader import SqlModelReadError
from asqueel.validators import SqlModelValidationError


class _Model(SqlBuilder):
    def main(self, root):
        pass  # built per-test on model.source


def _mount():
    model = _Model()
    model.create()
    return model


def test_full_vocabulary_mounts():
    """Every element in the grammar builds a well-formed tree."""
    model = _mount()
    db = model.source.db(name="testdb")
    db.extensions().extension(name="unaccent")
    s = db.schemas().schema(name="public", comment="the default schema")
    t = s.tables().table(name="recipe", pkey="id", caption_field="title")
    columns = t.columns()
    columns.column(name="id", dtype="L", notnull=True)
    author = columns.column(name="author_id", dtype="L", indexed=True)
    author.relation(to="public.author.id", foreign_key=True)
    virtual_columns = t.virtual_columns()
    virtual_columns.formulaColumn(name="up", sql_formula="upper($title)")
    virtual_columns.aliasColumn(name="an", relation_path="@author_id.name")
    virtual_columns.subQueryColumn(name="cnt", query="...", mode="json")
    virtual_columns.pyColumn(name="calc")
    cc = t.composites().compositeColumn(name="k2", columns="id,author_id")
    cc.relation(to="public.other.k2", foreign_key=True)
    t.constraints().constraint(
        name="uq", constraint_type="UNIQUE", columns="id,author_id",
    )
    t.indexes().index(name="ix", columns="author_id")
    assert sum(1 for _ in model.source) == 1  # one db at the top


def test_tree_is_addressed_by_name():
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="p")
    t = schema.tables().table(name="t", pkey="c")
    t.columns().column(name="c", dtype="L")
    assert model.source.get_node("db.schemas.p.tables.t.columns.c") is not None


def test_structural_names_have_tag_scoped_namespaces():
    model = _mount()
    db = model.source.db(name="d")
    db.extensions().extension(name="shared")
    schema = db.schemas().schema(name="shared")
    table = schema.tables().table(name="t", pkey="id")
    table.columns().column(name="id", dtype="serial")
    rendered = SqlMigrationRenderer(model).render()["root"]
    assert "shared" in rendered["schemas"]
    assert "shared" in rendered["extensions"]


def test_dotted_table_and_column_names_are_loud():
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="s")
    tables = schema.tables()
    with pytest.raises(ValueError, match="separator"):
        tables.table(name="bad.table")
    table = tables.table(name="t")
    with pytest.raises(ValueError, match="separator"):
        table.columns().column(name="bad.column")


def test_column_rejects_non_column_child():
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="p")
    t = schema.tables().table(name="t")
    col = t.columns().column(name="c", dtype="L")
    with pytest.raises(ValueError):
        col.column(name="nested", dtype="L")


def test_virtual_column_rejects_relation():
    """A virtual column reads through an existing relation, never its own."""
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="p")
    t = schema.tables().table(name="t")
    fc = t.virtual_columns().formulaColumn(name="f", sql_formula="1")
    with pytest.raises(ValueError):
        fc.relation(to="p.other.id")


def test_relation_is_at_most_one_per_column():
    """The violation is reported by domain validation, not grammar validation."""
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="p")
    t = schema.tables().table(name="t")
    col = t.columns().column(name="c", dtype="L")
    col.relation(to="p.a.id")
    assert model.validate_source() == []
    col.relation(to="p.b.id")
    assert model.validate_source() == []
    with pytest.raises(ValueError, match="at most one"):
        model.validate_model()


def test_relations_with_the_same_local_structural_key_are_loud():
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="s")
    tables = schema.tables()
    for name in ("a", "b"):
        target = tables.table(name=name, pkey="x,y")
        target_columns = target.columns()
        target_columns.column(name="x", dtype="L")
        target_columns.column(name="y", dtype="L")
    source = tables.table(name="source", pkey="id")
    source_columns = source.columns()
    source_columns.column(name="id", dtype="serial")
    source_columns.column(name="x", dtype="L")
    source_columns.column(name="y", dtype="L")
    composites = source.composites()
    first = composites.compositeColumn(name="first", columns="x,y")
    second = composites.compositeColumn(name="second", columns="x,y")
    first.relation(to="s.a", foreign_key=True)
    second.relation(to="s.b", foreign_key=True)
    with pytest.raises(SqlModelValidationError, match="at most one"):
        model.validate_model()


def test_undeclared_attribute_is_rejected_where_the_signature_is_closed():
    """``db`` declares no ``**extra``, so a typo cannot become an attribute."""
    model = _mount()
    with pytest.raises(ValueError):
        model.source.db(name="d", dbnmae="typo")


def test_extra_attributes_are_carried_where_the_signature_is_open():
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="p")
    t = schema.tables().table(name="t")
    t.columns().column(name="c", dtype="L", x_widget="slider")
    node = model.source.get_node("db.schemas.p.tables.t.columns.c")
    assert node.get_attr("x_widget") == "slider"


def test_dtype_must_be_a_known_code():
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="p")
    t = schema.tables().table(name="t")
    with pytest.raises(ValueError):
        t.columns().column(name="c", dtype="NOPE")


def test_constraint_type_must_be_known():
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="p")
    t = schema.tables().table(name="t")
    with pytest.raises(ValueError):
        t.constraints().constraint(
            name="x", constraint_type="EXCLUDE", columns="c",
        )


def test_projection_flags_ride_on_the_nodes():
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="p")
    t = schema.tables().table(name="t")
    columns = t.columns()
    columns.column(name="a", dtype="L")
    columns.column(name="b", dtype="L")
    t.composites().compositeColumn(name="ab", columns="a,b")
    t.virtual_columns().formulaColumn(name="f", sql_formula="1")
    col = model.source.get_node("db.schemas.p.tables.t.columns.a")
    composite = model.source.get_node("db.schemas.p.tables.t.composites.ab")
    formula = model.source.get_node("db.schemas.p.tables.t.virtual_columns.f")
    assert col._get_meta("projects_column") is True
    assert col._get_meta("projects_relation") is True
    assert composite._get_meta("projects_column") is None
    assert composite._get_meta("projects_relation") is True
    assert formula._get_meta("projects_column") is None
    assert formula._get_meta("projects_relation") is None


def test_out_of_scope_elements_are_absent():
    for gone in ("view", "function", "sequence", "dbtype", "trigger",
                 "eventTrigger"):
        assert gone not in SqlBuilder._class_schema, gone


def test_composite_target_resolves_to_its_member_columns():
    """D4: a multi-column FK to a non-pkey key targets a composite."""
    normalized = JsonStructureProducer({
        "db": "d",
        "schemas": [{"name": "s", "tables": [
            {"name": "parent", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"},
                         {"name": "a", "dtype": "L"},
                         {"name": "b", "dtype": "L"}],
             "constraints": [{"type": "UNIQUE", "columns": ["a", "b"]}]},
            {"name": "child", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"},
                         {"name": "pa", "dtype": "L"},
                         {"name": "pb", "dtype": "L"}],
             "relations": [
                 {"columns": ["pa", "pb"], "related_schema": "s",
                  "related_table": "parent", "related_columns": ["a", "b"]},
             ]},
        ]}],
    }).get_json_struct()
    builder = SqlModelReader(normalized).to_builder()
    relation = builder.source.query(
        "#n", deep=True, condition=lambda n: n.node_tag == "relation")[0]
    assert relation.get_attr("to") == "s.parent.a_b"
    assert json_equal(normalized, SqlMigrationRenderer(builder).render())


def test_relation_deferral_forms_project_exactly():
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="s")
    tables = schema.tables()
    parent = tables.table(name="parent", pkey="id")
    parent.columns().column(name="id", dtype="serial")
    child = tables.table(name="child", pkey="id")
    child_columns = child.columns()
    child_columns.column(name="id", dtype="serial")
    immediate = child_columns.column(name="immediate_id", dtype="L")
    immediate.relation(
        to="s.parent.id", foreign_key=True, deferrable=True,
    )
    deferred = child_columns.column(name="deferred_id", dtype="L")
    deferred.relation(to="s.parent.id", foreign_key=True, deferred=True)

    rendered = SqlMigrationRenderer(model).render()
    relations = rendered["root"]["schemas"]["s"]["tables"]["child"][
        "relations"
    ].values()
    attributes = {tuple(item["attributes"]["columns"]): item["attributes"]
                  for item in relations}
    assert attributes[("immediate_id",)]["deferrable"] is True
    assert "initially_deferred" not in attributes[("immediate_id",)]
    assert attributes[("deferred_id",)]["deferrable"] is True
    assert attributes[("deferred_id",)]["initially_deferred"] is True

    source = SqlPythonEmitter(model).emit()
    assert "deferrable=True" in source
    assert "deferred=True" in source
    namespace = {}
    exec(compile(source, "<phase-13>", "exec"), namespace)  # noqa: S102
    rebuilt = namespace["ImportedDatabase"]()
    rebuilt.create()
    assert json_equal(rendered, SqlMigrationRenderer(rebuilt).render())


def test_initially_deferred_requires_effective_deferrability():
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="s")
    tables = schema.tables()
    parent = tables.table(name="parent", pkey="id")
    parent.columns().column(name="id", dtype="serial")
    child = tables.table(name="child", pkey="id")
    child_columns = child.columns()
    child_columns.column(name="id", dtype="serial")
    column = child_columns.column(name="parent_id", dtype="L")
    column.relation(to="s.parent.id", initially_deferred=True)
    with pytest.raises(SqlModelValidationError, match="initially_deferred"):
        model.validate_model()


def test_named_multicolumn_unique_remains_explicit():
    normalized = JsonStructureProducer({
        "db": "d", "schemas": [{"name": "s", "tables": [{
            "name": "account", "pkey": "id",
            "columns": [{"name": "id", "dtype": "serial"},
                        {"name": "tenant_id", "dtype": "L"},
                        {"name": "email", "dtype": "T"}],
            "constraints": [{
                "name": "uq_account_tenant_email", "type": "UNIQUE",
                "columns": ["tenant_id", "email"],
            }],
        }]}],
    }).get_json_struct()
    builder = SqlModelReader(normalized).to_builder()
    constraints = builder.source.query(
        "#n", deep=True, condition=lambda node: node.node_tag == "constraint",
    )
    assert [node.get_attr("name") for node in constraints] == [
        "uq_account_tenant_email",
    ]
    assert json_equal(normalized, SqlMigrationRenderer(builder).render())


def test_reader_translates_builder_name_errors_to_json_paths():
    normalized = JsonStructureProducer({
        "db": "d", "schemas": [{"name": "s", "tables": [{
            "name": "bad.table", "columns": [{"name": "id", "dtype": "L"}],
        }]}],
    }).get_json_struct()
    with pytest.raises(
        SqlModelReadError, match=r"root\.schemas\.s\.tables\.bad\.table",
    ):
        SqlModelReader(normalized).to_builder()


def test_default_migrator_ignores_fk_name_only_differences():
    normalized = JsonStructureProducer({
        "db": "d", "schemas": [{"name": "s", "tables": [
            {"name": "parent", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"}]},
            {"name": "child", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"},
                         {"name": "parent_id", "dtype": "L"}],
             "relations": [{
                 "name": "child_parent_id_fkey", "columns": ["parent_id"],
                 "related_schema": "s", "related_table": "parent",
                 "related_columns": ["id"],
             }]},
        ]}],
    }).get_json_struct()
    rendered = SqlMigrationRenderer(SqlModelReader(normalized).to_builder()).render()
    migrator = SqlMigrator(object())
    migrator.sqlStructure = deepcopy(normalized)
    migrator.ormStructure = rendered
    migrator.commands = nested_defaultdict()
    events = list(migrator.dictDifferChanges())
    assert [(event, item["changed_attribute"]) for event, item in events] == [
        ("changed", "constraint_name"),
    ]
    for event, item in events:
        getattr(migrator, f"{event}_{item['entity']}")(**item)
    assert migrator.getChanges() == ""


def test_dtype_defaults_cover_sized_and_unsized_columns():
    model = _mount()
    schema = model.source.db(name="d").schemas().schema(name="s")
    table = schema.tables().table(name="t")
    table_columns = table.columns()
    table_columns.column(name="sized", size="0:80")
    table_columns.column(name="unsized")
    columns = SqlMigrationRenderer(model).render()["root"]["schemas"]["s"][
        "tables"
    ]["t"]["columns"]
    assert columns["sized"]["attributes"]["dtype"] == "A"
    assert columns["unsized"]["attributes"]["dtype"] == "T"


def test_emitter_disambiguates_colliding_python_identifiers():
    normalized = JsonStructureProducer({
        "db": "d", "schemas": [{"name": "s", "tables": [
            {"name": "a-b", "columns": [{"name": "id", "dtype": "L"}]},
            {"name": "a_b", "columns": [{"name": "id", "dtype": "L"}]},
        ]}],
    }).get_json_struct()
    source = SqlPythonEmitter(SqlModelReader(normalized).to_builder()).emit()
    assert "a_b = tables.table(" in source
    assert "a_b_2 = tables.table(" in source
    namespace = {}
    exec(compile(source, "<identifier-collision>", "exec"), namespace)  # noqa: S102
    rebuilt = namespace["ImportedDatabase"]()
    rebuilt.create()
    assert json_equal(normalized, SqlMigrationRenderer(rebuilt).render())


def test_generated_relation_docs_name_domain_validation():
    relation_section = generate_grammar_md().split("### `relation`", 1)[1]
    assert "SqlBuilder.validate_model" in relation_section
    assert "SqlBuilder.validate_source" not in relation_section
