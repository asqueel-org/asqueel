# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 13 contract — exact reverse semantics with GenroPy compatibility."""
from __future__ import annotations

from copy import deepcopy

import pytest

from genro_sqlmigration import JsonStructureProducer
from genro_sqlmigration.structures import json_equal

from genro_sql import SqlMigrationRenderer, SqlModelReader
from genro_sql.reader import SqlModelReadError


def _normalized(tables):
    return JsonStructureProducer({
        "db": "d", "schemas": [{"name": "s", "tables": tables}],
    }).get_json_struct()


def _without_fk_names(structure):
    result = deepcopy(structure)
    for schema in result["root"]["schemas"].values():
        for table in schema["tables"].values():
            for relation in table["relations"].values():
                relation["attributes"].pop("constraint_name", None)
    return result


def _roundtrip(structure):
    builder = SqlModelReader(structure).to_builder()
    return builder, SqlMigrationRenderer(builder).render()


def test_deferrable_immediate_and_deferred_sugar_are_distinct():
    immediate = _normalized([
        {"name": "parent", "pkey": "id",
         "columns": [{"name": "id", "dtype": "serial"}]},
        {"name": "child", "pkey": "id",
         "columns": [{"name": "id", "dtype": "serial"},
                     {"name": "parent_id", "dtype": "L"}],
         "relations": [{
             "columns": ["parent_id"], "related_schema": "s",
             "related_table": "parent", "related_columns": ["id"],
             "deferrable": True,
         }]},
    ])
    builder, rendered = _roundtrip(immediate)
    assert json_equal(immediate, rendered)
    relation = builder.source.query(
        "#n", deep=True, condition=lambda node: node.node_tag == "relation",
    )[0]
    assert relation.get_attr("deferrable") is True
    assert not relation.get_attr("initially_deferred")
    assert not relation.get_attr("deferred")


def test_ambiguous_joined_composite_names_roundtrip_losslessly():
    structure = _normalized([
        {"name": "p1", "pkey": "x,y",
         "columns": [{"name": "x", "dtype": "L"},
                     {"name": "y", "dtype": "L"}]},
        {"name": "p2", "pkey": "x,y",
         "columns": [{"name": "x", "dtype": "L"},
                     {"name": "y", "dtype": "L"}]},
        {"name": "child", "pkey": "id",
         "columns": [{"name": "id", "dtype": "serial"},
                     {"name": "a_b", "dtype": "L"},
                     {"name": "c", "dtype": "L"},
                     {"name": "a", "dtype": "L"},
                     {"name": "b_c", "dtype": "L"}],
         "relations": [
             {"columns": ["a_b", "c"], "related_schema": "s",
              "related_table": "p1", "related_columns": ["x", "y"]},
             {"columns": ["a", "b_c"], "related_schema": "s",
              "related_table": "p2", "related_columns": ["x", "y"]},
         ]},
    ])
    _builder, rendered = _roundtrip(structure)
    assert json_equal(structure, rendered)


def test_single_column_hash_named_unique_roundtrips_as_a_constraint():
    structure = _normalized([
        {"name": "account", "pkey": "id",
         "columns": [{"name": "id", "dtype": "serial"},
                     {"name": "email", "dtype": "T"}],
         "constraints": [{"type": "UNIQUE", "columns": ["email"]}]},
    ])
    builder, rendered = _roundtrip(structure)
    assert json_equal(structure, rendered)
    constraints = builder.source.query(
        "#n", deep=True, condition=lambda node: node.node_tag == "constraint",
    )
    assert len(constraints) == 1


def test_readable_fk_name_is_nonsemantic_recipe_metadata():
    structure = _normalized([
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
    ])
    builder, rendered = _roundtrip(structure)
    assert json_equal(_without_fk_names(structure), _without_fk_names(rendered))
    relation = builder.source.query(
        "#n", deep=True, condition=lambda node: node.node_tag == "relation",
    )[0]
    assert relation.get_attr("name") is None
    assert relation.get_attr("constraint_name") is None


def test_unrepresentable_reader_inputs_are_loud_with_the_json_path():
    external = _normalized([
        {"name": "child", "pkey": "a,b",
         "columns": [{"name": "a", "dtype": "L"},
                     {"name": "b", "dtype": "L"}],
         "relations": [{
             "columns": ["a", "b"], "related_schema": "outside",
             "related_table": "parent", "related_columns": ["a", "b"],
         }]},
    ])
    with pytest.raises(SqlModelReadError, match="outside|relations"):
        SqlModelReader(external).to_builder()

    event_trigger = _normalized([])
    event_trigger["root"]["event_triggers"] = {"audit": {}}
    with pytest.raises(SqlModelReadError, match="event_triggers"):
        SqlModelReader(event_trigger).to_builder()
