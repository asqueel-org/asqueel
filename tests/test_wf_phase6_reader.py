# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 6 contract — SqlModelReader: normalized JSON to source tree.

Round-trip law: JSON A -> to_builder() -> SqlMigrationRenderer.render()
-> JSON B, with json_equal(A, B). Fixtures are authored as human JSON and
normalized through JsonStructureProducer, so the law reads:
producer(human) == render(reader(producer(human))).
"""
from __future__ import annotations

import pytest

from asqueel_migration import JsonStructureProducer
from asqueel_migration.structures import DTYPE_CODES, json_equal

from asqueel import SqlMigrationRenderer, SqlModelReader


def _roundtrip(human_json):
    normalized = JsonStructureProducer(human_json).get_json_struct()
    builder = SqlModelReader(normalized).to_builder()
    rendered = SqlMigrationRenderer(builder).render()
    assert json_equal(normalized, rendered), (normalized, rendered)
    return builder


def test_minimal_table():
    _roundtrip({
        "db": "mini",
        "schemas": [{"name": "s", "tables": [
            {"name": "t", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"}]},
        ]}],
    })


def test_all_dtypes_roundtrip():
    sized = {"A": "0:80", "C": "4", "N": "10,2"}
    columns = [{"name": "id", "dtype": "serial"}] + [
        {"name": f"col_{dtype.lower()}", "dtype": dtype,
         **({"size": sized[dtype]} if dtype in sized else {})}
        for dtype in DTYPE_CODES if dtype != "serial"
    ]
    _roundtrip({
        "db": "types",
        "schemas": [{"name": "s", "tables": [
            {"name": "t", "pkey": "id", "columns": columns},
        ]}],
    })


def test_composite_pkey_and_composite_unique():
    _roundtrip({
        "db": "d",
        "schemas": [{"name": "s", "tables": [
            {"name": "t", "pkey": "a,b",
             "columns": [{"name": "a", "dtype": "L"},
                         {"name": "b", "dtype": "L"},
                         {"name": "c", "dtype": "A", "size": "0:10"}],
             "constraints": [
                 {"type": "UNIQUE", "columns": ["b", "c"]},
             ]},
        ]}],
    })


def test_check_constraint_and_comments_unicode():
    _roundtrip({
        "db": "d",
        "schemas": [{"name": "s", "tables": [
            {"name": "t", "pkey": "id", "comment": "tabella è — “quoted”",
             "columns": [
                 {"name": "id", "dtype": "serial"},
                 {"name": "v", "dtype": "I", "comment": "valore €"},
             ],
             "constraints": [
                 {"type": "CHECK", "name": "ck_v", "check_clause": "(v > 0)"},
             ]},
        ]}],
    })


def test_single_column_fk_with_actions_and_deferrable():
    builder = _roundtrip({
        "db": "d",
        "schemas": [{"name": "s", "tables": [
            {"name": "parent", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"}]},
            {"name": "child", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"},
                         {"name": "parent_id", "dtype": "L"}],
             "relations": [
                 {"columns": ["parent_id"], "related_schema": "s",
                  "related_table": "parent", "related_columns": ["id"],
                  "on_delete": "CASCADE", "on_update": "SET NULL",
                  "deferrable": True, "initially_deferred": True},
             ]},
        ]}],
    })
    # single-column FK re-nests under its source column
    rel_nodes = builder.source.query(
        "#n", deep=True, condition=lambda n: n.node_tag == "relation")
    assert len(rel_nodes) == 1


def test_multicolumn_fk_synthesizes_deterministic_composites():
    builder = _roundtrip({
        "db": "geo",
        "schemas": [{"name": "geo", "tables": [
            {"name": "city", "pkey": "country_code,code",
             "columns": [{"name": "country_code", "dtype": "C", "size": "2"},
                         {"name": "code", "dtype": "C", "size": "4"}]},
            {"name": "address", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"},
                         {"name": "c1", "dtype": "C", "size": "2"},
                         {"name": "c2", "dtype": "C", "size": "4"}],
             "relations": [
                 {"columns": ["c1", "c2"], "related_schema": "geo",
                  "related_table": "city",
                  "related_columns": ["country_code", "code"]},
             ]},
        ]}],
    })
    # D4: composite named "_".join(columns)
    assert builder.source[
        "db.schemas.geo.tables.address.composites.c1_c2"
    ] is not None


def test_composite_name_collision_gets_stable_suffix():
    # wf:contract: if the readable composite name collides with an existing
    # wf:contract: column, SqlModelReader uses the deterministic suffix ``_2``.
    human = {
        "db": "geo",
        "schemas": [{"name": "geo", "tables": [
            {"name": "city", "pkey": "a,b",
             "columns": [{"name": "a", "dtype": "L"},
                         {"name": "b", "dtype": "L"}]},
            {"name": "t", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"},
                         {"name": "x", "dtype": "L"},
                         {"name": "y", "dtype": "L"},
                         {"name": "x_y", "dtype": "L"}],
             "relations": [
                 {"columns": ["x", "y"], "related_schema": "geo",
                  "related_table": "city", "related_columns": ["a", "b"]},
             ]},
        ]}],
    }
    normalized = JsonStructureProducer(human).get_json_struct()
    builder = SqlModelReader(normalized).to_builder()
    assert builder.source["db.schemas.geo.tables.t.composites.x_y_2"] is not None
    assert json_equal(normalized, SqlMigrationRenderer(builder).render())


def test_index_with_sort_where_method_options():
    _roundtrip({
        "db": "d",
        "schemas": [{"name": "s", "tables": [
            {"name": "t", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"},
                         {"name": "a", "dtype": "I"},
                         {"name": "b", "dtype": "A", "size": "0:20"}],
             "indexes": [
                 {"columns": {"a": None, "b": "DESC"}, "unique": True,
                  "method": "btree", "where": "(a > 0)",
                  "with_options": {"fillfactor": "70"}},
             ]},
        ]}],
    })


def test_two_schemas_same_table_names():
    _roundtrip({
        "db": "d",
        "schemas": [
            {"name": "one", "tables": [
                {"name": "t", "pkey": "id",
                 "columns": [{"name": "id", "dtype": "serial"}]}]},
            {"name": "two", "tables": [
                {"name": "t", "pkey": "id",
                 "columns": [{"name": "id", "dtype": "serial"}]}]},
        ],
    })


def test_extensions_roundtrip():
    _roundtrip({
        "db": "d",
        "extensions": ["pg_trgm", "uuid-ossp"],
        "schemas": [{"name": "s", "tables": [
            {"name": "t", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"}]},
        ]}],
    })


def test_unknown_attribute_key_is_a_loud_error():
    # wf:contract: strict mode — an attribute key outside the structure-1.0
    # wf:contract: contract raises with the JSON path, never silently kept.
    normalized = JsonStructureProducer({
        "db": "d",
        "schemas": [{"name": "s", "tables": [
            {"name": "t", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"}]},
        ]}],
    }).get_json_struct()
    normalized["root"]["schemas"]["s"]["tables"]["t"]["columns"]["id"][
        "attributes"]["mystery"] = 1
    with pytest.raises(Exception, match="mystery"):
        SqlModelReader(normalized).to_builder()
