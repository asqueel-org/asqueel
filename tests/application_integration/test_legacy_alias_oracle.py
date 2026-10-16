"""Executable source oracle for legacy alias metadata only (no framework or DB).

The extracted AliasColumnWrapper is run with DbModelObj=object and a stand-in
column. This exercises the real merge/delegation method, not legacy resolution,
SQL compilation or Bag integration. Source baseline: Genropy fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea.
Set GENRO_LEGACY_ROOT to another checkout to explicitly test that source instead.
"""
import ast
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from asqueel import SqlDatabaseConfig, resolve_model


def test_legacy_alias_inherits_attributes_overrides_locally_and_delegates_dtype():
    root = Path(os.environ.get('GENRO_LEGACY_ROOT', '/Users/gporcari/Sviluppo/Genropy/genropy'))
    path = root / 'gnrpy/gnr/sql/gnrsqlmodel/columns.py'
    if not path.is_file():
        pytest.skip('Optional legacy source oracle requires GENRO_LEGACY_ROOT checkout')
    tree = ast.parse(path.read_text())
    wrapper = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == 'AliasColumnWrapper')
    module = ast.Module(body=[ast.ImportFrom(module='__future__',
                                            names=[ast.alias(name='annotations')], level=0),
                              wrapper], type_ignores=[])
    namespace = {'DbModelObj': object}
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), namespace)
    original = SimpleNamespace(attributes={'dtype': 'I', 'name_long': 'Original',
                                           'format': '#,###', 'virtual_column': True},
                               dtype='I')
    alias_attributes = {'tag': 'aliasColumn', 'relation_path': '@customer.id',
                        'name_long': 'Customer identifier'}
    alias = namespace['AliasColumnWrapper'](original, alias_attributes)
    assert alias.attributes == {'dtype': 'I', 'name_long': 'Customer identifier', 'format': '#,###'}
    assert alias.dtype == 'I'
    assert alias.sqlclass == 'virtual_column'
    assert alias.relation_path == '@customer.id'
    assert alias.originalColumn is original
    assert original.attributes['name_long'] == 'Original'
    assert alias_attributes['tag'] == 'aliasColumn'

    config = SqlDatabaseConfig()
    pkg = config.source.db('aliases').packages().package('app')
    target = pkg.table('customer', pkey='id')
    target.column('id', dtype='I', name_long='Original', x_legacy_format='#,###')
    source = pkg.table('source')
    source.column('customer', dtype='I').relation('app.customer.id')
    source.aliasColumn('identifier', relation_path='@customer.id', name_long='Customer identifier')
    modern_alias = resolve_model(config).table('app.source').column('identifier')
    assert modern_alias.dtype == alias.dtype
    for key in ('dtype', 'name_long'):
        assert modern_alias.attributes[key] == alias.attributes[key]
    assert modern_alias.attributes['x_legacy_format'] == alias.attributes['format']
    assert modern_alias.relation_path == alias.relation_path
