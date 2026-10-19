"""Write SQL on the hierarchical model, following the legacy adapter rules."""
from uuid import uuid4

import pytest

from asqueel import SqlDatabase, SqlDatabaseConfig
from asqueel.configuration import _owned_handler
from asqueel.write_compiler import WriteCompiler
from tests.native_support import postgres_dsn


def recipe(implementation, conninfo=None, path=None, schema: str | None = 'main'):
    source = SqlDatabaseConfig()
    kwargs = {'implementation': implementation}
    if conninfo:
        kwargs['conninfo'] = conninfo
    db = source.source.db('writes', **kwargs)
    if path:
        db.connection(name=str(path), implementation='sqlite')
    pkg = db.packages().package('sales', sqlschema=schema, sqlprefix=True)
    item = pkg.table('item', pkey='id')
    item.column('id', size=':22')
    item.column('name')
    item.column('label', sqlname='label_sql')
    item.column('state', sql_default="'new'")
    item.column('code', sql_value="upper(:name)")
    item.formulaColumn('double_name', sql_formula="$name || $name")
    serial = pkg.table('ticket', pkey='id')
    serial.column('id', dtype='serial')
    serial.column('note')
    row = pkg.table('row', pkey='row_key')
    row.column('order_id', dtype='L')
    row.column('line', dtype='L')
    row.column('qty', dtype='N', sqlname='qty_sql')
    row.compositeColumn('row_key', columns='order_id,line')
    return source


def bind(source):
    return SqlDatabase(model=source.render(mode='objects_tree'), config=_owned_handler(source))


@pytest.fixture(params=['postgres', 'sqlite'])
def db(request):
    database = bind(recipe(request.param))
    try:
        yield database
    finally:
        database.closeConnection()


def writer(db):
    return WriteCompiler(db.adapter)


def model(db, name):
    return db.table(name).model


def params_of(compiled):
    return dict(compiled.params)


def test_insert_omits_none_and_emits_sql_value(db):
    compiled = writer(db).insert(model(db, 'sales.item'), {'id': 'a', 'name': 'x', 'label': None}, {})
    sql = compiled.sql
    assert '"id"' in sql and '"name"' in sql and '"code"' in sql
    assert '"label_sql"' not in sql  # None is omitted: the column default applies
    assert 'upper(' in sql
    assert params_of(compiled)['name'] == 'x'


def test_insert_returns_only_database_decided_columns(db):
    compiled = writer(db).insert(model(db, 'sales.item'), {'id': 'a', 'name': 'x'}, {})
    assert compiled.sql.endswith('RETURNING "state" AS "state","code" AS "code"')
    supplied = writer(db).insert(model(db, 'sales.item'), {'id': 'a', 'name': 'x', 'state': 'old'}, {})
    assert supplied.sql.endswith('RETURNING "code" AS "code"')
    ticket = writer(db).insert(model(db, 'sales.ticket'), {'note': 'n'}, {})
    assert ticket.sql.endswith('RETURNING "id" AS "id"')


def test_insert_drops_relation_pkey_virtual_and_unknown_keys(db):
    record = {'id': 'a', 'name': 'x', '@customer': {'x': 1}, 'pkey': 'a',
              'double_name': 'xx', 'not_a_column': 5}
    compiled = writer(db).insert(model(db, 'sales.item'), record, {})
    assert '"double_name"' not in compiled.sql and '"not_a_column"' not in compiled.sql
    assert '@customer' not in params_of(compiled) and 'pkey' not in params_of(compiled)
    assert 'double_name' not in params_of(compiled)
    assert params_of(compiled)['not_a_column'] == 5  # kept as parameter, never as column


def test_insert_without_values_uses_default_values(db):
    compiled = writer(db).insert(model(db, 'sales.ticket'), {}, {})
    assert 'DEFAULT VALUES' in compiled.sql


def test_update_sets_present_keys_including_none(db):
    compiled = writer(db).update(model(db, 'sales.item'), {'id': 'a', 'label': None}, {})
    sql = compiled.sql
    assert '"label_sql"=' in sql and '"id"=' in sql and '"code"=upper(' in sql
    assert '"name"=' not in sql
    assert params_of(compiled)['label'] is None
    assert params_of(compiled)['__pkey__0'] == 'a'


def test_update_key_precedence_old_record_then_pkey_then_record(db):
    table = model(db, 'sales.item')
    from_old = writer(db).update(table, {'id': 'new'}, {}, pkey='p', old_record={'id': 'old'})
    assert params_of(from_old)['__pkey__0'] == 'old'
    from_pkey = writer(db).update(table, {'id': 'new'}, {}, pkey='p')
    assert params_of(from_pkey)['__pkey__0'] == 'p'
    from_record = writer(db).update(table, {'id': 'new'}, {})
    assert params_of(from_record)['__pkey__0'] == 'new'


def test_update_without_columns_is_refused(db):
    with pytest.raises(ValueError, match='at least one column'):
        writer(db).update(model(db, 'sales.ticket'), {'pkey': 1}, {}, pkey=1)


def test_composite_key_uses_component_sql_names(db):
    table = model(db, 'sales.row')
    deleted = writer(db).delete(table, {'order_id': 1, 'line': 2}, {})
    assert 'WHERE "order_id"=' in deleted.sql and ' AND "line"=' in deleted.sql
    updated = writer(db).update(table, {'qty': 3}, {}, pkey=(1, 2))
    assert '"qty_sql"=' in updated.sql
    assert params_of(updated)['__pkey__0'] == 1 and params_of(updated)['__pkey__1'] == 2
    with pytest.raises(ValueError, match='composite key'):
        writer(db).update(table, {'qty': 3}, {}, pkey='1,2')


def test_delete_uses_sql_names_in_where(db):
    # Legacy adapter.delete used model names in the WHERE (genropy#1691).
    source = recipe(db.adapter.dialect)
    source.source['db'].packages().package('sales').table('item').column('id', sqlname='item_key')
    other = bind(source)
    try:
        compiled = writer(other).delete(model(other, 'sales.item'), {'id': 'a'}, {})
        assert 'WHERE "item_key"=' in compiled.sql
    finally:
        other.closeConnection()


def test_lock_table_uses_nowait(db):
    compiled = writer(db).lock_table(model(db, 'sales.item'), {}, nowait=True)
    if db.adapter.dialect == 'sqlite':
        assert compiled is None
    else:
        assert compiled is not None
        assert compiled.sql.endswith('IN ACCESS EXCLUSIVE MODE NOWAIT')


# ----------------------------------------------------------------------
#  Execution
# ----------------------------------------------------------------------

CREATE = (
    'CREATE TABLE {s}sales_item (id TEXT PRIMARY KEY, name TEXT, label_sql TEXT, '
    "state TEXT DEFAULT 'new', code TEXT)",
    'CREATE TABLE {s}sales_row (order_id BIGINT, line BIGINT, qty_sql NUMERIC, PRIMARY KEY (order_id, line))',
)


@pytest.fixture(params=['sqlite', pytest.param('postgres', marks=pytest.mark.postgresql)])
def live(request, tmp_path):
    if request.param == 'sqlite':
        source, prefix = recipe('sqlite', path=tmp_path / 'writes.db', schema=None), ''
    else:
        schema = 'wc_' + uuid4().hex[:8]
        source, prefix = recipe('postgres', conninfo=postgres_dsn(), schema=schema), f'"{schema}".'
    database = bind(source)
    try:
        if prefix:
            database.execute(f'CREATE SCHEMA {prefix[:-1]}')
        for statement in CREATE:
            database.execute(statement.format(s=prefix))
        database.commit()
        try:
            yield database
        finally:
            database.rollback()
            if prefix:
                database.execute(f'DROP SCHEMA {prefix[:-1]} CASCADE')
                database.commit()
    finally:
        database.closeConnection()


def rows(db, sql):
    return [dict(row) for row in db.execute(sql).rows]


def test_executed_insert_update_delete(live):
    db, compile = live, writer(live)
    prefix = '' if db.adapter.dialect == 'sqlite' else model(db, 'sales.item').sqlschema
    item_sql = f'"{prefix}".sales_item' if prefix else 'sales_item'
    inserted = db.execute(compile.insert(model(db, 'sales.item'), {'id': 'a', 'name': 'ada', 'state': None}, {}))
    assert [dict(row) for row in inserted.rows] == [{'state': 'new', 'code': 'ADA'}]
    db.execute(compile.update(model(db, 'sales.item'), {'id': 'a', 'label': 'L', 'name': 'bob'}, {}))
    assert rows(db, f'SELECT id, name, label_sql, state, code FROM {item_sql}') == [
        {'id': 'a', 'name': 'bob', 'label_sql': 'L', 'state': 'new', 'code': 'BOB'}]
    renamed = db.execute(compile.update(model(db, 'sales.item'), {'id': 'b', 'name': 'bob'}, {},
                                        old_record={'id': 'a'}))
    assert renamed.rowcount == 1
    deleted = db.execute(compile.delete(model(db, 'sales.item'), {'id': 'b'}, {}))
    assert deleted.rowcount == 1
    assert rows(db, f'SELECT id FROM {item_sql}') == []
    db.commit()


def seed(db, prefix):
    for key, name, state in (('a', 'ada', 'old'), ('b', 'bob', 'old'), ('c', 'cid', 'new')):
        db.execute(f"INSERT INTO {prefix}sales_item (id, name, state) VALUES ('{key}', '{name}', '{state}')")
    for order_id, line in ((1, 1), (1, 2), (2, 1)):
        db.execute(f'INSERT INTO {prefix}sales_row (order_id, line, qty_sql) VALUES ({order_id}, {line}, 1)')


def item_sql(db):
    schema = model(db, 'sales.item').sqlschema
    return (f'"{schema}".' if db.adapter.dialect == 'postgres' else ''), schema


def test_query_fetch_then_sql_update_and_sql_delete(live):
    db = live
    prefix, _ = item_sql(db)
    seed(db, prefix)
    query = db.table('sales.item').query(columns='$name', where='$state = :s', s='old',
                                         order_by='$name', addPkeyColumn=True)
    assert [(row['pkey'], row['name']) for row in query.fetch()] == [('a', 'ada'), ('b', 'bob')]
    assert query.sql_update({'label': 'checked'}) == 2
    assert rows(db, f'SELECT id FROM {prefix}sales_item WHERE label_sql = \'checked\' ORDER BY id') == [
        {'id': 'a'}, {'id': 'b'}]
    first = db.table('sales.item').query(columns='$name', where='$state = :s', s='old', order_by='$name', limit=1)
    assert first.sql_delete() == 1
    assert rows(db, f'SELECT id FROM {prefix}sales_item ORDER BY id') == [{'id': 'b'}, {'id': 'c'}]
    assert query.sql_delete() == 1
    assert rows(db, f'SELECT id FROM {prefix}sales_item ORDER BY id') == [{'id': 'c'}]
    db.commit()



def test_query_sql_update_refuses_shared_parameter_names(db):
    query = db.table('sales.item').query(where='$name = :name', name='x')
    with pytest.raises(ValueError, match='both the query and the values'):
        writer(db).update_selection(model(db, 'sales.item'), query._key_plan(model(db, 'sales.item')),
                                    {'name': 'y'}, {})


def test_selection_statement_embeds_the_key_select(db):
    query = db.table('sales.item').query(where='$name > :q', q='a')
    compiled = writer(db).delete_selection(model(db, 'sales.item'), query._key_plan(model(db, 'sales.item')), {})
    assert compiled.sql.startswith('DELETE FROM') and '("id") IN (SELECT' in compiled.sql


def test_insert_many_groups_consecutive_records_with_the_same_columns(db):
    records = [{'id': 'a', 'name': 'x'}, {'id': 'b', 'name': 'y'}, {'id': 'c'}, {'id': 'd', 'name': 'z'}]
    groups = writer(db).insert_many(model(db, 'sales.item'), records, {})
    assert [len(params) for _, params in groups] == [2, 1, 1]
    assert all('RETURNING' not in compiled.sql for compiled, _ in groups)


def test_table_sql_commands_without_triggers(live):
    db = live
    prefix, _ = item_sql(db)
    table = db.table('sales.item')
    record = {'id': 'a', 'name': 'ada'}
    assert table.sql_insert(record) is record
    assert record['state'] == 'new' and record['code'] == 'ADA'
    batch = [{'id': 'b', 'name': 'bob'}, {'id': 'c', 'name': 'cid'}, {'id': 'd'}]
    assert table.sql_insert(batch) is batch
    assert rows(db, f'SELECT id, code FROM {prefix}sales_item ORDER BY id') == [
        {'id': 'a', 'code': 'ADA'}, {'id': 'b', 'code': 'BOB'}, {'id': 'c', 'code': 'CID'}, {'id': 'd', 'code': None}]
    assert table.sql_update({'id': 'z', 'name': 'zed'}, old_record={'id': 'd'}) is None
    assert table.sql_delete({'id': 'a'}) is None
    assert rows(db, f'SELECT id, name FROM {prefix}sales_item ORDER BY id') == [
        {'id': 'b', 'name': 'bob'}, {'id': 'c', 'name': 'cid'}, {'id': 'z', 'name': 'zed'}]
    db.commit()
