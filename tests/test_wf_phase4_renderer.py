# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 4 contract — SqlMigrationRenderer: source tree to normalized JSON.

The golden oracle is JsonStructureProducer: the same physical model written
as a recipe and as a human JSON must converge on the same normalized dict
(codex/02 Slice B). StructureValidator guards the boundary.
"""
from __future__ import annotations

import json
import typing

import pytest

from asqueel_migration import JsonStructureProducer, StructureValidator
from asqueel_migration.structures import DTYPE_CODES, json_equal

from asqueel import SqlBuilder, SqlMigrationRenderer
from asqueel import elements
from asqueel.validators import SqlModelValidationError


class GoldenRecipe(SqlBuilder):
    def main(self, root):
        db = root.db(name="recipes")
        public = db.schemas().schema(name="public")
        tables = public.tables()

        author = tables.table(name="author", pkey="id", comment="Authors")
        author_columns = author.columns()
        author_columns.column(name="id", dtype="serial")
        author_columns.column(
            name="name", dtype="A", size="0:120", notnull=True,
            name_long="Author name", x_gui="hidden",
        )

        recipe = tables.table(name="recipe", pkey="id")
        recipe_columns = recipe.columns()
        recipe_columns.column(name="id", dtype="serial")
        recipe_columns.column(
            name="title", dtype="A", size="0:160", notnull=True,
        )
        author_id = recipe_columns.column(
            name="author_id", dtype="L", notnull=True,
        )
        author_id.relation(to="public.author.id", foreign_key=True,
                           on_delete="CASCADE", back_reference="recipes",
                           one_name="Author", many_name="Recipes")
        constraints = recipe.constraints()
        constraints.constraint(
            name="uq_author_title", constraint_type="UNIQUE",
            columns="author_id,title",
        )
        constraints.constraint(
            name="ck_title", constraint_type="CHECK",
            check_clause="(char_length(title) > 0)",
        )
        recipe.indexes().index(
            name="ix_title", columns={"title": None, "id": "DESC"},
        )

        db.extensions().extension(name="pg_trgm")


class _EmptyRecipe(SqlBuilder):
    def main(self, root):
        pass


GOLDEN_HUMAN_JSON = {
    "db": "recipes",
    "extensions": ["pg_trgm"],
    "schemas": [{
        "name": "public",
        "tables": [
            {
                "name": "author",
                "pkey": "id",
                "comment": "Authors",
                "columns": [
                    {"name": "id", "dtype": "serial"},
                    {"name": "name", "dtype": "A", "size": "0:120",
                     "notnull": True},
                ],
            },
            {
                "name": "recipe",
                "pkey": "id",
                "columns": [
                    {"name": "id", "dtype": "serial"},
                    {"name": "title", "dtype": "A", "size": "0:160",
                     "notnull": True},
                    {"name": "author_id", "dtype": "L", "notnull": True},
                ],
                "relations": [
                    {"columns": ["author_id"], "related_schema": "public",
                     "related_table": "author", "related_columns": ["id"],
                     "on_delete": "CASCADE"},
                ],
                "constraints": [
                    {"type": "UNIQUE", "name": "uq_author_title",
                     "columns": ["author_id", "title"]},
                    {"type": "CHECK", "name": "ck_title",
                     "check_clause": "(char_length(title) > 0)"},
                ],
                "indexes": [
                    {"name": "ix_title",
                     "columns": {"title": None, "id": "DESC"}},
                    # D3: FK column always indexed (legacy parity)
                    {"columns": ["author_id"]},
                ],
            },
        ],
    }],
}


def _render():
    model = GoldenRecipe()
    model.create()
    return SqlMigrationRenderer(model).render()


def test_golden_convergence_with_json_twin():
    rendered = _render()
    twin = JsonStructureProducer(GOLDEN_HUMAN_JSON).get_json_struct()
    assert json_equal(rendered, twin)


def test_output_passes_structure_validator():
    StructureValidator().validate(_render())


def test_semantic_plane_never_reaches_the_json():
    flat = json.dumps(_render())
    for banned in ("name_long", "one_name", "many_name", "back_reference",
                   "x_gui", "caption_field"):
        assert banned not in flat, banned


def test_render_returns_a_fresh_structure_each_call():
    model = GoldenRecipe()
    model.create()
    renderer = SqlMigrationRenderer(model)
    first, second = renderer.render(), renderer.render()
    assert first is not second
    assert json_equal(first, second)


def test_virtual_columns_do_not_project():
    class WithVirtuals(SqlBuilder):
        def main(self, root):
            tables = root.db(name="d").schemas().schema(name="s").tables()
            t = tables.table(name="t", pkey="id")
            t.columns().column(name="id", dtype="serial")
            virtual_columns = t.virtual_columns()
            virtual_columns.aliasColumn(name="al", relation_path="@rel.name")
            virtual_columns.formulaColumn(name="fx", sql_formula="1+1")
            virtual_columns.pyColumn(name="py", py_method="calc")
            virtual_columns.subQueryColumn(name="sq", query="select 1")

    model = WithVirtuals()
    model.create()
    cols = SqlMigrationRenderer(model).render()["root"]["schemas"]["s"][
        "tables"]["t"]["columns"]
    assert set(cols) == {"id"}


def test_composite_relation_projects_multicolumn_fk():
    class CompositeFk(SqlBuilder):
        def main(self, root):
            s = root.db(name="geo").schemas().schema(name="geo")
            tables = s.tables()
            country = tables.table(name="country", pkey="code")
            country.columns().column(name="code", dtype="C", size="2")
            city = tables.table(name="city", pkey="country_code,code")
            city_columns = city.columns()
            city_columns.column(name="country_code", dtype="C", size="2")
            city_columns.column(name="code", dtype="C", size="4")
            addr = tables.table(name="address", pkey="id")
            addr_columns = addr.columns()
            addr_columns.column(name="id", dtype="serial")
            addr_columns.column(name="c1", dtype="C", size="2")
            addr_columns.column(name="c2", dtype="C", size="4")
            cc = addr.composites().compositeColumn(
                name="city_key", columns="c1,c2",
            )
            cc.relation(to="geo.city", foreign_key=True)

    model = CompositeFk()
    model.create()
    rels = SqlMigrationRenderer(model).render()["root"]["schemas"]["geo"][
        "tables"]["address"]["relations"]
    (rel,) = rels.values()
    assert rel["attributes"]["columns"] == ["c1", "c2"]
    assert rel["attributes"]["related_columns"] == ["country_code", "code"]


def test_composite_unique_projects_unique_constraint():
    class CompositeUq(SqlBuilder):
        def main(self, root):
            tables = root.db(name="d").schemas().schema(name="s").tables()
            t = tables.table(name="t", pkey="id")
            columns = t.columns()
            columns.column(name="id", dtype="serial")
            columns.column(name="a", dtype="L")
            columns.column(name="b", dtype="L")
            t.composites().compositeColumn(
                name="ab", columns="a,b", unique=True,
            )

    model = CompositeUq()
    model.create()
    constraints = SqlMigrationRenderer(model).render()["root"]["schemas"][
        "s"]["tables"]["t"]["constraints"]
    (cst,) = constraints.values()
    assert cst["attributes"]["constraint_type"] == "UNIQUE"
    assert cst["attributes"]["columns"] == ["a", "b"]


def test_indexed_true_materializes_an_index_item():
    class Indexed(SqlBuilder):
        def main(self, root):
            tables = root.db(name="d").schemas().schema(name="s").tables()
            t = tables.table(name="t", pkey="id")
            columns = t.columns()
            columns.column(name="id", dtype="serial")
            columns.column(name="email", dtype="A", size="0:80", indexed=True)

    model = Indexed()
    model.create()
    table = SqlMigrationRenderer(model).render()["root"]["schemas"]["s"][
        "tables"]["t"]
    assert "indexed" not in table["columns"]["email"]["attributes"]
    assert any(
        list(ix["attributes"]["columns"]) == ["email"]
        for ix in table["indexes"].values()
    )


def test_dtype_and_fk_action_literals_match_the_installed_contract():
    # wf:contract: the Literal aliases declared in elements.py must
    # wf:contract: enumerate exactly asqueel_migration.structures.DTYPE_CODES
    # wf:contract: and the fk_action enum of schemas/structure-1.0.json
    # wf:contract: (RESTRICT, CASCADE, SET NULL, SET DEFAULT).
    assert set(typing.get_args(elements.DTYPE)) == set(DTYPE_CODES)
    assert set(typing.get_args(elements.FK_ACTION)) == {
        "RESTRICT", "CASCADE", "SET NULL", "SET DEFAULT"}


def test_duplicate_unique_structural_keys_are_loud():
    model = _EmptyRecipe()
    model.create()
    tables = model.source.db(name="d").schemas().schema(name="s").tables()
    table = tables.table(
        name="t", pkey="id",
    )
    columns = table.columns()
    columns.column(name="id", dtype="serial")
    columns.column(name="code", dtype="T")
    constraints = table.constraints()
    constraints.constraint(
        name="uq_one", constraint_type="UNIQUE", columns="code",
    )
    constraints.constraint(
        name="uq_two", constraint_type="UNIQUE", columns="code",
    )
    with pytest.raises(SqlModelValidationError, match="duplicate UNIQUE"):
        SqlMigrationRenderer(model).render()


def test_duplicate_index_structural_keys_are_loud():
    model = _EmptyRecipe()
    model.create()
    tables = model.source.db(name="d").schemas().schema(name="s").tables()
    table = tables.table(
        name="t", pkey="id",
    )
    columns = table.columns()
    columns.column(name="id", dtype="serial")
    columns.column(name="code", dtype="T")
    indexes = table.indexes()
    indexes.index(name="ix_one", columns="code")
    indexes.index(name="ix_two", columns="code", where="code IS NOT NULL")
    with pytest.raises(SqlModelValidationError, match="duplicate index"):
        SqlMigrationRenderer(model).render()
