"""Compile unchanged literal select specifications extracted from a legacy model.

This exercises real declarations, not the legacy query executor. The optional
source checkout is never imported or modified.
"""
import ast
import os
from pathlib import Path

import pytest

from genro_sql import SqlDatabaseConfig, build_database


def literal(node):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == 'dict' and not node.args
            and all(keyword.arg is not None for keyword in node.keywords)):
        return {keyword.arg: literal(keyword.value) for keyword in node.keywords}
    return ast.literal_eval(node)


def test_legacy_task_formula_select_dictionaries_compile_unchanged():
    root = Path(os.environ.get('GENRO_LEGACY_ROOT', '/Users/gporcari/Sviluppo/Genropy/genropy'))
    path = root / 'projects/gnrcore/packages/sys/model/task.py'
    if not path.is_file():
        pytest.skip('Optional legacy declaration probe requires GENRO_LEGACY_ROOT')
    tree = ast.parse(path.read_text())
    names = {'active_workers', 'last_result_ts', 'last_completed', 'last_error'}
    declarations = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'formulaColumn' and node.args
                and isinstance(node.args[0], ast.Constant) and node.args[0].value in names):
            declarations[node.args[0].value] = {
                keyword.arg: literal(keyword.value) for keyword in node.keywords
                if keyword.arg in {'select', 'dtype', 'name_long'}
            }
    assert declarations.keys() == names

    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            tables = root.db('legacy_probe').schemas().schema('sys').tables()
            task = tables.table('task', pkey='id')
            task.columns().column('id', dtype='I')
            for table_name in ('task_execution', 'task_result'):
                columns = tables.table(table_name, pkey='id').columns()
                columns.column('id', dtype='I')
                columns.column('task_id', dtype='I')
                columns.column('is_error', dtype='B')
                for timestamp in ('start_ts', 'end_ts', 'start_time'):
                    columns.column(timestamp, dtype='DH')
            virtuals = task.virtual_columns()
            for name, attributes in declarations.items():
                virtuals.formulaColumn(name, **attributes)

    with build_database(Recipe) as db:
        for name, attributes in declarations.items():
            column = db.table('sys.task').column(name).model
            assert dict(column.select) == attributes['select']
            query = db.table('sys.task').query(columns=f'${name}').compiled
            assert '#THIS' not in query.sql
            assert 'SELECT' in query.sql
            assert 'LIMIT 1' in query.sql if 'limit' in attributes['select'] else 'LIMIT 1' not in query.sql
