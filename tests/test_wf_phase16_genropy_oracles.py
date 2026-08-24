# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 16 contract — GenroPy structure oracle and live inspection.

Runtime and model-composition APIs are outside this migration-structure comparison.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from genro_sqlmigration import SqlMigrator, StructureValidator
from genro_sqlmigration.structures import json_equal

from genro_sql import (
    SqlBuilder,
    SqlMigrationRenderer,
    SqlModelReader,
    SqlPythonEmitter,
)


class GenroPyVideoSubset(SqlBuilder):
    def main(self, root):
        # GenroPy source (verbatim selected excerpt):
        # def configurePackage(pkg):
        #     pkg.attributes.update(comment='video package', name_short='video', name_long='video', name_full='video')
        #     people = pkg.table('people', name_short='people', name_long='People',
        #                        rowcaption='name,year:%s (%s)', pkey='id')
        #     people.column('id', 'L')
        #     cast = pkg.table('cast', name_short='cast', name_long='Cast',
        #                      rowcaption='', pkey='id')
        #     cast.column('id', 'L')
        #     cast.column('person_id', 'L', name_short='Prs',
        #                 name_long='Person id').relation('people.id')

        # Explicit recipe for the same complete model:
        video = root.db(name="mydb").schemas().schema(name="video")
        tables = video.tables()
        people = tables.table(name="video_people", pkey="id")
        people.columns().column(name="id", dtype="L")
        cast = tables.table(name="video_cast", pkey="id")
        cast_columns = cast.columns()
        cast_columns.column(name="id", dtype="L")
        # Legacy navigation materializes the supporting index.
        person_id = cast_columns.column(
            name="person_id", dtype="L", indexed=True,
        )
        person_id.relation(to="video.video_people.id", foreign_key=False)


class DescendingIndexRecipe(SqlBuilder):
    def main(self, root):
        schema = root.db(name="inspection").schemas().schema(name="wfp16")
        recipe = schema.tables().table(name="recipe", pkey="id")
        columns = recipe.columns()
        columns.column(name="id", dtype="serial")
        columns.column(name="title", dtype="A", size="0:120")
        recipe.indexes().index(
            name="ix_recipe_title_id",
            columns={"title": None, "id": "DESC"},
        )


def _model(builder_type):
    model = builder_type()
    model.create()
    return model


def test_verbatim_legacy_declaration_builds_the_modern_source_tree():
    model = _model(GenroPyVideoSubset)
    people = model.source["db.schemas.video.tables.video_people"]
    cast = model.source["db.schemas.video.tables.video_cast"]
    person_id = model.source[
        "db.schemas.video.tables.video_cast.columns.person_id"
    ]
    relation = next(node for node in person_id.value if node.node_tag == "relation")

    assert people.get_attr("pkey") == "id"
    assert cast.get_attr("pkey") == "id"
    assert model.source[
        "db.schemas.video.tables.video_people.columns.id"
    ].get_attr("dtype") == "L"
    assert model.source[
        "db.schemas.video.tables.video_cast.columns.id"
    ].get_attr("dtype") == "L"
    assert person_id.get_attr("dtype") == "L"
    assert person_id.get_attr("indexed") is True
    assert relation.get_attr("to") == "video.video_people.id"
    assert relation.get_attr("foreign_key") is False


def test_real_genropy_orm_json_equals_the_complete_modern_projection():
    oracle_path = Path(__file__).parent / "oracles" / "genropy_video_subset_orm.json"
    bundle = json.loads(oracle_path.read_text(encoding="utf-8"))
    provenance = bundle["provenance"]
    legacy = bundle["structure"]

    assert provenance["generator"] == (
        "gnr.sql.gnrsqlmigration.orm_extractor.OrmExtractor"
    )
    assert re.fullmatch(r"[0-9a-f]{40}", provenance["genropy_commit"])
    assert provenance["source"] == "gnrpy/tests/sql/common.py::configurePackage"
    StructureValidator().validate(legacy)
    modern = SqlMigrationRenderer(_model(GenroPyVideoSubset)).render()
    assert json_equal(legacy, modern)


@pytest.mark.postgresql
def test_live_inspection_preserves_descending_order_and_builds_a_recipe(pg_database):
    desired = SqlMigrationRenderer(_model(DescendingIndexRecipe)).render()
    desired_index = next(iter(
        desired["root"]["schemas"]["wfp16"]["tables"]["recipe"]["indexes"].values()
    ))
    assert desired_index["entity_name"] == "idx_0419f7f4"
    assert desired_index["attributes"]["index_name"] == "ix_recipe_title_id"

    migrator = SqlMigrator(pg_database)
    migrator.ormStructure = desired
    migrator.prepareMigrationCommands()
    migrator.applyChanges()

    inspected = pg_database.get_json_struct()
    recovered = SqlModelReader(inspected).to_builder()
    table = recovered.source["db.schemas.wfp16.tables.recipe"]
    index_nodes = recovered.source["db.schemas.wfp16.tables.recipe.indexes"]
    indexes = {
        node.get_attr("name"): node
        for node in index_nodes.value
    }
    assert "ix_recipe_title_id" in indexes, indexes
    index = indexes["ix_recipe_title_id"]
    source = SqlPythonEmitter(recovered).emit()

    assert index.get_attr("columns") == {"title": None, "id": "DESC"}
    assert 'name="ix_recipe_title_id"' in source
    assert 'columns={"title": None, "id": "DESC"}' in source
    assert json_equal(inspected, SqlMigrationRenderer(recovered).render())
