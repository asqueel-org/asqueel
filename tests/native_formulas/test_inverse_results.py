"""Verify every native child_count against rows, without changing its formula."""
from collections import Counter

import pytest


HIERARCHIES = ('sys.widget', 'adm.htag', 'adm.menu', 'invc.product_group', 'invc.product_type')
NODES = [(letter * 22, parent * 22 if parent else None)
         for letter, parent in [('a', None), ('b', 'a'), ('c', 'a'), ('d', 'b'),
                                ('e', None), ('f', 'z'), ('g', 'g')]]


@pytest.fixture(scope='module', params=['db_pg', 'db_sqlite'])
def hierarchy_db(request):
    db = request.getfixturevalue(request.param)
    quote = db.dialect.quote_identifier
    for key in HIERARCHIES:
        table = db.model.table(key)
        parent = table.relations['_children'].target_columns[0]
        target = f'{quote(table.physical_schema)}.{quote(table.physical_name)}'
        id_sql, parent_sql = [quote(table.columns[name].physical_name) for name in ('id', parent)]
        # Include the native visibility markers now read by the compiler.
        markers = []
        for name, dtype in [(table.policies.draft_field, 'BOOLEAN'),
                            (table.policies.logical_deletion_field, 'TIMESTAMP')]:
            if name:
                markers.append(f', {quote(table.columns[name].physical_name)} {dtype}')
        db.execute(f'CREATE TABLE {target} ({id_sql} TEXT PRIMARY KEY, {parent_sql} TEXT{"".join(markers)})')
        for identity, parent_id in NODES:
            db.execute(f'INSERT INTO {target} ({id_sql}, {parent_sql}) VALUES (:id,:parent_id)',
                       dict(id=identity, parent_id=parent_id))
    db.commit()
    return db


@pytest.mark.parametrize('key', HIERARCHIES)
def test_native_child_count_matches_direct_children_and_keeps_outer_rows(hierarchy_db, key):
    table = hierarchy_db.table(key)
    definition = table.model.columns['child_count'].attributes['select']
    assert definition['columns'] == 'COUNT(*)'
    assert definition['where'] == '@_children.parent_id=#THIS.id'
    counts = Counter(parent for _, parent in NODES if parent is not None)
    expected = [{'id': identity, 'child_count': counts[identity]} for identity, _ in NODES]
    query = table.query('$id,$child_count', order_by='$id')
    assert [dict(row) for row in query.fetch()] == expected
    assert [dict(row) for row in query.fetch()] == expected
    filtered = table.query('$id,$child_count', where='$child_count>:minimum',
                           minimum=1, order_by='$child_count DESC,$id').fetch()
    assert [dict(row) for row in filtered] == [dict(id='a' * 22, child_count=2)]
    grouped = table.query('$id,COUNT(@_children.id) AS child_count',
                          group_by='$id', order_by='$id').fetch()
    assert [dict(row) for row in grouped] == expected


@pytest.mark.parametrize('key', HIERARCHIES)
def test_inverse_projection_keeps_null_children_and_explicit_row_multiplicity(hierarchy_db, key):
    table = hierarchy_db.table(key)
    rows = table.query('$id AS parent,@_children.id AS child', order_by='$id,@_children.id').fetch()
    expected = []
    for identity, _ in NODES:
        children = [child for child, parent in NODES if parent == identity]
        expected.extend(dict(parent=identity, child=child) for child in children or [None])
    assert [dict(row) for row in rows] == expected
    # DISTINCT and count operate on SQL rows; no implicit parent aggregation.
    plain = table.query('$id', where='@_children.id IS NOT NULL', order_by='$id')
    distinct = table.query('$id', where='@_children.id IS NOT NULL', order_by='$id', distinct=True)
    assert [row['id'] for row in plain.fetch()] == [letter * 22 for letter in 'aabg']
    assert [row['id'] for row in distinct.fetch()] == [letter * 22 for letter in 'abg']
    assert plain.count() == 4
    assert distinct.count() == 3
