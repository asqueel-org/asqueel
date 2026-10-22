"""All model ingress paths produce the same executable hierarchy."""
import json

import pytest

from asqueel import (DbModel, QueryCompiler, SqlDatabaseConfig, SqlDatabase,
                     model_from_json, model_to_json, resolve_model, to_physical_builder)
from asqueel.adapters.sqlite import SqlDbAdapter


def recipe():
    source = SqlDatabaseConfig()
    db = source.source.db('roundtrip', implementation='sqlite', conninfo='never-export-this')
    tables = db.schemas().schema('main').tables()
    owner = tables.table('owner', pkey='key')
    owner.column('code', 'T')
    owner.column('part', 'I')
    owner.composites().compositeColumn('key', columns='code,part')
    owner.column('label', 'T', indexed=True)
    owner.formulaColumn('caption', sql_formula="'doc:suffix' || $label || :suffix", var_suffix='!')
    child = tables.table('child', pkey='id')
    child.column('id', 'I')
    child.column('code', 'T')
    child.column('part', 'I')
    child.composites().compositeColumn('pair', columns='code,part').relation('main.owner', foreign_key=True)
    child.aliasColumn('caption', relation_path='@pair.caption')
    return source


def test_json_restores_compile_projection_identity_and_execution_without_configuration():
    model = resolve_model(recipe())
    document = model_to_json(model)
    assert 'never-export-this' not in document
    assert 'conninfo' not in json.loads(document)['database']['signatureDefaults']
    restored = model_from_json(document)
    assert isinstance(restored, DbModel)
    assert restored is not model
    assert model_to_json(restored) == document
    assert restored.table('main.child').columns['id'] is restored.column('main.child.id')
    adapter = SqlDbAdapter(None)
    for table, columns in [('main.owner', '$key,$caption'), ('main.child', '$id,$caption')]:
        first = QueryCompiler(model, adapter).select(table, columns=columns)
        second = QueryCompiler(restored, adapter).select(table, columns=columns)
        assert (first.sql, dict(first.params)) == (second.sql, dict(second.params))
    from asqueel import SqlMigrationRenderer
    assert SqlMigrationRenderer(to_physical_builder(model)).render() == SqlMigrationRenderer(to_physical_builder(restored)).render()
    def config(path, default=None):
        return {'implementation': 'sqlite', 'conninfo': ':memory:'}.get(path, default)
    db = SqlDatabase(model=restored, config=config)
    try:
        db.execute('CREATE TABLE owner(code TEXT, part INTEGER, label TEXT, PRIMARY KEY(code,part))')
        db.execute('CREATE TABLE child(id INTEGER PRIMARY KEY,code TEXT,part INTEGER)')
        db.table('main.owner').insert({'code': 'x', 'part': 2, 'label': 'Hello'})
        db.table('main.child').insert({'id': 1, 'code': 'x', 'part': 2})
        assert db.table('main.child').query(columns='$caption').fetch()[0]['caption'] == 'doc:suffixHello!'
    finally:
        db.closeConnection()


def test_json_rejects_runtime_code_and_old_descriptor_format():
    model = resolve_model(recipe())
    model.table('main.owner').attributes['x_table_class'] = object
    with pytest.raises(TypeError, match='symbolic data'):
        model_to_json(model)
    with pytest.raises(ValueError, match='format/version'):
        model_from_json('{"format":"asqueel.model","version":1,"model":{}}')
    data = json.loads(model_to_json(resolve_model(recipe())))
    data['database']['attributes']['connect_kwargs'] = {'password': 'secret'}
    with pytest.raises(ValueError, match='connection configuration'):
        model_from_json(json.dumps(data))


def test_json_and_projection_reject_what_is_not_a_hierarchical_model():
    model = resolve_model(recipe())
    model.table('main.owner').attributes['x_lookup'] = {1: 'one'}
    with pytest.raises(TypeError, match='string keys'):
        model_to_json(model)
    with pytest.raises(TypeError, match='requires DbModel'):
        model_to_json(object())
    with pytest.raises(TypeError, match='requires DbModel'):
        to_physical_builder(object())
    document = json.loads(model_to_json(resolve_model(recipe())))
    broken = json.loads(json.dumps(document))
    broken['namespaces']['generated'] = 'no'
    with pytest.raises(ValueError, match='Invalid hierarchical model node'):
        model_from_json(json.dumps(broken))
    broken = json.loads(json.dumps(document))
    broken['namespaces']['tag'] = 'tables'
    with pytest.raises(ValueError, match='database and its namespaces'):
        model_from_json(json.dumps(broken))
    broken = json.loads(json.dumps(document))
    broken['relations'] = broken['relations'][1:]
    with pytest.raises(ValueError, match='Relation registry'):
        model_from_json(json.dumps(broken))
