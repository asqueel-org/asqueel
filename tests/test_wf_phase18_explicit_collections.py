# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 18 contract — explicit authoring collections, stable projection."""

import pytest

from genro_sqlmigration import JsonStructureProducer
from genro_sqlmigration.structures import json_equal

from genro_sql import (
    SqlBuilder,
    SqlMigrationRenderer,
    SqlModelReader,
    SqlPythonEmitter,
)


class _ExplicitRecipe(SqlBuilder):
    def main(self, root):
        db = root.db("recipes")
        schemas = db.schemas()
        public = schemas.schema("public")
        tables = public.tables()

        author = tables.table("author", pkey="id")
        author_columns = author.columns()
        author_columns.column("id", dtype="serial")

        recipe = tables.table("recipe", pkey="id")
        recipe_columns = recipe.columns()
        recipe_columns.column("id", dtype="serial")
        author_id = recipe_columns.column("author_id", dtype="L")
        author_id.relation("public.author.id", foreign_key=True)
        recipe_virtual = recipe.virtual_columns()
        recipe_virtual.aliasColumn("author_name", relation_path="@author_id.name")
        recipe_composites = recipe.composites()
        recipe_composites.compositeColumn("identity", columns="id,author_id")
        recipe_constraints = recipe.constraints()
        recipe_constraints.constraint(
            "uq_recipe_author",
            constraint_type="UNIQUE",
            columns="id,author_id",
        )
        recipe_indexes = recipe.indexes()
        recipe_indexes.index("ix_recipe_author", columns="author_id")

        extensions = db.extensions()
        extensions.extension("pg_trgm")


_ORACLE = {
    "db": "recipes",
    "extensions": ["pg_trgm"],
    "schemas": [{
        "name": "public",
        "tables": [
            {
                "name": "author",
                "pkey": "id",
                "columns": [{"name": "id", "dtype": "serial"}],
            },
            {
                "name": "recipe",
                "pkey": "id",
                "columns": [
                    {"name": "id", "dtype": "serial"},
                    {"name": "author_id", "dtype": "L"},
                ],
                "relations": [{
                    "columns": ["author_id"],
                    "related_schema": "public",
                    "related_table": "author",
                    "related_columns": ["id"],
                }],
                "constraints": [{
                    "name": "uq_recipe_author",
                    "type": "UNIQUE",
                    "columns": ["id", "author_id"],
                }],
                "indexes": [
                    {"name": "ix_recipe_author", "columns": ["author_id"]},
                ],
            },
        ],
    }],
}


def test_explicit_collections_are_the_only_authoring_grammar():
    # wf:contract: the canonical chain is db.schemas().schema(...).tables()
    # wf:contract: .table(...).columns().column(...), with equivalent explicit
    # wf:contract: containers for extensions, virtual columns, composites,
    # wf:contract: constraints and indexes; skipping a container is loud.
    # wf:contract: singular column.relation(...) and compositeColumn.relation(...)
    # wf:contract: remain children of their source owner, never table.relations().
    model = _ExplicitRecipe()
    model.create()
    assert model.source["db.schemas.public.tables.recipe.columns.author_id"].node_tag == "column"
    assert model.source[
        "db.schemas.public.tables.recipe.columns.author_id.relation_0"
    ].node_tag == "relation"
    assert model.source[
        "db.schemas.public.tables.recipe.virtual_columns.author_name"
    ].node_tag == "aliasColumn"
    assert model.source[
        "db.schemas.public.tables.recipe.composites.identity"
    ].node_tag == "compositeColumn"

    bare = SqlBuilder()
    db = bare.source.db("d")
    with pytest.raises(ValueError, match="parent_tags"):
        db.schema("s")
    schemas = db.schemas()
    schema = schemas.schema("s")
    with pytest.raises(ValueError, match="parent_tags"):
        schema.table("t")
    tables = schema.tables()
    table = tables.table("t")
    with pytest.raises(ValueError, match="parent_tags"):
        table.column("id")
    with pytest.raises(AttributeError):
        table.relations()


def test_explicit_recipe_projects_and_round_trips_without_json_drift():
    # wf:contract: an explicit recipe renders strict-equal to the same complete
    # wf:contract: structure-1.0 oracle used before the containment change.
    # wf:contract: reader -> emitter produces only explicit-container syntax,
    # wf:contract: and compile -> exec -> create -> render closes strictly.
    model = _ExplicitRecipe()
    model.create()
    rendered = SqlMigrationRenderer(model).render()
    expected = JsonStructureProducer(_ORACLE).get_json_struct()
    assert json_equal(rendered, expected)

    recovered = SqlModelReader(rendered).to_builder()
    emitted = SqlPythonEmitter(recovered).emit()
    for call in (
        ".schemas()", ".tables()", ".columns()", ".constraints()",
        ".indexes()", ".extensions()",
    ):
        assert call in emitted
    namespace = {}
    exec(compile(emitted, "<explicit-recipe>", "exec"), namespace)
    rebuilt = namespace["ImportedDatabase"]()
    rebuilt.create()
    assert json_equal(rendered, SqlMigrationRenderer(rebuilt).render())
